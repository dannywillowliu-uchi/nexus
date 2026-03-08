from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from nexus.agents.literature.agent import LiteratureResult, run_literature_agent
from nexus.agents.literature.extract import Triple
from nexus.agents.reasoning_agent import generate_quick_summaries, generate_research_brief
from nexus.checkpoint.agent import run_checkpoint
from nexus.checkpoint.models import CheckpointContext, CheckpointDecision
from nexus.graph.abc import ABCHypothesis, find_abc_hypotheses
from nexus.graph.client import graph_client
from nexus.tools.molecular_dock import molecular_dock
from nexus.tracing.tracer import get_tracer

logger = logging.getLogger(__name__)

DEFAULT_TARGET_TYPES = ["Drug", "Gene"]

MAX_CONCURRENT_BRANCHES = 3
BRANCH_TIMEOUT = 30.0


class PipelineStep(Enum):
	LITERATURE = "literature"
	GRAPH = "graph"
	REASONING = "reasoning"
	VALIDATION = "validation"
	VISUALIZATION = "visualization"
	PROTOCOL = "protocol"
	EXPERIMENT = "experiment"
	COMPLETED = "completed"
	FAILED = "failed"


@dataclass
class PipelineResult:
	query: str
	start_entity: str
	start_type: str
	step: PipelineStep = PipelineStep.LITERATURE
	literature_result: LiteratureResult | None = None
	hypotheses: list[ABCHypothesis] = field(default_factory=list)
	scored_hypotheses: list[dict] = field(default_factory=list)
	research_briefs: list[dict] = field(default_factory=list)
	validation_results: list[dict] = field(default_factory=list)
	pivots: list[dict] = field(default_factory=list)
	branches: list = field(default_factory=list)
	errors: list[str] = field(default_factory=list)
	checkpoint_log: list[dict] = field(default_factory=list)
	experiment_results: list[dict] = field(default_factory=list)


LABEL_MAP: dict[str, str] = {
	"gene": "Gene", "protein": "Gene", "gene/protein": "Gene",
	"drug": "Drug", "compound": "Drug",
	"disease": "Disease",
	"biological_process": "BiologicalProcess", "biologicalprocess": "BiologicalProcess",
	"molecular_function": "MolecularFunction", "molecularfunction": "MolecularFunction",
	"cellular_component": "CellularComponent", "cellularcomponent": "CellularComponent",
	"pathway": "Pathway",
	"anatomy": "Anatomy",
	"phenotype": "Phenotype", "effect/phenotype": "Phenotype",
	"exposure": "Exposure",
}


def _resolve_label(entity_type: str) -> str:
	"""Map extracted entity type to a PrimeKG node label."""
	return LABEL_MAP.get(entity_type.lower(), "Gene")


def _normalize_entity_name(name: str) -> str:
	"""Normalize entity name for fuzzy matching against PrimeKG."""
	normalized = name.strip()
	# Remove Greek letters and their spelled-out forms
	for greek in ["α", "β", "γ", "δ", "ε", "-alpha", "-beta", "-gamma", "-delta"]:
		normalized = normalized.replace(greek, "")
	# Remove phospho- prefix
	normalized = normalized.replace("phospho-", "").replace("p-", "")
	return normalized.strip().rstrip("-")


async def _resolve_entity_in_graph(entity_name: str, entity_type: str) -> str | None:
	"""Try to find an existing PrimeKG node matching this entity name.

	Returns the exact PrimeKG node name if found, None otherwise.
	"""
	label = _resolve_label(entity_type)

	# 1. Exact match (case-insensitive) on the expected label
	result = await graph_client.execute_read(
		f"MATCH (n:{label}) WHERE toLower(n.name) = toLower($name) RETURN n.name LIMIT 1",
		name=entity_name,
	)
	if result:
		return result[0]["n.name"]

	# 2. Try normalized version (TNF-α → TNF, IL-6 → IL6)
	normalized = _normalize_entity_name(entity_name)
	if normalized and normalized != entity_name:
		result = await graph_client.execute_read(
			f"MATCH (n:{label}) WHERE toLower(n.name) = toLower($name) RETURN n.name LIMIT 1",
			name=normalized,
		)
		if result:
			return result[0]["n.name"]

	# 3. Try common variations
	variations = [
		entity_name.upper(),
		entity_name.replace("-", ""),
		entity_name.split("(")[0].strip(),
		entity_name.split("/")[0].strip(),
	]
	# Base name before first dash/space (e.g. "TNF-alpha" → "TNF")
	base = re.split(r"[-\s]", entity_name)[0]
	if base and base != entity_name:
		variations.append(base)

	for var in variations:
		if var and var != entity_name:
			result = await graph_client.execute_read(
				f"MATCH (n:{label}) WHERE toLower(n.name) = toLower($name) RETURN n.name LIMIT 1",
				name=var,
			)
			if result:
				return result[0]["n.name"]

	# 4. Any label — exact match (entity type from extraction might be wrong)
	result = await graph_client.execute_read(
		"MATCH (n) WHERE toLower(n.name) = toLower($name) RETURN n.name LIMIT 1",
		name=entity_name,
	)
	if result:
		return result[0]["n.name"]

	# 5. Any label — normalized
	if normalized and normalized != entity_name:
		result = await graph_client.execute_read(
			"MATCH (n) WHERE toLower(n.name) = toLower($name) RETURN n.name LIMIT 1",
			name=normalized,
		)
		if result:
			return result[0]["n.name"]

	return None


