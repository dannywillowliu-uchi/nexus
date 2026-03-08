from fastapi import APIRouter
from pydantic import BaseModel

from nexus.graph.abc import find_abc_hypotheses, find_drug_repurposing_candidates
from nexus.pipeline.orchestrator import score_hypothesis

router = APIRouter()


class QuickQuery(BaseModel):
	source_name: str
	source_type: str = "Drug"
	target_type: str = "Disease"
	max_results: int = 20


@router.post("/query")
async def quick_query(request: QuickQuery):
	"""Run ABC traversal and return scored hypotheses."""
	hypotheses = await find_abc_hypotheses(
		source_name=request.source_name,
		source_type=request.source_type,
		target_type=request.target_type,
		max_results=request.max_results,
	)

	scored = [score_hypothesis(h, []) for h in hypotheses]
	scored.sort(key=lambda h: h.get("overall_score", 0), reverse=True)

	return {
		"source": request.source_name,
		"source_type": request.source_type,
		"target_type": request.target_type,
		"count": len(scored),
		"hypotheses": scored,
	}
