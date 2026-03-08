from unittest.mock import AsyncMock, MagicMock, patch

from nexus.tools.literature_validate import literature_validate


MOCK_ESEARCH_RESPONSE = {"esearchresult": {"idlist": ["12345", "67890"]}}

MOCK_EFETCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <ArticleTitle>BRCA1 associated with breast cancer pathway</ArticleTitle>
        <Abstract>
          <AbstractText>BRCA1 is associated with DNA repair and linked to cancer risk through the p53 pathway.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>67890</PMID>
      <Article>
        <ArticleTitle>No association between XYZ and cancer</ArticleTitle>
        <Abstract>
          <AbstractText>No evidence was found linking XYZ to cancer pathways.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def _make_response(json_data=None, text=None):
	resp = MagicMock()
	if json_data is not None:
		resp.json.return_value = json_data
	if text is not None:
		resp.text = text
	return resp


def _make_async_client(get_side_effect=None, get_return_value=None):
	mock_client = MagicMock()
	if get_side_effect is not None:
		mock_client.get = AsyncMock(side_effect=get_side_effect)
	elif get_return_value is not None:
		mock_client.get = AsyncMock(return_value=get_return_value)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	return mock_client


@patch("nexus.tools.literature_validate.httpx.AsyncClient")
async def test_literature_validate_supporting(mock_async_client):
	esearch_resp = _make_response(json_data=MOCK_ESEARCH_RESPONSE)
	efetch_resp = _make_response(text=MOCK_EFETCH_XML)
	client = _make_async_client(get_side_effect=[esearch_resp, efetch_resp])
	mock_async_client.return_value = client

	hypothesis = {"a_name": "BRCA1", "b_name": "p53", "c_name": "breast cancer"}
	result = await literature_validate(hypothesis)

	assert result.status == "success"
	assert result.raw_data["total_results"] == 2
	assert result.raw_data["supporting_count"] > 0
	assert result.confidence_delta != 0.0
	assert len(result.raw_data["pmids"]) == 2


@patch("nexus.tools.literature_validate.httpx.AsyncClient")
async def test_literature_validate_no_results(mock_async_client):
	empty_resp = _make_response(json_data={"esearchresult": {"idlist": []}})
	client = _make_async_client(get_return_value=empty_resp)
	mock_async_client.return_value = client

	hypothesis = {"a_name": "fake_gene", "b_name": "fake_protein", "c_name": "fake_disease"}
	result = await literature_validate(hypothesis)

	assert result.status == "success"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"
	assert result.raw_data["total_results"] == 0


@patch("nexus.tools.literature_validate.httpx.AsyncClient")
async def test_literature_validate_http_error(mock_async_client):
	import httpx

	mock_client = MagicMock()
	mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection timeout"))
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	mock_async_client.return_value = mock_client

	hypothesis = {"a_name": "A", "b_name": "B", "c_name": "C"}
	result = await literature_validate(hypothesis)

	assert result.status == "error"
	assert result.confidence_delta == 0.0
