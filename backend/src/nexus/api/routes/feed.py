from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/feed")
async def get_feed(
	disease_area: str | None = None,
	limit: int = Query(default=20, ge=1, le=100),
	offset: int = Query(default=0, ge=0),
):
	return {
		"disease_area": disease_area,
		"limit": limit,
		"offset": offset,
		"entries": [],
	}
