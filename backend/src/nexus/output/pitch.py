"""Research pitch report generation."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from nexus.config import settings
from nexus.output.models import ResearchOutput, VisualAsset

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000

PITCH_PROMPT = """You are a biomedical research strategist writing a research pitch for a novel hypothesis discovered by an AI-driven pipeline. Write a compelling, scientifically rigorous pitch.

Hypothesis: {title}
Description: {description}
Hypothesis type: {hypothesis_type}
Disease area: {disease_area}

ABC Path: {a_name} ({a_type}) --[{ab_rel}]--> {b_name} ({b_type}) --[{bc_rel}]--> {c_name} ({c_type})

Scores:
- Overall: {overall:.2f}
- Novelty: {novelty:.2f}
- Evidence: {evidence:.2f}
- Path strength: {path_strength:.2f}

Research brief:
{brief_text}

Validation results:
{validation_text}

Discovery narrative:
{narrative}

Write the pitch in markdown with these exact sections:

## Executive Summary
One paragraph: what was discovered and why it matters clinically or scientifically.

## Methodology Rationale
Why Swanson ABC literature-based discovery was the right approach for this query. Why the specific validation tools were chosen based on the hypothesis type ({hypothesis_type}). How the adaptive pipeline's checkpoint decisions shaped the investigation.

## Discovery Process
{narrative}

## Evidence Chain
Walk through: literature support -> graph path analysis -> computational validation. Include specific confidence scores and what they mean. Cite papers where available.

## Clinical/Research Significance
What this means for the field. How it compares to existing knowledge. What's novel about this connection.

## Proposed Next Steps
Concrete experimental validation plan. Which assays, what controls, expected outcomes.

Return ONLY the markdown content starting with ## Executive Summary."""


def _format_brief(brief: dict[str, Any] | None) -> str:
	"""Format a research brief dict into text for the prompt."""
	if not brief:
		return "No detailed research brief available."

	parts: list[str] = []
	parts.append(f"Connection: {brief.get('connection_explanation', 'N/A')}")
	parts.append(f"Existing knowledge: {brief.get('existing_knowledge_comparison', 'N/A')}")
	parts.append(f"Suggested validation: {brief.get('suggested_validation', 'N/A')}")

	confidence = brief.get("confidence", {})
	if confidence:
		parts.append(f"Graph evidence: {confidence.get('graph_evidence', 0):.2f} - {confidence.get('graph_reasoning', '')}")
		parts.append(f"Literature support: {confidence.get('literature_support', 0):.2f} - {confidence.get('literature_reasoning', '')}")
		parts.append(f"Biological plausibility: {confidence.get('biological_plausibility', 0):.2f} - {confidence.get('plausibility_reasoning', '')}")
		parts.append(f"Novelty: {confidence.get('novelty', 0):.2f} - {confidence.get('novelty_reasoning', '')}")

	evidence = brief.get("literature_evidence", [])
	if evidence:
		parts.append("Literature evidence:")
		for e in evidence:
			parts.append(f"  - [{e.get('paper_id', '')}] {e.get('title', '')}: {e.get('snippet', '')} (confidence: {e.get('confidence', 0):.2f})")

	return "\n".join(parts)


def _format_validations(validations: list[dict[str, Any]]) -> str:
	"""Format validation results into text."""
	if not validations:
		return "No computational validation results available."
	parts: list[str] = []
	for v in validations:
		parts.append(
			f"- {v.get('tool', 'unknown')}: {v.get('status', '?')} | "
			f"confidence delta: {v.get('confidence_delta', 0):+.2f} | "
			f"{v.get('evidence_type', '?')} | {v.get('summary', '')}"
		)
	return "\n".join(parts)


def _fallback_pitch(hypothesis: dict[str, Any], narrative: str) -> str:
	"""Generate a template pitch when Claude is unavailable."""
	abc = hypothesis.get("abc_path", {})
	a = abc.get("a", {})
	b = abc.get("b", {})
	c = abc.get("c", {})
	brief = hypothesis.get("research_brief", {})

	return f"""## Executive Summary

{hypothesis.get("description", "")} This connection was discovered through Swanson ABC traversal of a biomedical knowledge graph, scoring {hypothesis.get("overall_score", 0):.2f} overall with a novelty score of {hypothesis.get("novelty_score", 0):.2f}.

## Methodology Rationale

The Swanson ABC method was chosen because it identifies implicit connections in the biomedical literature — relationships that exist through intermediary entities but have not been directly studied. This hypothesis ({hypothesis.get("hypothesis_type", "connection")}) was identified by traversing from {a.get("name", "A")} through {b.get("name", "B")} to {c.get("name", "C")}.

## Discovery Process

{narrative}

## Evidence Chain

- Graph path strength: {hypothesis.get("path_strength", 0):.2f}
- Literature evidence score: {hypothesis.get("evidence_score", 0):.2f}
- Novelty score: {hypothesis.get("novelty_score", 0):.2f}
{brief.get("connection_explanation", "") if brief else ""}

## Clinical/Research Significance

{brief.get("existing_knowledge_comparison", "Further analysis needed to assess clinical significance.") if brief else "Further analysis needed."}

## Proposed Next Steps

{brief.get("suggested_validation", "Manual literature review and experimental validation recommended.") if brief else "Manual literature review recommended."}
"""


