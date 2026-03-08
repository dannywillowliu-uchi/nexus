from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QuickQuery(BaseModel):
	query: str
	disease_area: str
	target_type: str


@router.post("/query")
async def quick_query(request: QuickQuery):
	return {
		"query": request.query,
		"disease_area": request.disease_area,
		"target_type": request.target_type,
		"status": "placeholder",
		"results": [],
	}
