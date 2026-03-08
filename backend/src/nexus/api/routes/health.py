from fastapi import APIRouter

from nexus.graph.client import graph_client

router = APIRouter()


@router.get("/health")
async def health_check():
	"""Health check with Neo4j connectivity info."""
	try:
		nodes = await graph_client.node_count()
		edges = await graph_client.edge_count()
		graph_status = {"connected": True, "nodes": nodes, "edges": edges}
	except Exception as exc:
		graph_status = {"connected": False, "error": str(exc)}

	return {
		"status": "ok",
		"service": "nexus",
		"graph": graph_status,
	}
