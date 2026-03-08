"""Tests for discovery narrative generation."""

from unittest.mock import AsyncMock, patch

import pytest

from nexus.output.narrative import _build_trace_text, _fallback_narrative, generate_discovery_narrative


CHECKPOINT_LOG = [
	{"stage": "literature", "decision": "continue", "reason": "Strong evidence found", "confidence": 0.8},
	{"stage": "graph", "decision": "pivot", "reason": "Low novelty on current path", "confidence": 0.65},
]

PIVOTS = [
	{
		"from_entity": "Alzheimer",
		"to_entity": "Tau Protein",
		"to_type": "Gene",
		"reason": "Low novelty on current path",
		"stage": "graph",
	},
]

VALIDATION_RESULTS = [
	{
		"tool": "molecular_dock",
		"status": "success",
		"confidence_delta": 0.3,
		"evidence_type": "supporting",
		"summary": "Binding affinity confirmed at -8.2 kcal/mol",
	},
]


def test_build_trace_text_full():
	text = _build_trace_text(
		checkpoint_log=CHECKPOINT_LOG,
		pivots=PIVOTS,
		branches=[["branch1"]],
		validation_results=VALIDATION_RESULTS,
		literature_stats={"papers": 12, "triples": 34},
		graph_stats={"hypotheses": 5, "scored": 5},
	)
	assert "LITERATURE STAGE" in text
	assert "12 papers" in text
	assert "CHECKPOINT" in text
	assert "PIVOT" in text
	assert "BRANCH" in text
	assert "VALIDATION" in text
	assert "molecular_dock" in text


def test_build_trace_text_empty():
	text = _build_trace_text([], [], [], [])
	assert text == "No trace data available."


def test_fallback_narrative():
	narrative = _fallback_narrative(
		query="Alzheimer treatment",
		start_entity="Alzheimer",
		checkpoint_log=CHECKPOINT_LOG,
		pivots=PIVOTS,
		validation_results=VALIDATION_RESULTS,
	)
	assert "Alzheimer treatment" in narrative
	assert "continue" in narrative
	assert "pivoted" in narrative
	assert "molecular_dock" in narrative


@pytest.mark.asyncio
async def test_generate_narrative_no_api_key():
	with patch("nexus.output.narrative.settings") as mock_settings:
		mock_settings.anthropic_api_key = ""
		narrative = await generate_discovery_narrative(
			query="Alzheimer treatment",
			start_entity="Alzheimer",
			start_type="Disease",
			checkpoint_log=CHECKPOINT_LOG,
			pivots=PIVOTS,
			branches=[],
			validation_results=VALIDATION_RESULTS,
		)
		assert "Alzheimer" in narrative


@pytest.mark.asyncio
async def test_generate_narrative_with_api():
	mock_response = AsyncMock()
	mock_response.content = [AsyncMock(text="The investigation began with Alzheimer disease...")]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_response)

	with patch("nexus.output.narrative.settings") as mock_settings, \
		patch("nexus.output.narrative.anthropic.AsyncAnthropic", return_value=mock_client):
		mock_settings.anthropic_api_key = "test-key"
		narrative = await generate_discovery_narrative(
			query="Alzheimer treatment",
			start_entity="Alzheimer",
			start_type="Disease",
			checkpoint_log=CHECKPOINT_LOG,
			pivots=PIVOTS,
			branches=[],
			validation_results=VALIDATION_RESULTS,
		)
		assert "Alzheimer" in narrative
		mock_client.messages.create.assert_called_once()
