from unittest.mock import patch

import httpx
import pytest

from nexus.agents.viz_agent import run_viz_agent
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


MOCK_ICON_RESPONSE = {
	"icons": [
		{"url": "https://api.biorender.com/icons/disease-001.svg", "name": "Disease"},
		{"url": "https://api.biorender.com/icons/disease-002.svg", "name": "Disease 2"},
	]
}


@pytest.mark.asyncio
@patch("nexus.agents.viz_agent.settings")
async def test_run_viz_agent_no_api_key(mock_settings):
	"""Without BIORENDER_API_KEY, returns fallback with text-only labels."""
	mock_settings.biorender_api_key = ""

	hypothesis = _make_hypothesis()
	result = await run_viz_agent(hypothesis)

	assert result["fallback"] is True
	assert result["hypothesis_id"] == "D001-G001-C001"
	assert len(result["nodes"]) == 3
	for node in result["nodes"]:
		assert node["icon_url"] is None
	assert result["pivot_trail"] is None


@pytest.mark.asyncio
@patch("nexus.agents.viz_agent.settings")
async def test_run_viz_agent_with_mocked_api(mock_settings, httpx_mock):
	"""With API key and mocked BioRender responses, returns proper icon URLs."""
	mock_settings.biorender_api_key = "test-biorender-key"

	# Mock responses for each unique entity type (Disease, Gene, Compound)
	disease_response = {"icons": [{"url": "https://biorender.com/icons/disease.svg", "name": "Disease"}]}
	gene_response = {"icons": [{"url": "https://biorender.com/icons/gene.svg", "name": "Gene"}]}
	compound_response = {"icons": [{"url": "https://biorender.com/icons/compound.svg", "name": "Compound"}]}

	httpx_mock.add_response(
		url=httpx.URL("https://api.biorender.com/v1/icons/search", params={"query": "Disease", "limit": "5"}),
		json=disease_response,
	)
	httpx_mock.add_response(
		url=httpx.URL("https://api.biorender.com/v1/icons/search", params={"query": "Gene", "limit": "5"}),
		json=gene_response,
	)
	httpx_mock.add_response(
		url=httpx.URL("https://api.biorender.com/v1/icons/search", params={"query": "Compound", "limit": "5"}),
		json=compound_response,
	)

	hypothesis = _make_hypothesis()
	result = await run_viz_agent(hypothesis)

	assert result["fallback"] is False
	assert result["hypothesis_id"] == "D001-G001-C001"

	# Check icon URLs are assigned
	node_map = {n["id"]: n for n in result["nodes"]}
	assert node_map["D001"]["icon_url"] == "https://biorender.com/icons/disease.svg"
	assert node_map["G001"]["icon_url"] == "https://biorender.com/icons/gene.svg"
	assert node_map["C001"]["icon_url"] == "https://biorender.com/icons/compound.svg"


@pytest.mark.asyncio
@patch("nexus.agents.viz_agent.settings")
async def test_run_viz_agent_with_pivot_trail(mock_settings):
	"""Pivot trail is included in the output when provided."""
	mock_settings.biorender_api_key = ""

	hypothesis = _make_hypothesis()
	trail = [
		{"entity": "TNF", "type": "Gene", "reason": "inflammatory mediator"},
		{"entity": "IL-6", "type": "Gene", "reason": "cytokine signaling"},
	]

	result = await run_viz_agent(hypothesis, pivot_trail=trail)

	assert result["pivot_trail"] is not None
	assert len(result["pivot_trail"]) == 2
	assert result["pivot_trail"][0]["entity"] == "TNF"
	assert result["pivot_trail"][1]["reason"] == "cytokine signaling"


@pytest.mark.asyncio
@patch("nexus.agents.viz_agent.settings")
async def test_run_viz_agent_builds_correct_edges(mock_settings):
	"""Edges correctly reflect the A->B and B->C relationships."""
	mock_settings.biorender_api_key = ""

	hypothesis = _make_hypothesis(
		a_id="D002",
		b_id="G002",
		c_id="C002",
		ab_relationship="LOCALIZES_DlA",
		bc_relationship="EXPRESSES_AeG",
	)

	result = await run_viz_agent(hypothesis)

	assert len(result["edges"]) == 2
	ab_edge = result["edges"][0]
	bc_edge = result["edges"][1]

	assert ab_edge["source"] == "D002"
	assert ab_edge["target"] == "G002"
	assert ab_edge["relationship"] == "LOCALIZES_DlA"

	assert bc_edge["source"] == "G002"
	assert bc_edge["target"] == "C002"
	assert bc_edge["relationship"] == "EXPRESSES_AeG"
