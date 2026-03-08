from unittest.mock import AsyncMock, patch

import httpx
import pytest

from nexus.cloudlab.provider import ExperimentProtocol
from nexus.cloudlab.strateos import StrateosProvider


def _make_protocol() -> ExperimentProtocol:
	return ExperimentProtocol(
		hypothesis_id="H001",
		title="Test Experiment",
		description="Test hypothesis validation",
		protocol_json={"instructions": [{"op": "pipette", "volume": "10:microliter"}]},
		estimated_cost=50.0,
	)


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
	response = httpx.Response(
		status_code=status_code,
		json=json_data,
		request=httpx.Request("GET", "https://example.com"),
	)
	return response


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_validate_protocol_success(mock_settings):
	mock_settings.strateos_email = "test@example.com"
	mock_settings.strateos_token = "test-token"
	mock_settings.strateos_organization_id = "org123"

	provider = StrateosProvider()
	protocol = _make_protocol()

	mock_resp = _mock_response({"valid": True, "errors": []})

	with patch("httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.post = AsyncMock(return_value=mock_resp)
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client_cls.return_value = mock_client

		result = await provider.validate_protocol(protocol)

	assert result == {"valid": True, "errors": []}


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_validate_protocol_http_error(mock_settings):
	mock_settings.strateos_email = "test@example.com"
	mock_settings.strateos_token = "test-token"
	mock_settings.strateos_organization_id = "org123"

	provider = StrateosProvider()
	protocol = _make_protocol()

	mock_resp = _mock_response({"detail": "Bad request"}, status_code=400)

	with patch("httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.post = AsyncMock(return_value=mock_resp)
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client_cls.return_value = mock_client

		result = await provider.validate_protocol(protocol)

	assert result["error"] is True
	assert result["status_code"] == 400


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_validate_protocol_missing_credentials(mock_settings):
	mock_settings.strateos_email = ""
	mock_settings.strateos_token = ""
	mock_settings.strateos_organization_id = ""

	provider = StrateosProvider()
	protocol = _make_protocol()

	with pytest.raises(ValueError, match="Missing Strateos credentials"):
		await provider.validate_protocol(protocol)


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_submit_experiment_success(mock_settings):
	mock_settings.strateos_email = "test@example.com"
	mock_settings.strateos_token = "test-token"
	mock_settings.strateos_organization_id = "org123"

	provider = StrateosProvider()
	protocol = _make_protocol()

	mock_resp = _mock_response({"id": "run_abc123", "status": "submitted"})

	with patch("httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.post = AsyncMock(return_value=mock_resp)
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client_cls.return_value = mock_client

		result = await provider.submit_experiment(protocol)

	assert result.submission_id == "run_abc123"
	assert result.provider == "strateos"
	assert result.status == "submitted"


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_poll_status_success(mock_settings):
	mock_settings.strateos_email = "test@example.com"
	mock_settings.strateos_token = "test-token"
	mock_settings.strateos_organization_id = "org123"

	provider = StrateosProvider()

	mock_resp = _mock_response({"id": "run_abc123", "status": "running"})

	with patch("httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.get = AsyncMock(return_value=mock_resp)
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client_cls.return_value = mock_client

		result = await provider.poll_status("run_abc123")

	assert result == "running"


@pytest.mark.asyncio
@patch("nexus.cloudlab.strateos.settings")
async def test_get_results_success(mock_settings):
	mock_settings.strateos_email = "test@example.com"
	mock_settings.strateos_token = "test-token"
	mock_settings.strateos_organization_id = "org123"

	provider = StrateosProvider()

	mock_resp = _mock_response({
		"summary": "Experiment completed successfully",
		"measurements": [{"value": 0.85}],
	})

	with patch("httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.get = AsyncMock(return_value=mock_resp)
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client_cls.return_value = mock_client

		result = await provider.get_results("run_abc123")

	assert result.submission_id == "run_abc123"
	assert result.status == "completed"
	assert result.summary == "Experiment completed successfully"
	assert "measurements" in result.data
