import json
from unittest.mock import AsyncMock, patch

import pytest

from nexus.agents.literature.extract import Triple
from nexus.agents.reasoning_agent import generate_quick_summaries, generate_research_brief
from nexus.graph.abc import ABCHypothesis


def _make_hypothesis(**overrides) -> ABCHypothesis:
	"""Create a test ABCHypothesis with sensible defaults."""
	defaults = {
		"a_id": "D001",
		"a_name": "Diabetes",
		"a_type": "Disease",
		"b_id": "G001",
		"b_name": "PPARG",
		"b_type": "Gene",
		"c_id": "C001",
		"c_name": "Metformin",
		"c_type": "Compound",
		"ab_relationship": "ASSOCIATES_DaG",
		"bc_relationship": "BINDS_CbG",
		"path_count": 5,
		"novelty_score": 0.95,
		"path_strength": 0.87,
		"intermediaries": [],
	}
	defaults.update(overrides)
	return ABCHypothesis(**defaults)


MOCK_TRIPLES = [
	Triple(
		subject="Diabetes",
		subject_type="Disease",
		predicate="associated_with",
		object="PPARG",
		object_type="Gene",
		confidence=0.9,
		source_paper_id="paper1",
	),
	Triple(
		subject="Metformin",
		subject_type="Compound",
		predicate="binds",
		object="PPARG",
		object_type="Gene",
		confidence=0.85,
		source_paper_id="paper2",
	),
]

MOCK_SUMMARIES_JSON = json.dumps([
	{
		"hypothesis": "Diabetes -> PPARG -> Metformin",
		"summary": "Diabetes is associated with PPARG gene variants. Metformin binds to PPARG, suggesting a mechanistic link.",
	},
])

MOCK_BRIEF_JSON = json.dumps({
	"connection_explanation": "Diabetes is linked to PPARG through genetic association, and Metformin targets PPARG directly.",
	"literature_evidence": [
		{
			"paper_id": "paper1",
			"title": "PPARG in Diabetes",
			"snippet": "PPARG variants are strongly associated with type 2 diabetes.",
			"confidence": 0.92,
		},
	],
	"existing_knowledge_comparison": "This connection is partially known but the specific binding mechanism is novel.",
	"confidence": {
		"graph_evidence": 0.85,
		"graph_reasoning": "Multiple paths connect these entities through PPARG.",
		"literature_support": 0.78,
		"literature_reasoning": "Several papers support the PPARG-diabetes association.",
		"biological_plausibility": 0.9,
		"plausibility_reasoning": "PPARG is a well-known metabolic regulator.",
		"novelty": 0.6,
		"novelty_reasoning": "The association is known but the drug mechanism is less explored.",
	},
	"suggested_validation": "In vitro binding assay of Metformin to PPARG followed by glucose uptake measurement.",
})


@pytest.mark.asyncio
@patch("nexus.agents.reasoning_agent.settings")
@patch("nexus.agents.reasoning_agent.anthropic.AsyncAnthropic")
async def test_generate_quick_summaries(mock_anthropic_cls, mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	mock_content_block = AsyncMock()
	mock_content_block.text = MOCK_SUMMARIES_JSON

	mock_message = AsyncMock()
	mock_message.content = [mock_content_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	hypotheses = [_make_hypothesis()]
	summaries = await generate_quick_summaries(hypotheses, MOCK_TRIPLES)

	assert len(summaries) == 1
	assert isinstance(summaries[0], str)
	assert "PPARG" in summaries[0]

	mock_client.messages.create.assert_called_once()
	call_kwargs = mock_client.messages.create.call_args.kwargs
	assert call_kwargs["model"] == "claude-sonnet-4-20250514"
	assert call_kwargs["max_tokens"] == 2000


@pytest.mark.asyncio
@patch("nexus.agents.reasoning_agent.settings")
async def test_generate_quick_summaries_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	hypotheses = [_make_hypothesis()]
	summaries = await generate_quick_summaries(hypotheses, MOCK_TRIPLES)

	assert len(summaries) == 1
	assert "Diabetes" in summaries[0]
	assert "Metformin" in summaries[0]
	assert "PPARG" in summaries[0]


@pytest.mark.asyncio
@patch("nexus.agents.reasoning_agent.settings")
@patch("nexus.agents.reasoning_agent.anthropic.AsyncAnthropic")
async def test_generate_research_brief(mock_anthropic_cls, mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	mock_content_block = AsyncMock()
	mock_content_block.text = MOCK_BRIEF_JSON

	mock_message = AsyncMock()
	mock_message.content = [mock_content_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	hypothesis = _make_hypothesis()
	papers = [
		{
			"paper_id": "paper1",
			"title": "PPARG in Diabetes",
			"abstract": "PPARG variants are strongly associated with type 2 diabetes.",
		},
	]

	brief = await generate_research_brief(hypothesis, MOCK_TRIPLES, papers)

	assert brief.hypothesis_title == "Diabetes -> PPARG -> Metformin"
	assert "PPARG" in brief.connection_explanation
	assert len(brief.literature_evidence) == 1
	assert brief.literature_evidence[0].paper_id == "paper1"
	assert brief.literature_evidence[0].confidence == 0.92
	assert brief.confidence.graph_evidence == 0.85
	assert brief.confidence.literature_support == 0.78
	assert brief.confidence.biological_plausibility == 0.9
	assert brief.confidence.novelty == 0.6
	assert "binding assay" in brief.suggested_validation.lower()

	mock_client.messages.create.assert_called_once()
	call_kwargs = mock_client.messages.create.call_args.kwargs
	assert call_kwargs["model"] == "claude-sonnet-4-20250514"
	assert call_kwargs["max_tokens"] == 2000


@pytest.mark.asyncio
@patch("nexus.agents.reasoning_agent.settings")
async def test_generate_research_brief_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	hypothesis = _make_hypothesis()
	brief = await generate_research_brief(hypothesis, MOCK_TRIPLES, [])

	assert brief.hypothesis_title == "Diabetes -> PPARG -> Metformin"
	assert "Diabetes" in brief.connection_explanation
	assert "Metformin" in brief.connection_explanation
	assert brief.literature_evidence == []
	assert brief.confidence.graph_evidence == hypothesis.path_strength
	assert brief.confidence.novelty == hypothesis.novelty_score
	assert brief.confidence.literature_support == 0.0
