"""Demo replay endpoint -- streams pre-scripted event traces via SSE."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.api.deps import event_store
from nexus.demo.traces import get_demo_trace
from nexus.harness.models import Event

router = APIRouter()


class DemoRequest(BaseModel):
	demo_id: int = Field(ge=1, le=3)
	speed: float = Field(default=1.0, gt=0)


@router.post("/demo/start")
async def start_demo(request: DemoRequest):
	session_id = f"demo-{request.demo_id}-{uuid.uuid4().hex[:8]}"
	trace = get_demo_trace(request.demo_id)

	async def replay():
		for event_data, delay in trace:
			await asyncio.sleep(delay / request.speed)
			event = Event(
				event_id=str(uuid.uuid4()),
				session_id=session_id,
				event_type=event_data["type"],
				hypothesis_id=event_data.get("hypothesis_id"),
				output_data=event_data,
			)
			event_store.add(event)

	asyncio.create_task(replay())
	return {"session_id": session_id, "demo_id": request.demo_id}
