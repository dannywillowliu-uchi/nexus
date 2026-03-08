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


async def test_create_session(client):
	with patch("nexus.api.routes.sessions.run_pipeline", new_callable=AsyncMock) as mock_pipeline:
		mock_pipeline.return_value = None
		resp = await client.post("/api/sessions", json={
			"query": "test query",
			"disease_area": "oncology",
			"start_entity": "BRCA1",
			"start_type": "Gene",
			"target_types": ["Compound"],
		})
		assert resp.status_code == 200
		data = resp.json()
		assert "session_id" in data
		assert data["status"] == "created"


async def test_get_session_events(client):
	resp = await client.get("/api/sessions/fake-session-id/events")
	assert resp.status_code == 200
	data = resp.json()
	assert isinstance(data, list)
