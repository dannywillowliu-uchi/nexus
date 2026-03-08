from __future__ import annotations

import logging

from nexus.graph.client import graph_client

logger = logging.getLogger(__name__)


async def detect_deltas(
	new_triples: list[dict],
) -> list[dict]:
	"""Detect high-delta edges: new A-B connections that create novel A-B-C paths.

	Args:
		new_triples: List of dicts with keys "subject", "object", "predicate".

	Returns:
		List of high-delta edges with new_paths_count > 0.
	"""
	if not new_triples:
		return []

	high_delta: list[dict] = []

	for triple in new_triples:
		subject = triple["subject"]
		obj = triple["object"]

		# Count 2-hop paths through the new edge's nodes that exist now.
		# A path A->B->C is "novel" if B is one of our edge's nodes and
		# the A->C connection doesn't exist directly.
		query = """
			MATCH (a)-[]->(b {name: $node})-[]->(c)
			WHERE a.name <> c.name
			AND NOT EXISTS { MATCH (a)-[:LITERATURE_EDGE]->(c) }
			AND NOT EXISTS { MATCH (a)-[:LITERATURE_EDGE]-(c) }
			RETURN count(DISTINCT c) AS new_paths
		"""

		# Check paths through subject node
		result_subj = await graph_client.execute_read(query, node=subject)
		paths_through_subj = result_subj[0]["new_paths"] if result_subj else 0

		# Check paths through object node
		result_obj = await graph_client.execute_read(query, node=obj)
		paths_through_obj = result_obj[0]["new_paths"] if result_obj else 0

		total_new_paths = paths_through_subj + paths_through_obj

		if total_new_paths > 0:
			high_delta.append({
				"subject": subject,
				"object": obj,
				"predicate": triple["predicate"],
				"new_paths_count": total_new_paths,
			})

	return high_delta
