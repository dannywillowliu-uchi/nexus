from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from nexus.api.deps import event_store
from nexus.db.models import SessionRequest
from nexus.harness.models import Event
from nexus.harness.runner import run_research_session

router = APIRouter()

# Track active background pipeline tasks
_active_tasks: dict[str, asyncio.Task] = {}

# Cache pipeline results keyed by session_id
_session_results: dict[str, dict] = {}


@router.post("/sessions")
async def create_session(request: SessionRequest):
	session_id = str(uuid.uuid4())

	async def _wrap(sid: str, req: SessionRequest) -> None:
		result = await run_research_session(sid, req, event_store)
		_session_results[sid] = result

	task = asyncio.create_task(_wrap(session_id, request))
	_active_tasks[session_id] = task

	return {"session_id": session_id, "status": "created"}


@router.get("/sessions/{session_id}/stream")
async def stream_events(session_id: str):
	queue: asyncio.Queue[Event] = asyncio.Queue()

	def callback(event: Event) -> None:
		if event.session_id == session_id:
			queue.put_nowait(event)

	event_store.register_callback(callback)

	async def event_generator():
		try:
			while True:
				try:
					event = await asyncio.wait_for(queue.get(), timeout=30.0)
					data = {
						"event_id": event.event_id,
						"event_type": event.event_type,
						"data": event.output_data,
					}
					yield f"data: {json.dumps(data)}\n\n"
					if event.event_type in ("pipeline_complete", "session_completed"):
						break
				except asyncio.TimeoutError:
					yield "data: {\"event_type\": \"keepalive\"}\n\n"
		finally:
			if callback in event_store.callbacks:
				event_store.callbacks.remove(callback)

	return StreamingResponse(
		event_generator(),
		media_type="text/event-stream",
	)


@router.get("/sessions/{session_id}/events")
async def get_session_events(session_id: str):
	events = event_store.get_by_session(session_id)
	return [
		{
			"event_id": e.event_id,
			"event_type": e.event_type,
			"data": e.output_data,
		}
		for e in events
	]


@router.get("/sessions/{session_id}/report")
async def get_session_report(session_id: str):
	events = event_store.get_by_session(session_id)
	if not events:
		return {"session_id": session_id, "status": "not_found", "hypotheses": []}

	# Derive status from events + task state
	event_types = [e.event_type for e in events]
	if "session_completed" in event_types or "pipeline_complete" in event_types:
		status = "completed"
	else:
		task = _active_tasks.get(session_id)
		status = "running" if task and not task.done() else "unknown"

	# Try cached result first (has full hypothesis data)
	cached = _session_results.get(session_id)
	if cached:
		return {
			"session_id": session_id,
			"status": "completed",
			"hypotheses": cached.get("hypotheses", []),
			"events_count": len(events),
		}

	# Fallback: extract from events
	hypothesis_events = [e for e in events if e.event_type == "hypothesis_scored"]
	hypotheses = [e.output_data for e in hypothesis_events if e.output_data]

	# Count pivots
	pivot_count = sum(1 for e in events if e.event_type == "pivot")

	# Build timeline
	timeline = [
		{
			"event_id": e.event_id,
			"event_type": e.event_type,
			"data": e.output_data,
			"timestamp": e.timestamp,
		}
		for e in events
	]

	return {
		"session_id": session_id,
		"status": status,
		"hypotheses": hypotheses,
		"hypothesis_count": len(hypotheses),
		"pivot_count": pivot_count,
		"events_count": len(events),
		"timeline": timeline,
	}
