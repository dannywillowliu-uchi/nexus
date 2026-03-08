from fastapi import APIRouter
from pydantic import BaseModel

from nexus.agents.literature.search import search_papers

router = APIRouter()


class QuickQuery(BaseModel):
	query: str
	disease_area: str
	target_type: str


@router.post("/query")
async def quick_query(request: QuickQuery):
	try:
		papers = await search_papers(f"{request.query} {request.disease_area}", max_results=5)
		return {
			"query": request.query,
			"disease_area": request.disease_area,
			"target_type": request.target_type,
			"status": "success",
			"results": [{"paper_id": p.paper_id, "title": p.title, "abstract": p.abstract[:200]} for p in papers],
		}
	except Exception as exc:
		return {
			"query": request.query,
			"disease_area": request.disease_area,
			"target_type": request.target_type,
			"status": "error",
			"results": [],
			"error": str(exc),
		}
