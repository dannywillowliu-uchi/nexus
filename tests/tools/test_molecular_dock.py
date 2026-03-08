from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from nexus.tools.molecular_dock import molecular_dock


def _make_response(json_data=None, status_code=200):
	resp = MagicMock()
	resp.json.return_value = json_data
	resp.status_code = status_code
	resp.raise_for_status = MagicMock()
	return resp


def _make_async_client(**kwargs):
	"""Create a mock AsyncClient with configurable post/get behaviour."""
	mock_client = MagicMock()
	mock_client.post = kwargs.get("post", AsyncMock())
	mock_client.get = kwargs.get("get", AsyncMock())
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	return mock_client


@patch("nexus.tools.molecular_dock.settings")
async def test_molecular_dock_no_api_key(mock_settings):
	mock_settings.tamarind_bio_api_key = ""

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "partial"
	assert result.raw_data["reason"] == "missing_api_key"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"
	assert "aspirin" in result.summary
	assert "COX2" in result.summary


@patch("nexus.tools.molecular_dock.asyncio.sleep", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.httpx.AsyncClient")
async def test_molecular_dock_submit_success(mock_async_client, mock_settings, mock_sleep):
	mock_settings.tamarind_bio_api_key = "test-key"

	submit_resp = _make_response(json_data={"jobName": "nexus-dock-aspirin-COX2"})
	poll_resp = _make_response(json_data={
		"jobs": [{"jobName": "nexus-dock-aspirin-COX2", "status": "Complete"}]
	})
	result_resp = _make_response(json_data={
		"docking_score": -8.5,
		"download_url": "https://s3.example.com/results.tar.gz",
	})

	client = _make_async_client(
		post=AsyncMock(side_effect=[submit_resp, result_resp]),
		get=AsyncMock(return_value=poll_resp),
	)
	mock_async_client.return_value = client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "success"
	assert result.confidence_delta == 0.5
	assert result.evidence_type == "supporting"
	assert result.raw_data["docking_score"] == -8.5
	assert "aspirin" in result.summary
	assert "COX2" in result.summary

	# Verify the submit call
	first_post_call = client.post.call_args_list[0]
	assert "/submit-job" in first_post_call.args[0]
	submit_payload = first_post_call.kwargs["json"]
	assert submit_payload["type"] == "autodock_vina"
	assert submit_payload["settings"]["target"] == "COX2"
	assert submit_payload["settings"]["ligand"] == "aspirin"

	# Verify polling happened
	client.get.assert_called()
	get_call = client.get.call_args
	assert "/jobs" in get_call.args[0]

	# Verify result fetch
	second_post_call = client.post.call_args_list[1]
	assert "/result" in second_post_call.args[0]
	result_payload = second_post_call.kwargs["json"]
	assert result_payload["pdbsOnly"] is False


@patch("nexus.tools.molecular_dock.asyncio.sleep", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.httpx.AsyncClient")
async def test_molecular_dock_submit_timeout(mock_async_client, mock_settings, mock_sleep):
	mock_settings.tamarind_bio_api_key = "test-key"

	submit_resp = _make_response(json_data={"jobName": "nexus-dock-aspirin-COX2"})
	# Polling always returns "Running" -- never completes
	poll_resp = _make_response(json_data={
		"jobs": [{"jobName": "nexus-dock-aspirin-COX2", "status": "Running"}]
	})

	client = _make_async_client(
		post=AsyncMock(return_value=submit_resp),
		get=AsyncMock(return_value=poll_resp),
	)
	mock_async_client.return_value = client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "partial"
	assert result.raw_data["status"] == "polling_timeout"
	assert result.raw_data["job_name"] == "nexus-dock-aspirin-COX2"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"


@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.httpx.AsyncClient")
async def test_molecular_dock_http_error(mock_async_client, mock_settings):
	mock_settings.tamarind_bio_api_key = "test-key"

	mock_response = MagicMock()
	mock_response.status_code = 500
	error = httpx.HTTPStatusError(
		"Internal Server Error", request=MagicMock(), response=mock_response
	)

	mock_client = MagicMock()
	mock_client.post = AsyncMock(side_effect=error)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	mock_async_client.return_value = mock_client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "error"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"
	assert "failed" in result.summary.lower()
	assert "error" in result.raw_data
