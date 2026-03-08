from __future__ import annotations

import json
import logging
import re
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


EXTRACTION_PROMPT = """Extract biomedical entity relationships from these paper abstracts.

Return ONLY a JSON array of objects. Each object has:
- "subject": entity name (use HGNC gene symbols like GRM1, TNF, BRAF, PDE5A, HDAC2, ADRB2 — NOT full names)
- "subject_type": one of [Disease, Gene, Drug, Anatomy, BiologicalProcess, CellularComponent, MolecularFunction, Pathway, Phenotype, Exposure]
- "predicate": one of [treats, binds, upregulates, downregulates, inhibits, activates, associated_with, expressed_in, participates_in, causes, negated]
- "object": entity name (use gene symbols and standard drug names)
- "object_type": one of the entity types above
- "confidence": 0.0-1.0 based on how explicitly stated
- "source_paper_id": the paper_id

CRITICAL RULES:
- Use gene symbols: GRM1 not "metabotropic glutamate receptor 1", TNF not "tumor necrosis factor alpha"
- Use standard drug names: Riluzole not "Rilutek", Thalidomide not "Thalomid"
- If text says "did NOT", "no effect", "failed to" → predicate = "negated"
- Keep the array short — max 5 triples per paper, focus on drug-gene and gene-disease relationships

Return ONLY the JSON array. No markdown, no explanation, no backticks.

Papers:
{papers_text}"""


def _format_papers(papers: list[Paper]) -> str:
	"""Format papers into text for the extraction prompt."""
	parts: list[str] = []
	for p in papers:
		abstract = (p.abstract or "")[:500]  # Truncate long abstracts
		parts.append(f"Paper ID: {p.paper_id}\nTitle: {p.title}\nAbstract: {abstract}\n")
	return "\n".join(parts)


def _parse_triples_json(text: str) -> list[dict[str, object]]:
	"""Robust JSON parsing that handles truncation and formatting issues."""
	cleaned = text.strip()

	# Strip markdown code blocks if present
	if cleaned.startswith("```json"):
		cleaned = cleaned[7:]
	elif cleaned.startswith("```"):
		cleaned = cleaned[3:]
	if cleaned.endswith("```"):
		cleaned = cleaned[:-3]
	cleaned = cleaned.strip()

	# Try direct parse first
	try:
		result = json.loads(cleaned)
		return result if isinstance(result, list) else [result]
	except json.JSONDecodeError:
		pass

	# Find the JSON array start
	start = cleaned.find("[")
	if start == -1:
		return []

	substring = cleaned[start:]

	# Try parsing from [ to end
	try:
		result = json.loads(substring)
		return result if isinstance(result, list) else [result]
	except json.JSONDecodeError:
		pass

	# Handle truncated JSON — find the last complete object "},\n" or "}\n"
	last_complete = substring.rfind("},")
	if last_complete > 0:
		try:
			fixed = substring[: last_complete + 1] + "]"
			result = json.loads(fixed)
			if isinstance(result, list):
				logger.info("Recovered %d triples from truncated JSON", len(result))
				return result
		except json.JSONDecodeError:
			pass

	# Try finding last complete object with just "}"
	last_brace = substring.rfind("}")
	if last_brace > 0:
		try:
			fixed = substring[: last_brace + 1] + "]"
			result = json.loads(fixed)
			if isinstance(result, list):
				logger.info("Recovered %d triples from truncated JSON (brace)", len(result))
				return result
		except json.JSONDecodeError:
			pass

	# Last resort: extract individual objects with regex
	objects = re.findall(r"\{[^{}]+\}", text)
	results = []
	for obj_str in objects:
		try:
			obj = json.loads(obj_str)
			if "subject" in obj and "predicate" in obj and "object" in obj:
				results.append(obj)
		except json.JSONDecodeError:
			continue

	if results:
		logger.info("Recovered %d triples via regex extraction", len(results))
	return results


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
