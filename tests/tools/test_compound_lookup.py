from unittest.mock import AsyncMock, MagicMock, patch

from nexus.tools.compound_lookup import compound_lookup


MOCK_PUBCHEM_RESPONSE = {
	"PC_Compounds": [
		{
			"id": {"id": {"cid": 2244}},
			"props": [
				{
					"urn": {"label": "Molecular Formula"},
					"value": {"sval": "C9H8O4"},
				},
				{
					"urn": {"label": "Molecular Weight"},
					"value": {"fval": 180.16},
				},
				{
					"urn": {"label": "IUPAC Name", "name": "Preferred"},
					"value": {"sval": "2-acetoxybenzoic acid"},
				},
			],
		}
	]
}


def _make_response(json_data=None, status_code=200):
	resp = MagicMock()
	resp.json.return_value = json_data
	resp.status_code = status_code
	return resp


def _make_async_client(get_return_value=None):
	mock_client = MagicMock()
	mock_client.get = AsyncMock(return_value=get_return_value)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	return mock_client


@patch("nexus.tools.compound_lookup.httpx.AsyncClient")
async def test_compound_lookup_success(mock_async_client):
	resp = _make_response(json_data=MOCK_PUBCHEM_RESPONSE)
	client = _make_async_client(get_return_value=resp)
	mock_async_client.return_value = client

	result = await compound_lookup("aspirin")

	assert result.status == "success"
	assert result.evidence_type == "supporting"
	assert result.confidence_delta == 0.1
	assert result.raw_data["cid"] == 2244
	assert result.raw_data["molecular_formula"] == "C9H8O4"
	assert result.raw_data["molecular_weight"] == 180.16
	assert result.raw_data["iupac_name"] == "2-acetoxybenzoic acid"
	assert "aspirin" in result.summary.lower()


@patch("nexus.tools.compound_lookup.httpx.AsyncClient")
async def test_compound_lookup_empty(mock_async_client):
	resp = _make_response(json_data={"PC_Compounds": []})
	client = _make_async_client(get_return_value=resp)
	mock_async_client.return_value = client

	result = await compound_lookup("nonexistent_compound")

	assert result.status == "success"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"


@patch("nexus.tools.compound_lookup.httpx.AsyncClient")
async def test_compound_lookup_404(mock_async_client):
	import httpx

	mock_response = MagicMock()
	mock_response.status_code = 404
	error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

	mock_client = MagicMock()
	mock_client.get = AsyncMock(side_effect=error)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	mock_async_client.return_value = mock_client

	result = await compound_lookup("fake_compound")

	assert result.status == "success"
	assert result.confidence_delta == 0.0
	assert result.raw_data["error"] == "not_found"
