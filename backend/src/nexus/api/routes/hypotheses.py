from fastapi import APIRouter

router = APIRouter()


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str):
	return {
		"hypothesis_id": hypothesis_id,
		"status": "placeholder",
		"title": "",
		"description": "",
		"scores": {},
	}
