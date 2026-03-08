from unittest.mock import AsyncMock, patch

from nexus.agents.literature.agent import LiteratureResult, run_literature_agent
from nexus.agents.literature.extract import Triple
from nexus.agents.literature.search import Paper


MOCK_PAPERS = [
	Paper(paper_id="11111", title="Test Paper", abstract="Test abstract.", year=2023, source="pubmed"),
]

MOCK_TRIPLES = [
	Triple(
		subject="BRCA1",
		subject_type="Gene",
		predicate="associated_with",
		object="Cancer",
		object_type="Disease",
		confidence=0.9,
		source_paper_id="11111",
	),
]


@patch("nexus.agents.literature.agent.extract_triples", new_callable=AsyncMock)
@patch("nexus.agents.literature.agent.search_papers", new_callable=AsyncMock)
async def test_run_literature_agent(mock_search, mock_extract):
	mock_search.return_value = MOCK_PAPERS
	mock_extract.return_value = MOCK_TRIPLES

	result = await run_literature_agent("BRCA1 cancer")

	assert isinstance(result, LiteratureResult)
	assert len(result.papers) == 1
	assert len(result.triples) == 1
	assert result.errors == []
	mock_search.assert_awaited_once_with("BRCA1 cancer", max_results=10)
	mock_extract.assert_awaited_once_with(MOCK_PAPERS)


@patch("nexus.agents.literature.agent.extract_triples", new_callable=AsyncMock)
@patch("nexus.agents.literature.agent.search_papers", new_callable=AsyncMock)
async def test_run_literature_agent_search_error(mock_search, mock_extract):
	mock_search.side_effect = RuntimeError("Network error")

	result = await run_literature_agent("test query")

	assert len(result.errors) == 1
	assert "Paper search failed" in result.errors[0]
	assert result.papers == []
	assert result.triples == []
	mock_extract.assert_not_awaited()


@patch("nexus.agents.literature.agent.extract_triples", new_callable=AsyncMock)
@patch("nexus.agents.literature.agent.search_papers", new_callable=AsyncMock)
async def test_run_literature_agent_extraction_error(mock_search, mock_extract):
	mock_search.return_value = MOCK_PAPERS
	mock_extract.side_effect = RuntimeError("API error")

	result = await run_literature_agent("test query")

	assert len(result.papers) == 1
	assert result.triples == []
	assert len(result.errors) == 1
	assert "Triple extraction failed" in result.errors[0]
