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
BRIEF_MAX_TOKENS = 4096
SUMMARY_MAX_TOKENS = 2000


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


RESEARCHER_REASONING_PROMPT = """You are a senior translational researcher reviewing a computationally-generated drug repurposing hypothesis. Think out loud as a researcher would — don't just report scores, reason through the biology.

HYPOTHESIS:
{drug_name} may have therapeutic activity against {disease_name} via {intermediary_gene}.

EVIDENCE:
- Drug->Gene link: {drug_gene_relationship} (confidence: {confidence_1:.2f})
- Gene->Disease link: {gene_disease_relationship} (confidence: {confidence_2:.2f})
- Path redundancy: {path_count} independent intermediaries
- Novel edges: {novel_edge_info}

Structure your analysis as a researcher thinking through this problem:

1. BIOLOGICAL PLAUSIBILITY
Think through the mechanism step by step. What does {intermediary_gene} actually do in the cell? What happens when {drug_name} affects it? Why would that matter for {disease_name}? Be specific about the molecular mechanism — explain the causal chain, don't just say "it's involved in the pathway."

2. STRENGTH OF EVIDENCE
What's the strongest piece of evidence supporting this? What's the weakest? Be honest about gaps. If the drug-gene link is only from metabolic enzymes (CYP450s), say that's much weaker than a direct pharmacological target. If the gene-disease association is from a GWAS study, note that correlation isn't causation.

3. WHAT A RESEARCHER WOULD DO FIRST
Describe the first experiment — not in general terms but specifically:
- What cell lines would you use? Name specific lines relevant to the disease.
- What assay would you run? MTT/MTS viability? Reporter gene? Binding assay? Why that one over alternatives?
- What concentrations of the drug? Base this on known pharmacology — what are typical plasma concentrations? What range makes sense for an in vitro experiment?
- What controls? Name a positive control drug that's known to work on this target, and a negative control cell line that doesn't express the target.
- What readout tells you it's working? Be specific about the measurement.
- How long would this take and roughly what would it cost?

4. WHY THIS MIGHT FAIL
Be intellectually honest. Give the top 3 reasons this hypothesis could be wrong. For each one, explain what would need to be true for the hypothesis to succeed despite this concern. Consider: bioavailability, selectivity, resistance mechanisms, patient subsets, concentration issues.

5. CLINICAL SIGNIFICANCE
If this IS real, what would it mean for patients? How many people have {disease_name}? What are current treatment options and their limitations? What gap would {drug_name} fill? Is there a specific patient population (e.g., treatment-resistant, specific mutation status) that would benefit most?

Write as a scientist talking to another scientist — rigorous but accessible. Use specific numbers, gene names, drug concentrations, and cell line names wherever possible. No vague hand-waving."""


SCORE_EXTRACTION_PROMPT = """Given this research brief, extract confidence scores (0.0-1.0) for each dimension.

Brief:
{narrative}

Return ONLY a JSON object:
{{"graph_evidence": float, "graph_reasoning": "one sentence", "literature_support": float, "literature_reasoning": "one sentence", "biological_plausibility": float, "plausibility_reasoning": "one sentence", "novelty": float, "novelty_reasoning": "one sentence"}}"""


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


def _build_novel_edge_info(hypothesis: ABCHypothesis, triples: list[Triple]) -> str:
	"""Summarise any novel (literature-extracted) edges relevant to this hypothesis."""
	path_entities = {hypothesis.a_name.lower(), hypothesis.b_name.lower(), hypothesis.c_name.lower()}
	novel = [
		f"{t.subject} --[{t.predicate}]--> {t.object} (conf {t.confidence})"
		for t in triples
		if t.subject.lower() in path_entities or t.object.lower() in path_entities
	]
	if novel:
		return "; ".join(novel[:5])
	return "None — all edges from curated knowledge graph"


