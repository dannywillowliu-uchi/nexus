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

For each triple, identify:
- subject: the source entity (e.g., gene, protein, disease, drug)
- subject_type: the type of the subject (e.g., Gene, Protein, Disease, Drug, Pathway)
- predicate: the relationship (e.g., "inhibits", "causes", "treats", "upregulates")
- object: the target entity
- object_type: the type of the object
- confidence: your confidence in the extraction (0.0 to 1.0)
- source_paper_id: the paper_id this triple was extracted from

Papers:
{papers_text}

Return a JSON array of triples. Example:
[
  {{
    "subject": "BRCA1",
    "subject_type": "Gene",
    "predicate": "associated_with",
    "object": "Breast Cancer",
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
			model="claude-sonnet-4-20250514",
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
