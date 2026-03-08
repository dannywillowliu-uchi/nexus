"""Discovery narrative generation from pipeline trace data."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from nexus.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000

NARRATIVE_PROMPT = """You are a science writer. Given the trace data from an automated biological discovery pipeline, write a compelling chronological narrative of how this discovery was made. Write in past tense, third person ("The pipeline...").

Query: {query}
Starting entity: {start_entity} ({start_type})

Pipeline trace:
{trace_text}

Write a 3-5 paragraph narrative that:
1. Opens with what question was being investigated and why
2. Walks through each key decision point — what the pipeline found, why it continued/pivoted/branched
3. Highlights surprising or counterintuitive findings
4. Ends with how the final hypothesis emerged from this process

Keep it concise and scientifically accurate. No markdown headers — just flowing paragraphs.
Return ONLY the narrative text."""


def _build_trace_text(
	checkpoint_log: list[dict[str, Any]],
	pivots: list[dict[str, Any]],
	branches: list[Any],
	validation_results: list[dict[str, Any]],
	literature_stats: dict[str, Any] | None = None,
	graph_stats: dict[str, Any] | None = None,
) -> str:
	"""Assemble pipeline trace into text for the narrative prompt."""
	parts: list[str] = []

	if literature_stats:
		parts.append(
			f"LITERATURE STAGE: Found {literature_stats.get('papers', 0)} papers, "
			f"extracted {literature_stats.get('triples', 0)} triples"
		)

	for cp in checkpoint_log:
		parts.append(
			f"CHECKPOINT ({cp.get('stage', '?')}): Decision={cp.get('decision', '?')} | "
			f"Reason: {cp.get('reason', 'N/A')} | Confidence: {cp.get('confidence', 0):.2f}"
		)

	for p in pivots:
		parts.append(
			f"PIVOT at {p.get('stage', '?')}: {p.get('from_entity', '?')} -> {p.get('to_entity', '?')} "
			f"({p.get('to_type', '?')}) | Reason: {p.get('reason', 'N/A')}"
		)

	if branches:
		parts.append(f"BRANCH: Explored {len(branches)} parallel entities")

	if graph_stats:
		parts.append(
			f"GRAPH STAGE: Found {graph_stats.get('hypotheses', 0)} hypotheses, "
			f"scored {graph_stats.get('scored', 0)}"
		)

	for v in validation_results:
		parts.append(
			f"VALIDATION ({v.get('tool', '?')}): {v.get('status', '?')} | "
			f"Delta={v.get('confidence_delta', 0):+.2f} | {v.get('evidence_type', '?')} | "
			f"{v.get('summary', '')}"
		)

	return "\n".join(parts) if parts else "No trace data available."


def _fallback_narrative(
	query: str,
	start_entity: str,
	checkpoint_log: list[dict[str, Any]],
	pivots: list[dict[str, Any]],
	validation_results: list[dict[str, Any]],
) -> str:
	"""Generate a template-based narrative when Claude is unavailable."""
	parts: list[str] = []
	parts.append(
		f"The investigation began with the query \"{query}\", "
		f"starting from {start_entity}."
	)

	for cp in checkpoint_log:
		decision = cp.get("decision", "continue")
		stage = cp.get("stage", "unknown")
		reason = cp.get("reason", "")
		parts.append(
			f"At the {stage} checkpoint, the pipeline decided to {decision.lower()}"
			f"{': ' + reason if reason else ''}."
		)

	for p in pivots:
		parts.append(
			f"The pipeline pivoted from {p.get('from_entity', '?')} to "
			f"{p.get('to_entity', '?')} because {p.get('reason', 'of new evidence')}."
		)

	for v in validation_results:
		parts.append(
			f"Validation via {v.get('tool', 'unknown')}: {v.get('summary', 'completed')}."
		)

	return " ".join(parts)


async def generate_discovery_narrative(
	query: str,
	start_entity: str,
	start_type: str,
	checkpoint_log: list[dict[str, Any]],
	pivots: list[dict[str, Any]],
	branches: list[Any],
	validation_results: list[dict[str, Any]],
	literature_stats: dict[str, Any] | None = None,
	graph_stats: dict[str, Any] | None = None,
) -> str:
	"""Generate a narrative of the discovery process from pipeline trace data.

	Synthesizes checkpoint decisions, pivots, branches, and validation
	results into a readable story of how the pipeline arrived at its
	hypothesis.

	Returns markdown-free narrative text (plain paragraphs).
	"""
	trace_text = _build_trace_text(
		checkpoint_log, pivots, branches,
		validation_results, literature_stats, graph_stats,
	)

	if not settings.anthropic_api_key:
		logger.warning("No API key, using template narrative")
		return _fallback_narrative(query, start_entity, checkpoint_log, pivots, validation_results)

	prompt = NARRATIVE_PROMPT.format(
		query=query,
		start_entity=start_entity,
		start_type=start_type,
		trace_text=trace_text,
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)
		return str(getattr(message.content[0], "text", "")).strip()
	except Exception:
		logger.exception("Failed to generate narrative, using fallback")
		return _fallback_narrative(query, start_entity, checkpoint_log, pivots, validation_results)
