from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from nexus.agents.literature.search import search_papers
from nexus.api.deps import event_store
from nexus.db.models import SessionRequest
from nexus.harness.runner import run_research_session

router = APIRouter()


class QuickQuery(BaseModel):
	source_name: str
	source_type: str = "Drug"
	target_type: str = "Disease"
	max_results: int = 20


class LiteratureQuery(BaseModel):
	query: str
	disease_area: str = ""
	max_results: int = 5


@router.post("/query")
async def quick_query(request: QuickQuery):
	"""Run full research session for a quick query."""
	session_id = str(uuid.uuid4())

	session_request = SessionRequest(
		query=f"{request.source_name} {request.target_type}",
		disease_area=request.target_type if request.target_type == "Disease" else "",
		start_entity=request.source_name,
		start_type=request.source_type,
		target_types=[request.target_type],
		max_hypotheses=request.max_results,
	)

	asyncio.create_task(
		run_research_session(session_id, session_request, event_store)
	)

	return {"session_id": session_id, "status": "created"}


@router.post("/literature")
async def literature_search(request: LiteratureQuery):
	"""Search literature and return papers."""
	try:
		search_query = f"{request.query} {request.disease_area}".strip()
		papers = await search_papers(search_query, max_results=request.max_results)
		return {
			"query": request.query,
			"disease_area": request.disease_area,
			"status": "success",
			"results": [{"paper_id": p.paper_id, "title": p.title, "abstract": p.abstract[:200]} for p in papers],
		}
	except Exception as exc:
		return {
			"query": request.query,
			"disease_area": request.disease_area,
			"status": "error",
			"results": [],
			"error": str(exc),
		}
