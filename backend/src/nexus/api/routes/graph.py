from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from nexus.graph.abc import find_abc_hypotheses
from nexus.graph.client import graph_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/graph/explore")
async def explore_graph(
	entity_name: str = Query(...),
	entity_type: str = Query(...),
	depth: int = Query(default=1, ge=1, le=5),
):
	try:
		# Try APOC subgraphAll for multi-hop exploration
		try:
			records = await graph_client.execute_read(
				"""
				MATCH (start {name: $entity_name})
				WHERE $entity_type IN labels(start) OR start.type = $entity_type
				CALL apoc.path.subgraphAll(start, {maxLevel: $depth})
				YIELD nodes, relationships
				RETURN nodes, relationships
				""",
				entity_name=entity_name,
				entity_type=entity_type,
				depth=depth,
			)
			if records:
				row = records[0]
				nodes = []
				seen_ids = set()
				for n in row.get("nodes", []):
					nid = str(n.get("name", n.get("id", id(n))))
					if nid not in seen_ids:
						seen_ids.add(nid)
						labels = n.get("labels", [])
						node_type = n.get("type") or (labels[0] if labels else "Entity")
						nodes.append({"id": nid, "name": n.get("name", nid), "type": node_type})
				edges = []
				for r in row.get("relationships", []):
					edges.append({
						"source": str(r.get("start", "")),
						"target": str(r.get("end", "")),
						"type": str(r.get("type", "RELATED")),
					})
				return {"entity_name": entity_name, "entity_type": entity_type, "depth": depth, "nodes": nodes, "edges": edges}
		except Exception:
			logger.debug("APOC not available, falling back to simple query")

		# Fallback: simple MATCH pattern
		records = await graph_client.execute_read(
			"""
			MATCH (n {name: $entity_name})-[r]-(m)
			RETURN n, r, m
			LIMIT 100
			""",
			entity_name=entity_name,
		)

		nodes = []
		edges = []
		seen_ids: set[str] = set()

		for row in records:
			for key in ("n", "m"):
				node = row.get(key, {})
				nid = str(node.get("name", node.get("id", "")))
				if nid and nid not in seen_ids:
					seen_ids.add(nid)
					node_type = node.get("type", "Entity")
					nodes.append({"id": nid, "name": node.get("name", nid), "type": node_type})

			rel = row.get("r", {})
			if rel:
				src = str(row.get("n", {}).get("name", ""))
				tgt = str(row.get("m", {}).get("name", ""))
				rel_type = str(rel.get("type", rel.get("predicate", "RELATED")))
				if src and tgt:
					edges.append({"source": src, "target": tgt, "type": rel_type})

		return {"entity_name": entity_name, "entity_type": entity_type, "depth": depth, "nodes": nodes, "edges": edges}

	except Exception:
		logger.exception("Graph explore failed")
		return {"entity_name": entity_name, "entity_type": entity_type, "depth": depth, "nodes": [], "edges": []}
