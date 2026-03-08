from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nexus.agents.literature.extract import Triple, extract_triples
from nexus.agents.literature.search import Paper, search_papers

logger = logging.getLogger(__name__)


@dataclass
class LiteratureResult:
	papers: list[Paper] = field(default_factory=list)
	triples: list[Triple] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)


async def run_literature_agent(query: str, max_papers: int = 10) -> LiteratureResult:
	"""Run the full literature agent pipeline: search papers then extract triples."""
	result = LiteratureResult()

	try:
		result.papers = await search_papers(query, max_results=max_papers)
	except Exception as exc:
		result.errors.append(f"Paper search failed: {exc}")
		return result

	try:
		result.triples = await extract_triples(result.papers)
	except Exception as exc:
		result.errors.append(f"Triple extraction failed: {exc}")

	return result
