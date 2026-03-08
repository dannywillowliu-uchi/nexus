"""Reasoning agent for generating hypothesis summaries and research briefs."""

from __future__ import annotations

import json
import logging

import anthropic

from nexus.agents.literature.extract import Triple
from nexus.config import settings
from nexus.db.models import ConfidenceAssessment, EvidenceItem, ResearchBrief
from nexus.graph.abc import ABCHypothesis

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000


def _parse_json(text: str) -> object:
	"""Parse JSON from a Claude response, stripping markdown fences if present."""
	cleaned = text.strip()
	if cleaned.startswith("```"):
		lines = cleaned.split("\n")
		lines = [line for line in lines[1:] if line.strip() != "```"]
		cleaned = "\n".join(lines)
	return json.loads(cleaned)


def _format_triples(triples: list[Triple], limit: int = 30) -> str:
	"""Format triples into text for prompts, limited to avoid token overflow."""
	parts: list[str] = []
	for t in triples[:limit]:
		parts.append(f"- {t.subject} ({t.subject_type}) --[{t.predicate}]--> {t.object} ({t.object_type}) [confidence: {t.confidence}]")
	return "\n".join(parts)


def _template_summary(h: ABCHypothesis) -> str:
	"""Generate a template-based fallback summary for a hypothesis."""
	return (
		f"{h.a_name} ({h.a_type}) may be connected to {h.c_name} ({h.c_type}) "
		f"through {h.b_name} ({h.b_type}). "
		f"The {h.ab_relationship} and {h.bc_relationship} relationships suggest "
		f"a potential link worth investigating."
	)


def _minimal_brief(hypothesis: ABCHypothesis) -> ResearchBrief:
	"""Generate a minimal fallback ResearchBrief when API is unavailable."""
	title = f"{hypothesis.a_name} -> {hypothesis.b_name} -> {hypothesis.c_name}"
	return ResearchBrief(
		hypothesis_title=title,
		connection_explanation=(
			f"{hypothesis.a_name} may be connected to {hypothesis.c_name} "
			f"via {hypothesis.b_name} through {hypothesis.ab_relationship} "
			f"and {hypothesis.bc_relationship} relationships."
		),
		literature_evidence=[],
		existing_knowledge_comparison="No literature analysis available without API key.",
		confidence=ConfidenceAssessment(
			graph_evidence=hypothesis.path_strength,
			graph_reasoning="Based on graph path strength.",
			literature_support=0.0,
			literature_reasoning="No API key configured for analysis.",
			biological_plausibility=0.0,
			plausibility_reasoning="No API key configured for analysis.",
			novelty=hypothesis.novelty_score,
			novelty_reasoning="Based on graph novelty score.",
		),
		suggested_validation="Manual literature review recommended.",
	)


QUICK_SUMMARY_PROMPT = """You are a biomedical research assistant. Given the following hypotheses connecting entities through a knowledge graph, provide a concise 2-3 sentence explanation of each hypothesis.

Hypotheses:
{hypotheses_text}

Supporting triples from literature:
{triples_text}

Return a JSON array where each element has:
- "hypothesis": the A->B->C path as a string
- "summary": a 2-3 sentence explanation

Return ONLY the JSON array, no other text."""


RESEARCH_BRIEF_PROMPT = """You are a biomedical research analyst. Generate a detailed research brief for the following hypothesis.

Hypothesis path: {a_name} ({a_type}) --[{ab_rel}]--> {b_name} ({b_type}) --[{bc_rel}]--> {c_name} ({c_type})

Path statistics:
- Number of connecting paths: {path_count}
- Path strength: {path_strength:.3f}

Relevant triples from literature:
{triples_text}

Paper abstracts:
{papers_text}

Return a JSON object with:
- "connection_explanation": detailed explanation of how A connects to C through B
- "literature_evidence": array of {{"paper_id": str, "title": str, "snippet": str, "confidence": float}}
- "existing_knowledge_comparison": how this compares to existing knowledge
- "confidence": {{
    "graph_evidence": float (0-1),
    "graph_reasoning": str,
    "literature_support": float (0-1),
    "literature_reasoning": str,
    "biological_plausibility": float (0-1),
    "plausibility_reasoning": str,
    "novelty": float (0-1),
    "novelty_reasoning": str
  }}
- "suggested_validation": experimental approaches to test this hypothesis

Return ONLY the JSON object, no other text."""


