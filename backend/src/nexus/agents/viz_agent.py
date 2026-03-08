"""Visualization agent for generating discovery path diagram metadata.

Takes an ABCHypothesis with its ABC path and optional pivot trail,
queries the BioRender API for relevant icons, and returns structured
figure metadata for the frontend to render.
"""

from __future__ import annotations

import logging

import httpx

from nexus.config import settings
from nexus.graph.abc import ABCHypothesis

logger = logging.getLogger(__name__)

BIORENDER_BASE_URL = "https://api.biorender.com/v1"


async def _fetch_icon_url(entity_type: str, client: httpx.AsyncClient) -> str | None:
	"""Search BioRender for an icon matching the entity type.

	Returns the URL of the first matching icon, or None on failure.
	"""
	try:
		resp = await client.get(
			f"{BIORENDER_BASE_URL}/icons/search",
			params={"query": entity_type, "limit": 5},
		)
		resp.raise_for_status()
		data = resp.json()
		icons = data.get("icons", [])
		if icons:
			return icons[0].get("url")
	except Exception:
		logger.warning("Failed to fetch BioRender icon for %s", entity_type)
	return None


async def run_viz_agent(
	hypothesis: ABCHypothesis,
	pivot_trail: list[dict] | None = None,
) -> dict:
	"""Generate visualization metadata for a hypothesis discovery path.

	Returns {
		"hypothesis_id": str,
		"nodes": [{"id": str, "name": str, "type": str, "icon_url": str | None}],
		"edges": [{"source": str, "target": str, "relationship": str}],
		"pivot_trail": [{"entity": str, "type": str, "reason": str}] | None,
		"fallback": bool  # True if no API key, text-only mode
	}
	"""
	hypothesis_id = f"{hypothesis.a_id}-{hypothesis.b_id}-{hypothesis.c_id}"

	nodes = [
		{"id": hypothesis.a_id, "name": hypothesis.a_name, "type": hypothesis.a_type, "icon_url": None},
		{"id": hypothesis.b_id, "name": hypothesis.b_name, "type": hypothesis.b_type, "icon_url": None},
		{"id": hypothesis.c_id, "name": hypothesis.c_name, "type": hypothesis.c_type, "icon_url": None},
	]

	edges = [
		{"source": hypothesis.a_id, "target": hypothesis.b_id, "relationship": hypothesis.ab_relationship},
		{"source": hypothesis.b_id, "target": hypothesis.c_id, "relationship": hypothesis.bc_relationship},
	]

	api_key = settings.biorender_api_key
	fallback = not api_key

	if not fallback:
		headers = {"Authorization": f"Bearer {api_key}"}
		async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
			# Collect unique entity types to avoid duplicate requests
			type_to_url: dict[str, str | None] = {}
			for node in nodes:
				entity_type = node["type"]
				if entity_type not in type_to_url:
					type_to_url[entity_type] = await _fetch_icon_url(entity_type, client)
			# Assign icon URLs to nodes
			for node in nodes:
				node["icon_url"] = type_to_url.get(node["type"])

	return {
		"hypothesis_id": hypothesis_id,
		"nodes": nodes,
		"edges": edges,
		"pivot_trail": pivot_trail,
		"fallback": fallback,
	}
