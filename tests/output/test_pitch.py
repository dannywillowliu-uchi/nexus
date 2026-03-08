"""Tests for research pitch generation."""

from unittest.mock import AsyncMock, patch

import pytest

from nexus.output.pitch import _fallback_pitch, _format_brief, _format_validations, generate_full_output, generate_research_pitch


SAMPLE_HYPOTHESIS = {
	"title": "Alzheimer -> APOE via Cholesterol",
	"description": "Alzheimer may be linked to APOE through Cholesterol (ASSOCIATES / INTERACTS)",
	"hypothesis_type": "target_discovery",
	"disease_area": "Alzheimer",
	"novelty_score": 0.85,
	"evidence_score": 0.6,
	"path_strength": 0.7,
	"overall_score": 0.72,
	"abc_path": {
		"a": {"id": "1", "name": "Alzheimer", "type": "Disease"},
		"b": {"id": "2", "name": "Cholesterol", "type": "Drug"},
		"c": {"id": "3", "name": "APOE", "type": "Gene"},
	},
	"intermediaries": [],
	"research_brief": {
		"connection_explanation": "Cholesterol metabolism affects APOE expression",
		"existing_knowledge_comparison": "Novel connection not directly studied",
		"suggested_validation": "Gene expression assay recommended",
		"confidence": {
			"graph_evidence": 0.7,
			"graph_reasoning": "Strong path",
			"literature_support": 0.6,
			"literature_reasoning": "Multiple papers",
			"biological_plausibility": 0.8,
			"plausibility_reasoning": "Known biological mechanism",
			"novelty": 0.85,
			"novelty_reasoning": "Not directly studied",
		},
		"literature_evidence": [
			{"paper_id": "PMC123", "title": "Cholesterol and APOE", "snippet": "Strong link found", "confidence": 0.9},
		],
	},
}


def test_format_brief_none():
	assert "No detailed" in _format_brief(None)


def test_format_brief_with_data():
	text = _format_brief(SAMPLE_HYPOTHESIS["research_brief"])
	assert "Cholesterol metabolism" in text
	assert "PMC123" in text
	assert "graph_evidence" not in text  # field name shouldn't appear raw
	assert "Graph evidence" in text


def test_format_validations_empty():
	assert "No computational" in _format_validations([])


def test_format_validations_with_data():
	validations = [{"tool": "molecular_dock", "status": "success", "confidence_delta": 0.3, "evidence_type": "supporting", "summary": "Binding confirmed"}]
	text = _format_validations(validations)
	assert "molecular_dock" in text
	assert "Binding confirmed" in text


def test_fallback_pitch():
	pitch = _fallback_pitch(SAMPLE_HYPOTHESIS, "The pipeline discovered...")
	assert "## Executive Summary" in pitch
	assert "## Methodology Rationale" in pitch
	assert "## Discovery Process" in pitch
	assert "Alzheimer" in pitch
	assert "Swanson ABC" in pitch


@pytest.mark.asyncio
async def test_generate_research_pitch_no_api_key():
	with patch("nexus.output.pitch.settings") as mock_settings:
		mock_settings.anthropic_api_key = ""
		pitch = await generate_research_pitch(
			SAMPLE_HYPOTHESIS, "The pipeline discovered...", []
		)
		assert "## Executive Summary" in pitch


@pytest.mark.asyncio
async def test_generate_research_pitch_with_api():
	mock_response = AsyncMock()
	mock_response.content = [AsyncMock(text="## Executive Summary\n\nAmazing discovery...")]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_response)

	with patch("nexus.output.pitch.settings") as mock_settings, \
		patch("nexus.output.pitch.anthropic.AsyncAnthropic", return_value=mock_client):
		mock_settings.anthropic_api_key = "test-key"
		pitch = await generate_research_pitch(
			SAMPLE_HYPOTHESIS, "The pipeline discovered...", []
		)
		assert "Alzheimer -> APOE via Cholesterol" in pitch
		assert "Executive Summary" in pitch


@pytest.mark.asyncio
async def test_generate_full_output_no_api_key():
	with patch("nexus.output.pitch.settings") as mock_pitch_settings, \
		patch("nexus.output.narrative.settings") as mock_narr_settings, \
		patch("nexus.output.renderer.settings") as mock_rend_settings:
		mock_pitch_settings.anthropic_api_key = ""
		mock_narr_settings.anthropic_api_key = ""
		mock_rend_settings.anthropic_api_key = ""

		output = await generate_full_output(
			hypothesis=SAMPLE_HYPOTHESIS,
			pipeline_query="Alzheimer treatment",
			pipeline_start_entity="Alzheimer",
			pipeline_start_type="Disease",
			checkpoint_log=[{"stage": "literature", "decision": "continue", "reason": "Good", "confidence": 0.8}],
			pivots=[],
			branches=[],
			validation_results=[],
		)
		assert output.hypothesis_title == "Alzheimer -> APOE via Cholesterol"
		assert len(output.visuals) >= 1  # at least pathway SVG
		assert output.discovery_narrative != ""
		assert "## Executive Summary" in output.pitch_markdown