async def generate_quick_summaries(
	hypotheses: list[ABCHypothesis],
	triples: list[Triple],
) -> list[str]:
	"""Generate concise summaries for a batch of hypotheses.

	Uses a single Claude call with all hypotheses batched together.
	Falls back to template-based summaries if no API key is configured.

	Args:
		hypotheses: List of ABC hypotheses to summarize.
		triples: Supporting triples for context (limited to 30 in the prompt).

	Returns:
		List of summary strings, one per hypothesis.
	"""
	if not hypotheses:
		return []

	if not settings.anthropic_api_key:
		logger.warning("No Anthropic API key configured, using template summaries")
		return [_template_summary(h) for h in hypotheses]

	hypotheses_text = "\n".join(
		f"- {h.a_name} ({h.a_type}) --[{h.ab_relationship}]--> "
		f"{h.b_name} ({h.b_type}) --[{h.bc_relationship}]--> "
		f"{h.c_name} ({h.c_type})"
		for h in hypotheses
	)
	triples_text = _format_triples(triples, limit=30)

	prompt = QUICK_SUMMARY_PROMPT.format(
		hypotheses_text=hypotheses_text,
		triples_text=triples_text or "No supporting triples available.",
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)

		response_text = message.content[0].text
		parsed = _parse_json(response_text)

		summaries: list[str] = []
		for item in parsed:
			summaries.append(str(item.get("summary", "")))

		return summaries

	except Exception:
		logger.exception("Failed to generate quick summaries, using templates")
		return [_template_summary(h) for h in hypotheses]


async def generate_research_brief(
	hypothesis: ABCHypothesis,
	triples: list[Triple],
	papers: list[dict],
) -> ResearchBrief:
	"""Generate a detailed research brief for a single hypothesis.

	Uses a per-hypothesis Claude call with full context including triples
	and paper abstracts.

	Args:
		hypothesis: The ABC hypothesis to analyze.
		triples: Relevant triples from literature extraction.
		papers: List of paper dicts with at least 'paper_id', 'title', 'abstract'.

	Returns:
		A ResearchBrief with structured analysis and confidence assessment.
	"""
	if not settings.anthropic_api_key:
		logger.warning("No Anthropic API key configured, returning minimal brief")
		return _minimal_brief(hypothesis)

	triples_text = _format_triples(triples)
	papers_parts: list[str] = []
	for p in papers:
		papers_parts.append(
			f"Paper ID: {p.get('paper_id', '')}\n"
			f"Title: {p.get('title', '')}\n"
			f"Abstract: {p.get('abstract', '')}\n"
		)
	papers_text = "\n".join(papers_parts) or "No paper abstracts available."

	prompt = RESEARCH_BRIEF_PROMPT.format(
		a_name=hypothesis.a_name,
		a_type=hypothesis.a_type,
		ab_rel=hypothesis.ab_relationship,
		b_name=hypothesis.b_name,
		b_type=hypothesis.b_type,
		bc_rel=hypothesis.bc_relationship,
		c_name=hypothesis.c_name,
		c_type=hypothesis.c_type,
		path_count=hypothesis.path_count,
		path_strength=hypothesis.path_strength,
		triples_text=triples_text or "No supporting triples available.",
		papers_text=papers_text,
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)

		response_text = message.content[0].text
		data = _parse_json(response_text)

		confidence_data = data.get("confidence", {})
		confidence = ConfidenceAssessment(
			graph_evidence=float(confidence_data.get("graph_evidence", 0.0)),
			graph_reasoning=str(confidence_data.get("graph_reasoning", "")),
			literature_support=float(confidence_data.get("literature_support", 0.0)),
			literature_reasoning=str(confidence_data.get("literature_reasoning", "")),
			biological_plausibility=float(confidence_data.get("biological_plausibility", 0.0)),
			plausibility_reasoning=str(confidence_data.get("plausibility_reasoning", "")),
			novelty=float(confidence_data.get("novelty", 0.0)),
			novelty_reasoning=str(confidence_data.get("novelty_reasoning", "")),
		)

		evidence_items: list[EvidenceItem] = []
		for ev in data.get("literature_evidence", []):
			evidence_items.append(EvidenceItem(
				paper_id=str(ev.get("paper_id", "")),
				title=str(ev.get("title", "")),
				snippet=str(ev.get("snippet", "")),
				confidence=float(ev.get("confidence", 0.0)),
			))

		title = f"{hypothesis.a_name} -> {hypothesis.b_name} -> {hypothesis.c_name}"
		return ResearchBrief(
			hypothesis_title=title,
			connection_explanation=str(data.get("connection_explanation", "")),
			literature_evidence=evidence_items,
			existing_knowledge_comparison=str(data.get("existing_knowledge_comparison", "")),
			confidence=confidence,
			suggested_validation=str(data.get("suggested_validation", "")),
		)

	except Exception:
		logger.exception("Failed to generate research brief, returning minimal brief")
		return _minimal_brief(hypothesis)