async def generate_research_pitch(
	hypothesis: dict[str, Any],
	narrative: str,
	validation_results: list[dict[str, Any]] | None = None,
) -> str:
	"""Generate a full research pitch report for a hypothesis.

	Combines the hypothesis data, research brief, validation results,
	and discovery narrative into a structured markdown pitch document.
	"""
	if not settings.anthropic_api_key:
		logger.warning("No API key, using template pitch")
		return _fallback_pitch(hypothesis, narrative)

	abc = hypothesis.get("abc_path", {})
	a = abc.get("a", {})
	b = abc.get("b", {})
	c = abc.get("c", {})

	# Extract relationship labels from description
	desc = hypothesis.get("description", "")
	ab_rel = "relates_to"
	bc_rel = "relates_to"
	if "(" in desc and "/" in desc:
		rel_part = desc.split("(")[-1].split(")")[0]
		rels = rel_part.split("/")
		if len(rels) == 2:
			ab_rel = rels[0].strip()
			bc_rel = rels[1].strip()

	prompt = PITCH_PROMPT.format(
		title=hypothesis.get("title", ""),
		description=desc,
		hypothesis_type=hypothesis.get("hypothesis_type", "connection"),
		disease_area=hypothesis.get("disease_area", ""),
		a_name=a.get("name", ""),
		a_type=a.get("type", ""),
		ab_rel=ab_rel,
		b_name=b.get("name", ""),
		b_type=b.get("type", ""),
		bc_rel=bc_rel,
		c_name=c.get("name", ""),
		c_type=c.get("type", ""),
		overall=hypothesis.get("overall_score", 0),
		novelty=hypothesis.get("novelty_score", 0),
		evidence=hypothesis.get("evidence_score", 0),
		path_strength=hypothesis.get("path_strength", 0),
		brief_text=_format_brief(hypothesis.get("research_brief")),
		validation_text=_format_validations(validation_results or []),
		narrative=narrative,
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)
		pitch = str(getattr(message.content[0], "text", "")).strip()
		# Prepend the hypothesis title as top-level heading
		return f"# {hypothesis.get('title', 'Research Pitch')}\n\n{pitch}"
	except Exception:
		logger.exception("Failed to generate pitch, using fallback")
		return _fallback_pitch(hypothesis, narrative)


async def generate_full_output(
	hypothesis: dict[str, Any],
	pipeline_query: str,
	pipeline_start_entity: str,
	pipeline_start_type: str,
	checkpoint_log: list[dict[str, Any]],
	pivots: list[dict[str, Any]],
	branches: list[Any],
	validation_results: list[dict[str, Any]],
	literature_stats: dict[str, Any] | None = None,
	graph_stats: dict[str, Any] | None = None,
) -> ResearchOutput:
	"""Generate complete research output for a single hypothesis.

	Orchestrates narrative generation, visual rendering, and pitch
	assembly into a single ResearchOutput object.
	"""
	from nexus.output.narrative import generate_discovery_narrative
	from nexus.output.renderer import render_moa_svg, render_pathway_svg

	# Generate narrative
	narrative = await generate_discovery_narrative(
		query=pipeline_query,
		start_entity=pipeline_start_entity,
		start_type=pipeline_start_type,
		checkpoint_log=checkpoint_log,
		pivots=pivots,
		branches=branches,
		validation_results=validation_results,
		literature_stats=literature_stats,
		graph_stats=graph_stats,
	)

	# Generate visuals
	visuals: list[VisualAsset] = []

	pathway_svg = await render_pathway_svg(hypothesis)
	visuals.append(pathway_svg)

	moa_svg = await render_moa_svg(hypothesis)
	if moa_svg:
		visuals.append(moa_svg)

	# Generate pitch
	pitch = await generate_research_pitch(
		hypothesis=hypothesis,
		narrative=narrative,
		validation_results=validation_results,
	)

	return ResearchOutput(
		hypothesis_title=hypothesis.get("title", ""),
		visuals=visuals,
		discovery_narrative=narrative,
		pitch_markdown=pitch,
	)
