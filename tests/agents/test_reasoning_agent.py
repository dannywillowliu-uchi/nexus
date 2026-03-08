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

MOCK_NARRATIVE = """## 1. BIOLOGICAL PLAUSIBILITY

Diabetes is linked to PPARG through genetic association, and Metformin targets PPARG directly. PPARG is a nuclear receptor that regulates fatty acid storage and glucose metabolism. When activated by thiazolidinediones or similar ligands, it enhances insulin sensitivity.

## 2. STRENGTH OF EVIDENCE

Multiple papers support the PPARG-diabetes association. The strongest evidence comes from GWAS studies linking PPARG variants to T2D risk. The drug-gene link through direct binding is well-established pharmacologically.

## 3. WHAT A RESEARCHER WOULD DO FIRST

In vitro binding assay of Metformin to PPARG followed by glucose uptake measurement. Use HepG2 cells for hepatic context, treat with 1-10mM Metformin, measure PPARG transactivation via luciferase reporter.

## 4. WHY THIS MIGHT FAIL

Metformin's primary mechanism is through AMPK, not PPARG. The binding affinity may be too low to be clinically relevant. Off-target effects could confound results.

## 5. CLINICAL SIGNIFICANCE

Type 2 diabetes affects 462 million people worldwide. Current treatments have limitations including weight gain and cardiovascular risk. If Metformin acts through PPARG, it could explain differential responses in patients with PPARG polymorphisms."""


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

	# First call returns narrative, second call returns scores
	mock_narrative_block = AsyncMock()
	mock_narrative_block.text = MOCK_NARRATIVE

	mock_score_block = AsyncMock()
	mock_score_block.text = json.dumps({
		"graph_evidence": 0.87,
		"graph_reasoning": "Multiple paths through PPARG.",
		"literature_support": 0.78,
		"literature_reasoning": "Several papers support the association.",
		"biological_plausibility": 0.9,
		"plausibility_reasoning": "PPARG is a well-known metabolic regulator.",
		"novelty": 0.6,
		"novelty_reasoning": "The association is known but mechanism is less explored.",
	})

	mock_narrative_msg = AsyncMock()
	mock_narrative_msg.content = [mock_narrative_block]

	mock_score_msg = AsyncMock()
	mock_score_msg.content = [mock_score_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(side_effect=[mock_narrative_msg, mock_score_msg])
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
	assert brief.confidence.graph_evidence == 0.87
	assert brief.confidence.literature_support == 0.78
	assert brief.confidence.biological_plausibility == 0.9
	assert brief.confidence.novelty == 0.6
	assert "binding assay" in brief.suggested_validation.lower()
	assert brief.researcher_narrative == MOCK_NARRATIVE

	assert mock_client.messages.create.call_count == 2
	# First call is researcher reasoning (Sonnet, 4096 tokens)
	first_call = mock_client.messages.create.call_args_list[0].kwargs
	assert first_call["model"] == "claude-sonnet-4-20250514"
	assert first_call["max_tokens"] == 4096


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