async def merge_triples_to_graph(triples: list[Triple]) -> int:
	"""Merge extracted triples into Neo4j as LITERATURE_ASSOCIATION edges.

	Before creating nodes, resolves entity names against existing PrimeKG nodes
	using fuzzy matching (e.g. "TNF-α" → "TNF", "IL-6" → "IL6").
	"""
	count = 0
	for triple in triples:
		s_label = _resolve_label(triple.subject_type)
		o_label = _resolve_label(triple.object_type)

		# Resolve entities against existing graph nodes
		resolved_subject = await _resolve_entity_in_graph(triple.subject, triple.subject_type)
		resolved_object = await _resolve_entity_in_graph(triple.object, triple.object_type)

		subject_name = resolved_subject or triple.subject
		object_name = resolved_object or triple.object

		if resolved_subject and resolved_subject != triple.subject:
			logger.info("Resolved '%s' → existing node '%s'", triple.subject, resolved_subject)
		if resolved_object and resolved_object != triple.object:
			logger.info("Resolved '%s' → existing node '%s'", triple.object, resolved_object)

		# Use the resolved label if we matched an existing node
		if resolved_subject:
			s_match = await graph_client.execute_read(
				"MATCH (n {name: $name}) RETURN labels(n)[0] AS label LIMIT 1",
				name=resolved_subject,
			)
			if s_match:
				s_label = s_match[0]["label"]
		if resolved_object:
			o_match = await graph_client.execute_read(
				"MATCH (n {name: $name}) RETURN labels(n)[0] AS label LIMIT 1",
				name=resolved_object,
			)
			if o_match:
				o_label = o_match[0]["label"]

		query = (
			f"MERGE (s:{s_label} {{name: $subject}}) "
			f"ON CREATE SET s.node_type = $subject_type, s.source = 'literature_extraction' "
			f"MERGE (o:{o_label} {{name: $object}}) "
			f"ON CREATE SET o.node_type = $object_type, o.source = 'literature_extraction' "
			f"MERGE (s)-[r:LITERATURE_ASSOCIATION]->(o) "
			f"SET r.source = 'literature', r.is_novel = true, "
			f"r.predicate = $predicate, r.confidence = $confidence, "
			f"r.source_papers = [$source_paper_id] "
			f"RETURN r"
		)
		try:
			result = await graph_client.execute_write(
				query,
				subject=subject_name,
				subject_type=triple.subject_type,
				object=object_name,
				object_type=triple.object_type,
				predicate=triple.predicate,
				confidence=triple.confidence,
				source_paper_id=triple.source_paper_id,
			)
			count += len(result)
		except Exception:
			logger.warning("Failed to merge triple: %s -> %s", subject_name, object_name)
	return count


def _fuzzy_entity_match(entity: str, triple_text: str) -> bool:
	"""Check if an entity name appears in triple text, with partial matching."""
	entity_lower = entity.lower()
	text_lower = triple_text.lower()
	if entity_lower == text_lower:
		return True
	if entity_lower in text_lower or text_lower in entity_lower:
		return True
	entity_words = set(entity_lower.split())
	text_words = set(text_lower.split())
	if entity_words and text_words:
		overlap = entity_words & text_words
		if len(overlap) / min(len(entity_words), len(text_words)) > 0.5:
			return True
	return False


