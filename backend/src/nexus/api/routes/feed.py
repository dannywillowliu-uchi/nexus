from fastapi import APIRouter, Query

from nexus.api.deps import event_store

router = APIRouter()


@router.get("/feed")
async def get_feed(
	disease_area: str | None = None,
	limit: int = Query(default=20, ge=1, le=100),
	offset: int = Query(default=0, ge=0),
):
	# Pull hypothesis_scored events as feed entries
	all_events = event_store.events
	scored = [e for e in all_events if e.event_type == "hypothesis_scored" and e.output_data]

	if disease_area:
		scored = [e for e in scored if e.output_data and e.output_data.get("disease_area", "").lower() == disease_area.lower()]

	paginated = scored[offset:offset + limit]
	entries = []
	for e in paginated:
		data = e.output_data or {}
		entries.append({
			"id": e.event_id,
			"session_id": e.session_id,
			"title": data.get("title", ""),
			"disease_area": data.get("disease_area", ""),
			"score": data.get("overall_score", 0),
			"timestamp": e.timestamp,
		})

	return {
		"disease_area": disease_area,
		"limit": limit,
		"offset": offset,
		"total": len(scored),
		"entries": entries,
	}
