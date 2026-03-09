from fastapi import APIRouter

from nexus.api.deps import event_store

router = APIRouter()


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str):
	# Search events for this hypothesis (by Event.hypothesis_id field)
	events = event_store.get_by_hypothesis(hypothesis_id)
	if events:
		# Return the last (most enriched) event
		latest = events[-1]
		return {
			"hypothesis_id": hypothesis_id,
			"status": "found",
			**(latest.output_data or {}),
		}

	# Fallback: scan output_data for matching hypothesis_id
	# Return the LAST match (most enriched version)
	last_match = None
	for e in event_store.events:
		if e.output_data and e.output_data.get("hypothesis_id") == hypothesis_id:
			last_match = e
	if last_match:
		return {
			"hypothesis_id": hypothesis_id,
			"status": "found",
			**(last_match.output_data or {}),
		}

	return {
		"hypothesis_id": hypothesis_id,
		"status": "not_found",
	}
