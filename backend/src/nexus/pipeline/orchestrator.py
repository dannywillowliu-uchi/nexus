from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from nexus.agents.literature.agent import LiteratureResult, run_literature_agent
from nexus.agents.literature.extract import Triple
from nexus.checkpoint.agent import run_checkpoint
from nexus.checkpoint.models import CheckpointContext, CheckpointDecision
from nexus.graph.abc import ABCHypothesis, find_abc_hypotheses
from nexus.graph.client import graph_client

logger = logging.getLogger(__name__)

DEFAULT_TARGET_TYPES = ["Compound", "Gene"]


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
	pivots: list[dict] = field(default_factory=list)
	branches: list = field(default_factory=list)
	errors: list[str] = field(default_factory=list)
	checkpoint_log: list[dict] = field(default_factory=list)


async def merge_triples_to_graph(triples: list[Triple]) -> int:
	"""Merge extracted triples into Neo4j as new edges."""
	count = 0
	for triple in triples:
		query = """
			MERGE (s {name: $subject})
			ON CREATE SET s:Entity, s.type = $subject_type
			MERGE (o {name: $object})
			ON CREATE SET o:Entity, o.type = $object_type
			MERGE (s)-[r:LITERATURE_EDGE {predicate: $predicate}]->(o)
			ON CREATE SET r.source = "literature", r.is_novel = true,
				r.confidence = $confidence, r.source_paper_id = $source_paper_id
			RETURN r
		"""
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

	if type_pair == frozenset({"disease", "compound"}):
		hypothesis_type = "drug_repurposing"
	elif type_pair == frozenset({"disease"}) or (a_type == "disease" and c_type == "disease"):
		hypothesis_type = "comorbidity"
	elif c_type in ("biologicalprocess", "pathway", "molecularfunction"):
		hypothesis_type = "mechanism"
	elif type_pair == frozenset({"compound"}):
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

		result.step = PipelineStep.COMPLETED
		await _emit(on_event, "pipeline_complete", {
			"hypotheses": len(result.scored_hypotheses),
			"pivots": len(result.pivots),
			"branches": len(result.branches),
		})

	except Exception as exc:
		logger.exception("Pipeline failed")
		result.step = PipelineStep.FAILED
		result.errors.append(f"Pipeline error: {exc}")

	return result