async def _update_graph_edge_status(
	a_name: str,
	c_name: str,
	status: str,
	confidence: float,
) -> None:
	"""Update a hypothesized A-C edge in Neo4j with experiment results."""
	query = """
		MATCH (a {name: $a_name})-[r]->(c {name: $c_name})
		WHERE r.is_novel = true
		SET r.status = $status, r.validation_score = $confidence
		RETURN r
	"""
	try:
		await graph_client.execute_write(
			query,
			a_name=a_name,
			c_name=c_name,
			status=status,
			confidence=confidence,
		)
	except Exception:
		logger.warning("Failed to update graph edge %s -> %s", a_name, c_name)


def score_hypothesis(abc: ABCHypothesis, triples: list[Triple]) -> dict:
	"""Score a hypothesis based on evidence from triples."""
	# Count relevant triples using fuzzy matching (entity names from literature
	# often don't exactly match graph node names)
	path_entities = [abc.a_name, abc.b_name, abc.c_name]
	relevant_count = 0
	for t in triples:
		for entity in path_entities:
			if _fuzzy_entity_match(entity, t.subject) or _fuzzy_entity_match(entity, t.object):
				relevant_count += 1
				break
	evidence_score = min(relevant_count / 5.0, 1.0)

	# Determine hypothesis type from A/C types
	a_type = abc.a_type.lower()
	c_type = abc.c_type.lower()
	if a_type == "compound":
		a_type = "drug"
	if c_type == "compound":
		c_type = "drug"
	type_pair = frozenset({a_type, c_type})

	if type_pair == frozenset({"disease", "drug"}):
		hypothesis_type = "drug_repurposing"
	elif type_pair == frozenset({"disease"}) or (a_type == "disease" and c_type == "disease"):
		hypothesis_type = "comorbidity"
	elif c_type in ("biologicalprocess", "pathway", "molecularfunction"):
		hypothesis_type = "mechanism"
	elif type_pair == frozenset({"drug"}):
		hypothesis_type = "drug_interaction"
	elif c_type in ("gene", "protein"):
		hypothesis_type = "target_discovery"
	else:
		hypothesis_type = "connection"

	overall_score = abc.novelty_score * 0.3 + evidence_score * 0.4 + abc.path_strength * 0.3

	return {
		"title": f"{abc.a_name} -> {abc.c_name} via {abc.b_name}",
		"description": f"{abc.a_name} may be linked to {abc.c_name} through {abc.b_name} "
			f"({abc.ab_relationship} / {abc.bc_relationship})",
		"disease_area": abc.a_name if abc.a_type == "Disease" else abc.c_name if abc.c_type == "Disease" else "",
		"hypothesis_type": hypothesis_type,
		"novelty_score": abc.novelty_score,
		"evidence_score": evidence_score,
		"path_strength": abc.path_strength,
		"overall_score": round(overall_score, 4),
		"abc_path": {
			"a": {"id": abc.a_id, "name": abc.a_name, "type": abc.a_type},
			"b": {"id": abc.b_id, "name": abc.b_name, "type": abc.b_type},
			"c": {"id": abc.c_id, "name": abc.c_name, "type": abc.c_type},
		},
		"intermediaries": abc.intermediaries,
	}


async def _run_branch(
	entity_name: str,
	entity_type: str,
	target_types: list[str],
	triples: list[Triple],
	max_hypotheses: int = 10,
) -> list[dict]:
	"""Lightweight branch: entity resolution + graph search + scoring only."""
	candidates = await graph_client.resolve_entity_multi(entity_name, entity_type=entity_type)
	if candidates:
		entity_name = candidates[0].name
		entity_type = candidates[0].type

	all_hypotheses: list[ABCHypothesis] = []
	for target in target_types:
		hyps = await find_abc_hypotheses(
			source_name=entity_name,
			source_type=entity_type,
			target_type=target,
		)
		all_hypotheses.extend(hyps)

	scored = [score_hypothesis(h, triples) for h in all_hypotheses]
	scored.sort(key=lambda h: h.get("overall_score", 0), reverse=True)
	return scored[:max_hypotheses]


async def _emit(on_event: Callable | None, event_type: str, data: dict) -> None:
	"""Fire the on_event callback if provided."""
	if on_event is not None:
		await on_event(event_type, data)


