import json
from unittest.mock import AsyncMock, patch

from nexus.agents.literature.extract import extract_triples
from nexus.agents.literature.search import Paper


MOCK_PAPERS = [
	Paper(
		paper_id="11111",
		title="BRCA1 and Breast Cancer",
		abstract="BRCA1 mutations increase breast cancer risk significantly.",
		year=2023,
		source="pubmed",
	),
]

MOCK_TRIPLES_JSON = json.dumps([
	{
		"subject": "BRCA1",
		"subject_type": "Gene",
		"predicate": "associated_with",
		"object": "Breast Cancer",
		"object_type": "Disease",
		"confidence": 0.95,
		"source_paper_id": "11111",
	},
	{
		"subject": "BRCA1",
		"subject_type": "Gene",
		"predicate": "increases_risk_of",
		"object": "Breast Cancer",
		"object_type": "Disease",
		"confidence": 0.9,
		"source_paper_id": "11111",
	},
])


@patch("nexus.agents.literature.extract.settings")
@patch("nexus.agents.literature.extract.anthropic.AsyncAnthropic")
async def test_extract_triples(mock_anthropic_cls, mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	mock_content_block = AsyncMock()
	mock_content_block.text = MOCK_TRIPLES_JSON

	mock_message = AsyncMock()
	mock_message.content = [mock_content_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	triples = await extract_triples(MOCK_PAPERS)

	assert len(triples) == 2
	assert triples[0].subject == "BRCA1"
	assert triples[0].subject_type == "Gene"
	assert triples[0].predicate == "associated_with"
	assert triples[0].object == "Breast Cancer"
	assert triples[0].object_type == "Disease"
	assert triples[0].confidence == 0.95
	assert triples[0].source_paper_id == "11111"


@patch("nexus.agents.literature.extract.settings")
@patch("nexus.agents.literature.extract.anthropic.AsyncAnthropic")
async def test_extract_triples_markdown_fences(mock_anthropic_cls, mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	fenced_response = f"```json\n{MOCK_TRIPLES_JSON}\n```"
	mock_content_block = AsyncMock()
	mock_content_block.text = fenced_response

	mock_message = AsyncMock()
	mock_message.content = [mock_content_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	triples = await extract_triples(MOCK_PAPERS)
	assert len(triples) == 2
	assert triples[0].subject == "BRCA1"


@patch("nexus.agents.literature.extract.settings")
async def test_extract_triples_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	triples = await extract_triples(MOCK_PAPERS)
	assert triples == []


async def test_extract_triples_empty_papers():
	triples = await extract_triples([])
	assert triples == []
