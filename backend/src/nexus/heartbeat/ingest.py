from __future__ import annotations

import logging
from datetime import datetime, timedelta

from nexus.agents.literature.extract import Triple, extract_triples
from nexus.agents.literature.search import search_pubmed
from nexus.graph.client import graph_client

logger = logging.getLogger(__name__)


async def _merge_triples_to_graph(triples: list[Triple]) -> int:
	"""Merge extracted triples into Neo4j as LITERATURE_EDGE edges."""
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


async def ingest_recent_papers(
	query: str,
	days: int = 7,
	max_papers: int = 20,
) -> dict:
	"""Ingest recent papers from PubMed, extract triples, and merge into graph.

	Returns {"papers_found": int, "triples_extracted": int, "edges_merged": int}
	"""
	min_date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
	dated_query = f'{query} AND "{min_date}"[PDAT] : "3000"[PDAT]'

	papers = await search_pubmed(dated_query, max_results=max_papers)
	if not papers:
		return {"papers_found": 0, "triples_extracted": 0, "edges_merged": 0, "triples": []}

	triples = await extract_triples(papers)
	edges_merged = 0
	if triples:
		edges_merged = await _merge_triples_to_graph(triples)

	return {
		"papers_found": len(papers),
		"triples_extracted": len(triples),
		"edges_merged": edges_merged,
		"triples": [
			{"subject": t.subject, "object": t.object, "predicate": t.predicate}
			for t in triples
		],
	}
