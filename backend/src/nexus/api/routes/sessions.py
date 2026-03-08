from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from nexus.api.deps import event_store
from nexus.db.models import SessionRequest
from nexus.harness.models import Event
from nexus.pipeline.orchestrator import PipelineResult, run_pipeline

router = APIRouter()

# Track active background pipeline tasks
_active_tasks: dict[str, asyncio.Task] = {}

# Cache pipeline results keyed by session_id
_session_results: dict[str, dict] = {}

# Cache full PipelineResult objects for research output generation
_pipeline_results: dict[str, PipelineResult] = {}


@router.post("/sessions")
async def create_session(request: SessionRequest):
	session_id = str(uuid.uuid4())

	async def on_event(event_type: str, data: dict) -> None:
		event = Event(
			event_id=str(uuid.uuid4()),
			session_id=session_id,
			event_type=event_type,
			output_data=data,
		)
		event_store.add(event)
		if event_type == "pipeline_complete":
			_session_results[session_id] = data

	async def _run_and_store() -> PipelineResult:
		result = await run_pipeline(
			query=request.query,
			start_entity=request.start_entity,
			start_type=request.start_type,
			target_types=request.target_types,
			max_hypotheses=request.max_hypotheses,
			max_pivots=request.max_pivots,
			on_event=on_event,
		)
		_pipeline_results[session_id] = result
		return result

	task = asyncio.create_task(_run_and_store())
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
					if event.event_type == "pipeline_complete":
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

	# Check if pipeline is complete
	complete_events = [e for e in events if e.event_type == "pipeline_complete"]
	if not complete_events:
		task = _active_tasks.get(session_id)
		status = "running" if task and not task.done() else "unknown"
		return {"session_id": session_id, "status": status, "hypotheses": [], "events_count": len(events)}

	# Extract hypothesis data from events
	hypothesis_events = [e for e in events if e.event_type == "hypothesis_scored"]
	hypotheses = [e.output_data for e in hypothesis_events if e.output_data]

	return {
		"session_id": session_id,
		"status": "completed",
		"hypotheses": hypotheses,
		"events_count": len(events),
	}


@router.get("/sessions/{session_id}/research-output")
async def get_research_output(session_id: str):
	"""Generate full research output for the top hypothesis in a completed session."""
	from nexus.output.pitch import generate_full_output

	# Check if session is still running
	task = _active_tasks.get(session_id)
	if task and not task.done():
		return JSONResponse(status_code=202, content={"detail": "Session still in progress"})

	# Look up completed pipeline result
	result = _pipeline_results.get(session_id)
	if result is None:
		return JSONResponse(status_code=404, content={"detail": "Session not found"})

	if not result.scored_hypotheses:
		return JSONResponse(status_code=404, content={"detail": "No hypotheses found in session"})

	top_hypothesis = result.scored_hypotheses[0]

	# Build literature/graph stats from the pipeline result
	literature_stats = None
	if result.literature_result:
		literature_stats = {
			"papers": len(result.literature_result.papers),
			"triples": len(result.literature_result.triples),
		}

	output = await generate_full_output(
		hypothesis=top_hypothesis,
		pipeline_query=result.query,
		pipeline_start_entity=result.start_entity,
		pipeline_start_type=result.start_type,
		checkpoint_log=result.checkpoint_log,
		pivots=result.pivots,
		branches=result.branches,
		validation_results=result.validation_results,
		literature_stats=literature_stats,
	)

	return {
		"hypothesis_title": output.hypothesis_title,
		"visuals": [dataclasses.asdict(v) for v in output.visuals],
		"discovery_narrative": output.discovery_narrative,
		"pitch_markdown": output.pitch_markdown,
	}
