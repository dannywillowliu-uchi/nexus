from unittest.mock import AsyncMock, MagicMock, patch

from nexus.tools.molecular_dock import molecular_dock


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


@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.TamarindClient")
async def test_molecular_dock_submit_success(mock_client_cls, mock_settings):
	mock_settings.tamarind_bio_api_key = "test-key"

	mock_client = MagicMock()
	mock_client.run_job = AsyncMock(return_value={
		"status": "Complete",
		"result": {
			"docking_score": -8.5,
			"download_url": "https://s3.example.com/results.tar.gz",
		},
	})
	mock_client_cls.return_value = mock_client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "success"
	assert result.confidence_delta == 0.5
	assert result.evidence_type == "supporting"
	assert result.raw_data["docking_score"] == -8.5
	assert "aspirin" in result.summary
	assert "COX2" in result.summary

	# Verify the run_job call
	mock_client.run_job.assert_called_once_with(
		job_name="nexus-dock-aspirin-COX2",
		job_type="autodock_vina",
		settings={
			"target": "COX2",
			"ligand": "aspirin",
		},
	)


@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.TamarindClient")
async def test_molecular_dock_submit_timeout(mock_client_cls, mock_settings):
	mock_settings.tamarind_bio_api_key = "test-key"

	mock_client = MagicMock()
	mock_client.run_job = AsyncMock(side_effect=TimeoutError("timed out"))
	mock_client_cls.return_value = mock_client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "partial"
	assert result.raw_data["status"] == "polling_timeout"
	assert result.raw_data["job_name"] == "nexus-dock-aspirin-COX2"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"


@patch("nexus.tools.molecular_dock.settings")
@patch("nexus.tools.molecular_dock.TamarindClient")
async def test_molecular_dock_http_error(mock_client_cls, mock_settings):
	mock_settings.tamarind_bio_api_key = "test-key"

	mock_client = MagicMock()
	mock_client.run_job = AsyncMock(side_effect=Exception("Internal Server Error"))
	mock_client_cls.return_value = mock_client

	result = await molecular_dock("aspirin", "COX2")

	assert result.status == "error"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"
	assert "failed" in result.summary.lower()
	assert "error" in result.raw_data
