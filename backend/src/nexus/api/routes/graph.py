from fastapi import APIRouter, Query

from nexus.graph.abc import find_abc_hypotheses

router = APIRouter()


@router.get("/graph/explore")
async def explore_graph(
	entity_name: str = Query(...),
	entity_type: str = Query(...),
	depth: int = Query(default=1, ge=1, le=5),
):
	try:
		hypotheses = await find_abc_hypotheses(
			source_name=entity_name,
			source_type=entity_type,
			max_results=depth * 10,
		)
		nodes = []
		edges = []
		seen_nodes = set()
		for h in hypotheses:
			for node_id, name, ntype in [
				(h.a_id, h.a_name, h.a_type),
				(h.b_id, h.b_name, h.b_type),
				(h.c_id, h.c_name, h.c_type),
			]:
				if node_id not in seen_nodes:
					seen_nodes.add(node_id)
					nodes.append({"id": node_id, "name": name, "type": ntype})
			edges.append({"source": h.a_id, "target": h.b_id, "relationship": h.ab_relationship})
			edges.append({"source": h.b_id, "target": h.c_id, "relationship": h.bc_relationship})
		return {"entity_name": entity_name, "entity_type": entity_type, "depth": depth, "nodes": nodes, "edges": edges}
	except RuntimeError:
		# Graph client not connected
		return {"entity_name": entity_name, "entity_type": entity_type, "depth": depth, "nodes": [], "edges": [], "error": "Graph database not connected"}
