from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)

DEFAULT_TARGET_TYPES = ["Drug", "Gene"]


class PipelineStep(Enum):
	LITERATURE = "literature"
	GRAPH = "graph"
	REASONING = "reasoning"
	VALIDATION = "validation"
	VISUALIZATION = "visualization"
	PROTOCOL = "protocol"
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


async def merge_triples_to_graph(triples: list[Triple]) -> int:
	"""Merge extracted triples into Neo4j as LITERATURE_ASSOCIATION edges."""
	count = 0
	for triple in triples:
		s_label = _resolve_label(triple.subject_type)
		o_label = _resolve_label(triple.object_type)
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
				subject=triple.subject,
				subject_type=triple.subject_type,
				object=triple.object,
				object_type=triple.object_type,
				predicate=triple.predicate,
				confidence=triple.confidence,
				source_paper_id=triple.source_paper_id,
			)
			count += len(result)
		except Exception:
			logger.warning("Failed to merge triple: %s -> %s", triple.subject, triple.object)
	return count


def score_hypothesis(abc: ABCHypothesis, triples: list[Triple]) -> dict:
	"""Score a hypothesis based on evidence from triples."""
	# Count relevant triples (where subject or object matches any entity in the path)
	path_entities = {abc.a_name.lower(), abc.b_name.lower(), abc.c_name.lower()}
	relevant_count = sum(
		1 for t in triples
		if t.subject.lower() in path_entities or t.object.lower() in path_entities
	)
	evidence_score = min(relevant_count / 5.0, 1.0)

	# Determine hypothesis type from A/C types
	a_type = abc.a_type.lower()
	c_type = abc.c_type.lower()
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
	branch_futures: list[asyncio.Task] = []

	try:
		# --- Literature stage ---
		result.step = PipelineStep.LITERATURE
		await _emit(on_event, "stage_start", {"stage": "literature", "entity": source_name})

		lit_result = await run_literature_agent(query, max_papers=max_papers)
		result.literature_result = lit_result
		result.errors.extend(lit_result.errors)

		if lit_result.triples:
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

		elif lit_cp.decision == CheckpointDecision.BRANCH and lit_cp.pivot_entity:
			branch_task = asyncio.create_task(run_pipeline(
				query=query,
				start_entity=lit_cp.pivot_entity,
				start_type=lit_cp.pivot_entity_type or start_type,
				target_types=targets,
				max_hypotheses=max_hypotheses,
				max_papers=max_papers,
				max_pivots=0,
				on_event=on_event,
			))
			branch_futures.append(branch_task)
			await _emit(on_event, "branch", {"entity": lit_cp.pivot_entity, "reason": lit_cp.reason})

		# --- Graph stage ---
		result.step = PipelineStep.GRAPH
		await _emit(on_event, "stage_start", {"stage": "graph", "entity": source_name})

		all_hypotheses: list[ABCHypothesis] = []
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

		# --- Await branches and merge ---
		for future in branch_futures:
			try:
				branch_result = await future
				result.branches.append(branch_result)
				result.scored_hypotheses.extend(branch_result.scored_hypotheses)
			except Exception as exc:
				result.errors.append(f"Branch failed: {exc}")

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