async def generate_research_brief(
	hypothesis: ABCHypothesis,
	triples: list[Triple],
	papers: list[dict],
) -> ResearchBrief:
	"""Generate a detailed research brief using the researcher reasoning prompt.

	Calls Claude Sonnet with the RESEARCHER_REASONING_PROMPT to produce a
	full narrative analysis, then extracts structured confidence scores.

	Args:
		hypothesis: The ABC hypothesis to analyze.
		triples: Relevant triples from literature extraction.
		papers: List of paper dicts with at least 'paper_id', 'title', 'abstract'.

	Returns:
		A ResearchBrief with researcher_narrative and structured scores.
	"""
	if not settings.anthropic_api_key:
		logger.warning("No Anthropic API key configured, returning minimal brief")
		return _minimal_brief(hypothesis)

	# Build template variables from hypothesis
	novel_edge_info = _build_novel_edge_info(hypothesis, triples)

	prompt = RESEARCHER_REASONING_PROMPT.format(
		drug_name=hypothesis.a_name,
		disease_name=hypothesis.c_name,
		intermediary_gene=hypothesis.b_name,
		drug_gene_relationship=hypothesis.ab_relationship,
		confidence_1=hypothesis.path_strength,
		gene_disease_relationship=hypothesis.bc_relationship,
		confidence_2=hypothesis.path_strength,
		path_count=hypothesis.path_count,
		novel_edge_info=novel_edge_info,
	)

	# Append paper abstracts as supplementary context if available
	if papers:
		papers_ctx = "\n\nSUPPORTING LITERATURE:\n"
		for p in papers[:5]:
			papers_ctx += f"- {p.get('title', 'Untitled')} (ID: {p.get('paper_id', '')})\n  {p.get('abstract', '')[:300]}\n"
		prompt += papers_ctx

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

		# Step 1: Generate the full researcher narrative
		message = await client.messages.create(
			model=MODEL,
			max_tokens=BRIEF_MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)
		narrative = message.content[0].text

		# Step 2: Extract structured confidence scores from the narrative
		confidence = ConfidenceAssessment(
			graph_evidence=hypothesis.path_strength,
			graph_reasoning="Based on graph path strength.",
			literature_support=0.5,
			literature_reasoning="Pending score extraction.",
			biological_plausibility=0.5,
			plausibility_reasoning="Pending score extraction.",
			novelty=hypothesis.novelty_score,
			novelty_reasoning="Based on graph novelty score.",
		)
		try:
			score_msg = await client.messages.create(
				model="claude-haiku-4-5-20251001",
				max_tokens=500,
				messages=[{"role": "user", "content": SCORE_EXTRACTION_PROMPT.format(narrative=narrative[:3000])}],
			)
			score_data = _parse_json(score_msg.content[0].text)
			confidence = ConfidenceAssessment(
				graph_evidence=float(score_data.get("graph_evidence", hypothesis.path_strength)),
				graph_reasoning=str(score_data.get("graph_reasoning", "")),
				literature_support=float(score_data.get("literature_support", 0.0)),
				literature_reasoning=str(score_data.get("literature_reasoning", "")),
				biological_plausibility=float(score_data.get("biological_plausibility", 0.0)),
				plausibility_reasoning=str(score_data.get("plausibility_reasoning", "")),
				novelty=float(score_data.get("novelty", hypothesis.novelty_score)),
				novelty_reasoning=str(score_data.get("novelty_reasoning", "")),
			)
		except Exception:
			logger.debug("Score extraction failed, using defaults from narrative")

		# Step 3: Extract section content for structured fields
		sections = _extract_sections(narrative)

		title = f"{hypothesis.a_name} -> {hypothesis.b_name} -> {hypothesis.c_name}"
		return ResearchBrief(
			hypothesis_title=title,
			connection_explanation=sections.get("biological_plausibility", ""),
			literature_evidence=[],
			existing_knowledge_comparison=sections.get("strength_of_evidence", ""),
			confidence=confidence,
			suggested_validation=sections.get("what_a_researcher_would_do_first", ""),
			researcher_narrative=narrative,
		)

	except Exception:
		logger.exception("Failed to generate research brief, returning minimal brief")
		return _minimal_brief(hypothesis)


def _extract_sections(narrative: str) -> dict[str, str]:
	"""Extract named sections from the researcher narrative."""
	section_headers = [
		"BIOLOGICAL PLAUSIBILITY",
		"STRENGTH OF EVIDENCE",
		"WHAT A RESEARCHER WOULD DO FIRST",
		"WHY THIS MIGHT FAIL",
		"CLINICAL SIGNIFICANCE",
	]
	sections: dict[str, str] = {}
	lines = narrative.split("\n")
	current_key = ""
	current_lines: list[str] = []

	for line in lines:
		stripped = line.strip()
		# Check if this line is a section header (e.g., "1. BIOLOGICAL PLAUSIBILITY" or "## 1. BIOLOGICAL PLAUSIBILITY")
		matched = False
		for header in section_headers:
			if header in stripped.upper():
				if current_key:
					sections[current_key] = "\n".join(current_lines).strip()
				current_key = header.lower().replace(" ", "_")
				current_lines = []
				matched = True
				break
		if not matched and current_key:
			current_lines.append(line)

	if current_key:
		sections[current_key] = "\n".join(current_lines).strip()

	return sections