async def run_pipeline(
	query: str,
	start_entity: str | None = None,
	start_type: str = "Disease",
	target_types: list[str] | None = None,
	max_hypotheses: int = 10,
	max_papers: int = 10,
	max_pivots: int = 3,
	on_event: Callable | None = None,
) -> PipelineResult:
	"""Run the full adaptive discovery pipeline with checkpoint-driven pivots."""
	source_name = start_entity or query
	result = PipelineResult(query=query, start_entity=source_name, start_type=start_type)
	targets = target_types or DEFAULT_TARGET_TYPES
	pivot_count = 0

	tracer = get_tracer()

	try:
		# --- Literature stage ---
		result.step = PipelineStep.LITERATURE
		await _emit(on_event, "stage_start", {"stage": "literature", "entity": source_name})

		if tracer:
			with tracer.span("literature_agent", input_data={"query": query, "max_papers": max_papers}) as lit_span:
				lit_result = await run_literature_agent(query, max_papers=max_papers)
				lit_span.set_output({
					"papers": len(lit_result.papers),
					"triples": len(lit_result.triples),
					"errors": lit_result.errors,
				})
		else:
			lit_result = await run_literature_agent(query, max_papers=max_papers)
		result.literature_result = lit_result
		result.errors.extend(lit_result.errors)

		if lit_result.triples:
			if tracer:
				with tracer.span("merge_triples_to_graph", input_data={"count": len(lit_result.triples)}) as merge_span:
					merged = await merge_triples_to_graph(lit_result.triples)
					merge_span.set_output({"merged": merged})
			else:
				merged = await merge_triples_to_graph(lit_result.triples)
			await _emit(on_event, "triples_merged", {"count": merged})

		await _emit(on_event, "stage_complete", {
			"stage": "literature",
			"papers": len(lit_result.papers),
			"triples": len(lit_result.triples),
		})

		# --- Checkpoint after literature ---
		triples_dicts = [
			{"subject": t.subject, "predicate": t.predicate, "object": t.object}
			for t in lit_result.triples
		]
		lit_checkpoint_ctx = CheckpointContext(
			stage="literature",
			original_query=query,
			current_entity=source_name,
			current_entity_type=start_type,
			pivot_count=pivot_count,
			max_pivots=max_pivots,
			triples=triples_dicts,
		)
		if tracer:
			with tracer.span("checkpoint_literature", input_data={"entity": source_name, "pivots": pivot_count}) as cp_span:
				lit_cp = await run_checkpoint(lit_checkpoint_ctx)
				cp_span.set_output({"decision": lit_cp.decision.value, "reason": lit_cp.reason, "confidence": lit_cp.confidence})
		else:
			lit_cp = await run_checkpoint(lit_checkpoint_ctx)
		result.checkpoint_log.append({
			"stage": "literature",
			"decision": lit_cp.decision.value,
			"reason": lit_cp.reason,
			"confidence": lit_cp.confidence,
		})

		if lit_cp.decision == CheckpointDecision.PIVOT and lit_cp.pivot_entity:
			source_name = lit_cp.pivot_entity
			start_type = lit_cp.pivot_entity_type or start_type
			pivot_count += 1
			result.pivots.append({
				"from_entity": result.start_entity,
				"to_entity": source_name,
				"to_type": start_type,
				"reason": lit_cp.reason,
				"stage": "literature",
			})
			await _emit(on_event, "pivot", {"entity": source_name, "reason": lit_cp.reason})

		elif lit_cp.decision == CheckpointDecision.BRANCH:
			branch_entities_raw = lit_cp.branch_entities or []
			if not branch_entities_raw and lit_cp.pivot_entity:
				branch_entities_raw = [{"name": lit_cp.pivot_entity, "type": lit_cp.pivot_entity_type or start_type}]
			branch_entities_raw = branch_entities_raw[:MAX_CONCURRENT_BRANCHES]

			sem = asyncio.Semaphore(MAX_CONCURRENT_BRANCHES)
			triples_for_branches = lit_result.triples if lit_result else []

			async def bounded_branch(ent: dict) -> list[dict]:
				async with sem:
					return await asyncio.wait_for(
						_run_branch(
							ent["name"], ent.get("type", start_type),
							targets, triples_for_branches,
						),
						timeout=BRANCH_TIMEOUT,
					)

			branch_tasks = [asyncio.create_task(bounded_branch(e)) for e in branch_entities_raw]
			for task in asyncio.as_completed(branch_tasks):
				try:
					branch_scored = await task
					result.branches.append(branch_scored)
					result.scored_hypotheses.extend(branch_scored)
				except (TimeoutError, Exception) as exc:
					result.errors.append(f"Branch failed: {exc}")

			await _emit(on_event, "branch", {
				"entities": [e["name"] for e in branch_entities_raw],
				"reason": lit_cp.reason,
			})

		# --- Entity resolution ---
		candidates = await graph_client.resolve_entity_multi(source_name, entity_type=start_type)
		if candidates:
			resolved = candidates[0]
			logger.info("Resolved '%s' -> '%s' (method=%s)", source_name, resolved.name, resolved.match_method)
			if len(candidates) > 1:
				alt_names = [c.name for c in candidates[1:]]
				logger.info("Alternative matches for '%s': %s", source_name, alt_names)
			source_name = resolved.name
			start_type = resolved.type
			result.start_entity = source_name
			result.start_type = start_type
			await _emit(on_event, "entity_resolved", {
				"original": resolved.original_query,
				"resolved": resolved.name,
				"type": resolved.type,
				"method": resolved.match_method,
				"alternatives": [
					{"name": c.name, "type": c.type, "identifier": c.identifier}
					for c in candidates[1:]
				],
			})
		else:
			logger.warning("Could not resolve '%s' in graph", source_name)
			await _emit(on_event, "entity_resolved", {
				"original": source_name,
				"resolved": source_name,
				"type": start_type,
				"method": "unresolved",
				"alternatives": [],
			})

		# --- Graph stage ---
		result.step = PipelineStep.GRAPH
		await _emit(on_event, "stage_start", {"stage": "graph", "entity": source_name})

		all_hypotheses: list[ABCHypothesis] = []
		if tracer:
			with tracer.span("graph_abc_search", input_data={"entity": source_name, "targets": targets}) as graph_span:
				for target in targets:
					hyps = await find_abc_hypotheses(
						source_name=source_name,
						source_type=start_type,
						target_type=target,
					)
					all_hypotheses.extend(hyps)
				graph_span.set_output({"hypotheses_found": len(all_hypotheses)})
		else:
			for target in targets:
				hyps = await find_abc_hypotheses(
					source_name=source_name,
					source_type=start_type,
					target_type=target,
				)
				all_hypotheses.extend(hyps)

		result.hypotheses = all_hypotheses
		triples_for_scoring = lit_result.triples if lit_result else []
		scored = [score_hypothesis(h, triples_for_scoring) for h in all_hypotheses]
		result.scored_hypotheses = scored

		await _emit(on_event, "stage_complete", {
			"stage": "graph",
			"hypotheses": len(all_hypotheses),
			"scored": len(scored),
		})

		# --- Checkpoint after graph ---
		hyp_dicts = [
			{"a_name": h.a_name, "b_name": h.b_name, "c_name": h.c_name, "novelty_score": h.novelty_score}
			for h in all_hypotheses
		]
		graph_checkpoint_ctx = CheckpointContext(
			stage="graph",
			original_query=query,
			current_entity=source_name,
			current_entity_type=start_type,
			pivot_count=pivot_count,
			max_pivots=max_pivots,
			hypotheses=hyp_dicts,
		)
		if tracer:
			with tracer.span("checkpoint_graph", input_data={"entity": source_name, "hypotheses": len(all_hypotheses)}) as gcp_span:
				graph_cp = await run_checkpoint(graph_checkpoint_ctx)
				gcp_span.set_output({"decision": graph_cp.decision.value, "reason": graph_cp.reason})
		else:
			graph_cp = await run_checkpoint(graph_checkpoint_ctx)
		result.checkpoint_log.append({
			"stage": "graph",
			"decision": graph_cp.decision.value,
			"reason": graph_cp.reason,
			"confidence": graph_cp.confidence,
		})

		if graph_cp.decision == CheckpointDecision.PIVOT and graph_cp.pivot_entity:
			pivot_count += 1
			result.pivots.append({
				"from_entity": source_name,
				"to_entity": graph_cp.pivot_entity,
				"to_type": graph_cp.pivot_entity_type or start_type,
				"reason": graph_cp.reason,
				"stage": "graph",
			})
			await _emit(on_event, "pivot", {"entity": graph_cp.pivot_entity, "reason": graph_cp.reason})

			# Re-run literature + graph for the new pivot entity
			pivot_query = f"{query} {graph_cp.pivot_entity}"
			pivot_lit = await run_literature_agent(pivot_query, max_papers=max_papers)
			result.errors.extend(pivot_lit.errors)

			if pivot_lit.triples:
				await merge_triples_to_graph(pivot_lit.triples)

			pivot_source = graph_cp.pivot_entity
			pivot_type = graph_cp.pivot_entity_type or start_type
			for target in targets:
				hyps = await find_abc_hypotheses(
					source_name=pivot_source,
					source_type=pivot_type,
					target_type=target,
				)
				result.hypotheses.extend(hyps)
				pivot_scored = [score_hypothesis(h, pivot_lit.triples) for h in hyps]
				result.scored_hypotheses.extend(pivot_scored)

		# --- Sort and trim ---
		result.scored_hypotheses.sort(key=lambda h: h.get("overall_score", 0), reverse=True)
		result.scored_hypotheses = result.scored_hypotheses[:max_hypotheses]

		# --- Reasoning stage: generate research briefs for top hypotheses ---
		result.step = PipelineStep.REASONING
		await _emit(on_event, "stage_start", {"stage": "reasoning", "count": len(result.scored_hypotheses)})

		# Map scored hypotheses back to ABCHypothesis objects for the reasoning agent
		top_abc = result.hypotheses[:max_hypotheses]
		triples_for_reasoning = lit_result.triples if lit_result else []

		# Quick summaries for all top hypotheses
		summaries = await generate_quick_summaries(top_abc, triples_for_reasoning)
		for i, sh in enumerate(result.scored_hypotheses):
			if i < len(summaries):
				sh["summary"] = summaries[i]

		# Detailed research briefs for the top 3
		papers_dicts = []
		if lit_result:
			papers_dicts = [
				{"paper_id": p.paper_id, "title": p.title, "abstract": p.abstract}
				for p in lit_result.papers
			]

		for i, abc_hyp in enumerate(top_abc[:3]):
			try:
				brief = await generate_research_brief(abc_hyp, triples_for_reasoning, papers_dicts)
				brief_dict = {
					"hypothesis_title": brief.hypothesis_title,
					"connection_explanation": brief.connection_explanation,
					"literature_evidence": [
						{"paper_id": e.paper_id, "title": e.title, "snippet": e.snippet, "confidence": e.confidence}
						for e in brief.literature_evidence
					],
					"existing_knowledge_comparison": brief.existing_knowledge_comparison,
					"confidence": {
						"graph_evidence": brief.confidence.graph_evidence,
						"literature_support": brief.confidence.literature_support,
						"biological_plausibility": brief.confidence.biological_plausibility,
						"novelty": brief.confidence.novelty,
					},
					"suggested_validation": brief.suggested_validation,
					"researcher_narrative": brief.researcher_narrative,
				}
				result.research_briefs.append(brief_dict)
				if i < len(result.scored_hypotheses):
					result.scored_hypotheses[i]["research_brief"] = brief_dict
			except Exception as exc:
				logger.warning("Research brief generation failed for hypothesis %d: %s", i, exc)

		await _emit(on_event, "stage_complete", {
			"stage": "reasoning",
			"summaries": len(summaries),
			"briefs": len(result.research_briefs),
		})

		# --- Validation stage: molecular docking for drug-gene hypotheses ---
		result.step = PipelineStep.VALIDATION
		await _emit(on_event, "stage_start", {"stage": "validation"})

		for sh in result.scored_hypotheses[:3]:
			abc_path = sh.get("abc_path", {})
			a_type = abc_path.get("a", {}).get("type", "")
			b_type = abc_path.get("b", {}).get("type", "")
			a_name = abc_path.get("a", {}).get("name", "")
			b_name = abc_path.get("b", {}).get("name", "")

			# Only dock Drug-Gene pairs
			if a_type == "Drug" and b_type == "Gene":
				try:
					dock_result = await molecular_dock(a_name, b_name)
					validation_entry = {
						"tool": "molecular_dock",
						"compound": a_name,
						"protein": b_name,
						"status": dock_result.status,
						"confidence_delta": dock_result.confidence_delta,
						"evidence_type": dock_result.evidence_type,
						"summary": dock_result.summary,
					}
					result.validation_results.append(validation_entry)
					sh["validation"] = validation_entry
				except Exception as exc:
					logger.warning("Molecular docking failed for %s + %s: %s", a_name, b_name, exc)

		await _emit(on_event, "stage_complete", {
			"stage": "validation",
			"docking_results": len(result.validation_results),
		})

		result.step = PipelineStep.COMPLETED
		await _emit(on_event, "pipeline_complete", {
			"hypotheses": len(result.scored_hypotheses),
			"briefs": len(result.research_briefs),
			"validations": len(result.validation_results),
			"pivots": len(result.pivots),
			"branches": len(result.branches),
		})

	except Exception as exc:
		logger.exception("Pipeline failed")
		result.step = PipelineStep.FAILED
		result.errors.append(f"Pipeline error: {exc}")

	return result
