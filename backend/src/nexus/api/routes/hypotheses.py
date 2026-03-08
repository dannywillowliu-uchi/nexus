from fastapi import APIRouter

from nexus.api.deps import event_store

router = APIRouter()


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str):
	# Search events for this hypothesis
	events = event_store.get_by_hypothesis(hypothesis_id)
	if events:
		latest = events[-1]
		return {
			"hypothesis_id": hypothesis_id,
			"status": "found",
			**(latest.output_data or {}),
		}

	# Also search scored events by ID in output_data
	all_events = event_store.events
	for e in all_events:
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
