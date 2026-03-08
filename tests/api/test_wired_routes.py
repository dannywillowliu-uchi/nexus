from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.api.app import app


@pytest.fixture
async def client():
	with (
		patch("nexus.api.app.graph_client.connect", new_callable=AsyncMock),
		patch("nexus.api.app.graph_client.close", new_callable=AsyncMock),
	):
		transport = ASGITransport(app=app)
		async with AsyncClient(transport=transport, base_url="http://test") as ac:
			yield ac


async def test_graph_explore_no_connection(client):
	"""GET /api/graph/explore returns empty results when graph not connected."""
	resp = await client.get("/api/graph/explore", params={"entity_name": "Alzheimer", "entity_type": "Disease"})
	assert resp.status_code == 200
	data = resp.json()
	assert data["entity_name"] == "Alzheimer"
	assert data["entity_type"] == "Disease"
	assert data["nodes"] == []
	assert data["edges"] == []


async def test_quick_query_placeholder(client):
	"""POST /api/query returns scored hypotheses structure."""
	with patch("nexus.api.routes.query.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc:
		mock_abc.return_value = []
		resp = await client.post("/api/query", json={
			"source_name": "BRCA1",
			"source_type": "Gene",
			"target_type": "Disease",
		})
		assert resp.status_code == 200
		data = resp.json()
		assert data["source"] == "BRCA1"
		assert data["source_type"] == "Gene"
		assert data["target_type"] == "Disease"
		assert data["count"] == 0
		assert data["hypotheses"] == []


async def test_session_report_not_found(client):
	"""GET /api/sessions/{id}/report for nonexistent session returns not_found."""
	resp = await client.get("/api/sessions/nonexistent-session-id/report")
	assert resp.status_code == 200
	data = resp.json()
	assert data["session_id"] == "nonexistent-session-id"
	assert data["status"] == "not_found"
	assert data["hypotheses"] == []


async def test_feed_empty(client):
	"""GET /api/feed returns proper structure with empty entries."""
	resp = await client.get("/api/feed")
	assert resp.status_code == 200
	data = resp.json()
	assert data["disease_area"] is None
	assert data["limit"] == 20
	assert data["offset"] == 0
	assert data["total"] == 0
	assert data["entries"] == []


async def test_hypothesis_not_found(client):
	"""GET /api/hypotheses/{id} returns not_found status."""
	resp = await client.get("/api/hypotheses/fake-hypothesis-id")
	assert resp.status_code == 200
	data = resp.json()
	assert data["hypothesis_id"] == "fake-hypothesis-id"
	assert data["status"] == "not_found"
