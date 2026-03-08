from unittest.mock import AsyncMock, MagicMock, patch

from nexus.tools.tamarind_client import TamarindClient


@patch("nexus.tools.tamarind_client.settings")
async def test_list_job_types(mock_settings):
	"""list_job_types returns available job types from the API."""
	mock_settings.tamarind_bio_api_key = "test-key"
	client = TamarindClient(api_key="test-key")

	mock_response = MagicMock()
	mock_response.status_code = 200
	mock_response.json.return_value = {
		"jobTypes": ["diffdock", "esmfold", "autodock_vina", "gnina"]
	}
	mock_response.raise_for_status = MagicMock()

	with patch("httpx.AsyncClient") as mock_http:
		mock_http_instance = AsyncMock()
		mock_http_instance.get = AsyncMock(return_value=mock_response)
		mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
		mock_http_instance.__aexit__ = AsyncMock(return_value=False)
		mock_http.return_value = mock_http_instance

		result = await client.list_job_types()

	assert "diffdock" in result
	assert "esmfold" in result
	assert len(result) == 4
