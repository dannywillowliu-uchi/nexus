from unittest.mock import AsyncMock, MagicMock, patch

from nexus.agents.literature.search import search_pubmed, search_semantic_scholar


MOCK_ESEARCH_RESPONSE = {"esearchresult": {"idlist": ["11111", "22222"]}}

MOCK_EFETCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>11111</PMID>
      <Article>
        <ArticleTitle>BRCA1 and Breast Cancer Risk</ArticleTitle>
        <Abstract>
          <AbstractText>BRCA1 mutations increase breast cancer risk.</AbstractText>
        </Abstract>
        <Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>22222</PMID>
      <Article>
        <ArticleTitle>TP53 in Cancer</ArticleTitle>
        <Abstract>
          <AbstractText>TP53 is a tumor suppressor gene.</AbstractText>
        </Abstract>
        <Journal><JournalIssue><PubDate><Year>2022</Year></PubDate></JournalIssue></Journal>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

MOCK_S2_RESPONSE = {
	"data": [
		{
			"paperId": "abc123",
			"title": "Deep Learning for Genomics",
			"abstract": "We apply deep learning to genomic data.",
			"year": 2024,
			"citationCount": 42,
		},
		{
			"paperId": "def456",
			"title": "CRISPR Screening Methods",
			"abstract": "Novel CRISPR screening approaches.",
			"year": 2023,
			"citationCount": 15,
		},
	]
}


def _make_response(json_data=None, text=None):
	"""Create a MagicMock httpx.Response with sync json() and raise_for_status()."""
	resp = MagicMock()
	if json_data is not None:
		resp.json.return_value = json_data
	if text is not None:
		resp.text = text
	return resp


def _make_async_client(get_side_effect=None, get_return_value=None):
	"""Create a mock async client with proper context manager support."""
	mock_client = MagicMock()
	if get_side_effect is not None:
		mock_client.get = AsyncMock(side_effect=get_side_effect)
	elif get_return_value is not None:
		mock_client.get = AsyncMock(return_value=get_return_value)
	mock_client.__aenter__ = AsyncMock(return_value=mock_client)
	mock_client.__aexit__ = AsyncMock(return_value=False)
	return mock_client


@patch("nexus.agents.literature.search.httpx.AsyncClient")
async def test_search_pubmed(mock_async_client):
	esearch_resp = _make_response(json_data=MOCK_ESEARCH_RESPONSE)
	efetch_resp = _make_response(text=MOCK_EFETCH_XML)
	client = _make_async_client(get_side_effect=[esearch_resp, efetch_resp])
	mock_async_client.return_value = client

	papers = await search_pubmed("BRCA1 cancer")

	assert len(papers) == 2
	assert papers[0].paper_id == "11111"
	assert papers[0].title == "BRCA1 and Breast Cancer Risk"
	assert papers[0].year == 2023
	assert papers[0].source == "pubmed"
	assert papers[1].paper_id == "22222"
	assert papers[1].title == "TP53 in Cancer"


@patch("nexus.agents.literature.search.httpx.AsyncClient")
async def test_search_pubmed_empty(mock_async_client):
	empty_resp = _make_response(json_data={"esearchresult": {"idlist": []}})
	client = _make_async_client(get_return_value=empty_resp)
	mock_async_client.return_value = client

	papers = await search_pubmed("nonexistent query xyz")
	assert papers == []


@patch("nexus.agents.literature.search.httpx.AsyncClient")
async def test_search_semantic_scholar(mock_async_client):
	s2_resp = _make_response(json_data=MOCK_S2_RESPONSE)
	client = _make_async_client(get_return_value=s2_resp)
	mock_async_client.return_value = client

	papers = await search_semantic_scholar("deep learning genomics")

	assert len(papers) == 2
	assert papers[0].paper_id == "abc123"
	assert papers[0].title == "Deep Learning for Genomics"
	assert papers[0].year == 2024
	assert papers[0].citation_count == 42
	assert papers[0].source == "semantic_scholar"
	assert papers[1].paper_id == "def456"
