from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/graph/explore")
async def explore_graph(
	entity_name: str = Query(...),
	entity_type: str = Query(...),
	depth: int = Query(default=1, ge=1, le=5),
):
	return {
		"entity_name": entity_name,
		"entity_type": entity_type,
		"depth": depth,
		"nodes": [],
		"edges": [],
	}
