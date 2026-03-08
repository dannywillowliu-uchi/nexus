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


async def test_health_check(client):
	resp = await client.get("/api/health")
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] == "ok"
	assert data["service"] == "nexus"
