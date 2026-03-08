"""Tests for SVG rendering."""

from unittest.mock import AsyncMock, patch

import pytest

from nexus.output.renderer import _extract_svg, _fallback_pathway_svg, render_moa_svg, render_pathway_svg


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
}


def test_extract_svg_raw():
	svg = "<svg><rect/></svg>"
	assert _extract_svg(svg) == svg


def test_extract_svg_with_fences():
	text = "```svg\n<svg><rect/></svg>\n```"
	assert _extract_svg(text) == "<svg><rect/></svg>"


def test_extract_svg_with_leading_text():
	text = "Here is the SVG:\n<svg><rect/></svg>"
	assert _extract_svg(text) == "<svg><rect/></svg>"


def test_fallback_pathway_svg():
	svg = _fallback_pathway_svg(SAMPLE_HYPOTHESIS)
	assert "<svg" in svg
	assert "Alzheimer" in svg
	assert "Cholesterol" in svg
	assert "APOE" in svg
	assert "Disease" in svg


@pytest.mark.asyncio
async def test_render_pathway_svg_no_api_key():
	with patch("nexus.output.renderer.settings") as mock_settings:
		mock_settings.anthropic_api_key = ""
		asset = await render_pathway_svg(SAMPLE_HYPOTHESIS)
		assert asset.asset_type == "pathway"
		assert "<svg" in asset.svg
		assert "Alzheimer" in asset.svg


@pytest.mark.asyncio
async def test_render_pathway_svg_with_api():
	mock_response = AsyncMock()
	mock_response.content = [AsyncMock(text="<svg><circle r='50'/></svg>")]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_response)

	with patch("nexus.output.renderer.settings") as mock_settings, \
		patch("nexus.output.renderer.anthropic.AsyncAnthropic", return_value=mock_client):
		mock_settings.anthropic_api_key = "test-key"
		asset = await render_pathway_svg(SAMPLE_HYPOTHESIS)
		assert asset.asset_type == "pathway"
		assert "<svg>" in asset.svg
		mock_client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_render_moa_svg_no_brief():
	hypothesis = {**SAMPLE_HYPOTHESIS}
	with patch("nexus.output.renderer.settings") as mock_settings:
		mock_settings.anthropic_api_key = "test-key"
		result = await render_moa_svg(hypothesis)
		assert result is None


@pytest.mark.asyncio
async def test_render_moa_svg_with_brief():
	hypothesis = {
		**SAMPLE_HYPOTHESIS,
		"research_brief": {
			"connection_explanation": "Cholesterol metabolism affects APOE expression",
		},
	}
	mock_response = AsyncMock()
	mock_response.content = [AsyncMock(text="<svg><text>MOA</text></svg>")]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_response)

	with patch("nexus.output.renderer.settings") as mock_settings, \
		patch("nexus.output.renderer.anthropic.AsyncAnthropic", return_value=mock_client):
		mock_settings.anthropic_api_key = "test-key"
		result = await render_moa_svg(hypothesis)
		assert result is not None
		assert result.asset_type == "mechanism"
		assert "<svg>" in result.svg
