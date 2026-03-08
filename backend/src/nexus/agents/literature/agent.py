from __future__ import annotations

import logging
from dataclasses import dataclass, field

from nexus.agents.literature.extract import Triple, extract_triples
from nexus.agents.literature.search import Paper, search_papers
from nexus.tracing.tracer import get_tracer

logger = logging.getLogger(__name__)


@dataclass
class LiteratureResult:
	papers: list[Paper] = field(default_factory=list)
	triples: list[Triple] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)


async def run_literature_agent(query: str, max_papers: int = 10) -> LiteratureResult:
	"""Run the full literature agent pipeline: search papers then extract triples."""
	result = LiteratureResult()
	tracer = get_tracer()

	try:
		if tracer:
			with tracer.span("search_papers", input_data={"query": query, "max_results": max_papers}) as s:
				result.papers = await search_papers(query, max_results=max_papers)
				s.set_output({"papers_found": len(result.papers), "titles": [p.title[:60] for p in result.papers[:5]]})
		else:
			result.papers = await search_papers(query, max_results=max_papers)
	except Exception as exc:
		result.errors.append(f"Paper search failed: {exc}")
		return result

	try:
		if tracer:
			with tracer.span("extract_triples", input_data={"papers_count": len(result.papers)}) as s:
				result.triples = await extract_triples(result.papers)
				s.set_output({
					"triples_extracted": len(result.triples),
					"sample": [f"{t.subject} --{t.predicate}--> {t.object}" for t in result.triples[:5]],
				})
		else:
			result.triples = await extract_triples(result.papers)
	except Exception as exc:
		result.errors.append(f"Triple extraction failed: {exc}")

	return result
