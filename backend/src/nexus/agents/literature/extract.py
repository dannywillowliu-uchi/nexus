from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from nexus.agents.literature.search import Paper
from nexus.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Triple:
	subject: str
	subject_type: str
	predicate: str
	object: str
	object_type: str
	confidence: float
	source_paper_id: str = ""


EXTRACTION_PROMPT = """Extract biological entity-relationship triples from these paper abstracts.

Entity types: Disease, Gene, Drug, Anatomy, BiologicalProcess, CellularComponent, MolecularFunction, Pathway, Phenotype, Exposure

Predicate vocabulary: treats, binds, upregulates, downregulates, inhibits, activates, associated_with, expressed_in, participates_in, causes, negated

For each triple, provide:
- subject: entity name (use standard biomedical nomenclature, e.g. HGNC symbols for genes)
- subject_type: one of the entity types above
- predicate: one of the predicates above
- object: entity name
- object_type: one of the entity types above
- confidence: 0.0-1.0 based on how explicitly the paper states this relationship
- source_paper_id: the paper_id this triple was extracted from

Papers:
{papers_text}

Return a JSON array of triples. Example:
[
  {{
    "subject": "BRCA1",
    "subject_type": "Gene",
    "predicate": "associated_with",
    "object": "breast cancer",
    "object_type": "Disease",
    "confidence": 0.95,
    "source_paper_id": "12345"
  }}
]

Return ONLY the JSON array, no other text."""


def _format_papers(papers: list[Paper]) -> str:
	"""Format papers into text for the extraction prompt."""
	parts: list[str] = []
	for p in papers:
		parts.append(f"Paper ID: {p.paper_id}\nTitle: {p.title}\nAbstract: {p.abstract}\n")
	return "\n".join(parts)


def _parse_triples_json(text: str) -> list[dict[str, object]]:
	"""Parse JSON from Claude response, handling markdown fences."""
	cleaned = text.strip()
	if cleaned.startswith("```"):
		lines = cleaned.split("\n")
		# Remove first line (```json or ```) and last line (```)
		lines = [line for line in lines[1:] if line.strip() != "```"]
		cleaned = "\n".join(lines)
	return json.loads(cleaned)


async def extract_triples(papers: list[Paper]) -> list[Triple]:
	"""Use Claude to extract entity-relationship triples from paper abstracts."""
	if not settings.anthropic_api_key:
		logger.warning("No Anthropic API key configured, skipping triple extraction")
		return []

	if not papers:
		return []

	papers_text = _format_papers(papers)
	prompt = EXTRACTION_PROMPT.format(papers_text=papers_text)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model="claude-haiku-4-5-20251001",
			max_tokens=4096,
			messages=[{"role": "user", "content": prompt}],
		)

		response_text = message.content[0].text
		raw_triples = _parse_triples_json(response_text)

		triples: list[Triple] = []
		for t in raw_triples:
			triples.append(
				Triple(
					subject=str(t.get("subject", "")),
					subject_type=str(t.get("subject_type", "")),
					predicate=str(t.get("predicate", "")),
					object=str(t.get("object", "")),
					object_type=str(t.get("object_type", "")),
					confidence=float(t.get("confidence", 0.0)),
					source_paper_id=str(t.get("source_paper_id", "")),
				)
			)

		return triples

	except Exception:
		logger.exception("Failed to extract triples")
		return []
