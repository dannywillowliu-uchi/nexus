from fastapi import APIRouter

from nexus.api.deps import event_store

router = APIRouter()


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str):
	# Find the last hypothesis_scored event with this ID (most enriched version)
	last_scored = None
	for e in event_store.events:
		if e.output_data and e.output_data.get("hypothesis_id") == hypothesis_id:
			if e.event_type == "hypothesis_scored":
				last_scored = e

	if last_scored:
		return {
			"hypothesis_id": hypothesis_id,
			"status": "found",
			**(last_scored.output_data or {}),
		}

	# Fallback: any event with this hypothesis_id in output_data
	for e in reversed(event_store.events):
		if e.output_data and e.output_data.get("hypothesis_id") == hypothesis_id:
			return {
				"hypothesis_id": hypothesis_id,
				"status": "found",
				**e.output_data,
			}

	return {
		"hypothesis_id": hypothesis_id,
		"status": "not_found",
	}
