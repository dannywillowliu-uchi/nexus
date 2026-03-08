from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from nexus.tools.molecular_dock import molecular_dock


@patch("nexus.tools.molecular_dock._fetch_sdf_for_drug", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock._fetch_pdb_for_gene", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock.TamarindClient")
async def test_molecular_dock_uses_tamarind_client(mock_client_cls, mock_pdb, mock_sdf):
	"""molecular_dock should use TamarindClient for upload and submit."""
	mock_pdb.return_value = "ATOM 1 CA ALA A 1"
	mock_sdf.return_value = b"fake sdf content"

	mock_instance = AsyncMock()
	mock_instance.upload_file.return_value = "https://tamarind.bio/files/test.pdb"
	mock_instance.submit_job.return_value = "nexus-dock-test"
	mock_client_cls.return_value = mock_instance

	with patch("nexus.tools.molecular_dock.settings") as mock_settings:
		mock_settings.tamarind_bio_api_key = "test-key"
		result = await molecular_dock("Aspirin", "COX2")

	assert result.status == "partial"
	assert mock_instance.upload_file.await_count == 2
	mock_instance.submit_job.assert_awaited_once()


@patch("nexus.tools.molecular_dock.settings")
async def test_molecular_dock_no_api_key(mock_settings):
	"""No API key returns partial with skip message."""
	mock_settings.tamarind_bio_api_key = ""
	result = await molecular_dock("Aspirin", "COX2")
	assert result.status == "partial"
	assert "skipped" in result.summary.lower()
