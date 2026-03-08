import json
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.heartbeat.ingest import ingest_recent_papers


MOCK_ESEARCH_RESPONSE = {"esearchresult": {"idlist": ["99901", "99902"]}}

MOCK_EFETCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>99901</PMID>
      <Article>
        <ArticleTitle>Novel TNF-alpha pathway in ALS</ArticleTitle>
        <Abstract>
          <AbstractText>TNF-alpha signaling modulates ALS progression.</AbstractText>
        </Abstract>
        <Journal><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>99902</PMID>
      <Article>
        <ArticleTitle>SOD1 mutations in motor neuron disease</ArticleTitle>
        <Abstract>
          <AbstractText>SOD1 G93A mutation drives oxidative stress in MND.</AbstractText>
        </Abstract>
        <Journal><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

MOCK_TRIPLES_JSON = json.dumps([
	{
		"subject": "TNF-alpha",
		"subject_type": "Protein",
		"predicate": "modulates",
		"object": "ALS",
		"object_type": "Disease",
		"confidence": 0.9,
		"source_paper_id": "99901",
	},
	{
		"subject": "SOD1",
		"subject_type": "Gene",
		"predicate": "causes",
		"object": "Motor Neuron Disease",
		"object_type": "Disease",
		"confidence": 0.85,
		"source_paper_id": "99902",
	},
])


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


@patch("nexus.heartbeat.ingest.graph_client")
@patch("nexus.agents.literature.extract.settings")
@patch("nexus.agents.literature.extract.anthropic.AsyncAnthropic")
@patch("nexus.agents.literature.search.httpx.AsyncClient")
async def test_ingest_recent_papers(
	mock_httpx_client_cls,
	mock_anthropic_cls,
	mock_extract_settings,
	mock_graph_client,
):
	# Mock PubMed search
	esearch_resp = _make_response(json_data=MOCK_ESEARCH_RESPONSE)
	efetch_resp = _make_response(text=MOCK_EFETCH_XML)
	http_client = _make_async_client(get_side_effect=[esearch_resp, efetch_resp])
	mock_httpx_client_cls.return_value = http_client

	# Mock Anthropic extraction
	mock_extract_settings.anthropic_api_key = "test-key"
	mock_content_block = MagicMock()
	mock_content_block.text = MOCK_TRIPLES_JSON
	mock_message = MagicMock()
	mock_message.content = [mock_content_block]
	mock_anthropic_instance = AsyncMock()
	mock_anthropic_instance.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_anthropic_instance

	# Mock graph write
	mock_graph_client.execute_write = AsyncMock(return_value=[{"r": {}}])

	result = await ingest_recent_papers("ALS", days=7, max_papers=10)

	assert result["papers_found"] == 2
	assert result["triples_extracted"] == 2
	assert result["edges_merged"] == 2
	assert len(result["triples"]) == 2
	assert result["triples"][0]["subject"] == "TNF-alpha"


@patch("nexus.agents.literature.search.httpx.AsyncClient")
async def test_ingest_recent_papers_no_papers(mock_httpx_client_cls):
	empty_resp = _make_response(json_data={"esearchresult": {"idlist": []}})
	http_client = _make_async_client(get_return_value=empty_resp)
	mock_httpx_client_cls.return_value = http_client

	result = await ingest_recent_papers("nonexistent query xyz", days=7)

	assert result["papers_found"] == 0
	assert result["triples_extracted"] == 0
	assert result["edges_merged"] == 0
	assert result["triples"] == []
