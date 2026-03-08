from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.graph.abc import ABCHypothesis
from nexus.harness.event_store import EventStore
from nexus.harness.harness import Harness
from nexus.harness.models import HarnessConfig
from nexus.harness.validation_agent import (
	_build_hypothesis_context,
	_build_prior_results_context,
	_parse_tool_decision,
	run_validation_agent,
)
from nexus.tools.schema import ToolResponse


def _make_hypothesis() -> ABCHypothesis:
	return ABCHypothesis(
		a_id="D001",
		a_name="Alzheimer's Disease",
		a_type="Disease",
		b_id="G001",
		b_name="APOE",
		b_type="Gene",
		c_id="C001",
		c_name="Donepezil",
		c_type="Compound",
		ab_relationship="ASSOCIATES_DaG",
		bc_relationship="BINDS_CbG",
		path_count=5,
		novelty_score=0.95,
		path_strength=0.87,
	)


@pytest.fixture
def harness_setup():
	config = HarnessConfig(max_iterations_per_hypothesis=5, max_total_tool_calls=20)
	store = EventStore()
	harness = Harness(config, store)
	return harness, store


def test_build_hypothesis_context():
	hyp = _make_hypothesis()
	ctx = _build_hypothesis_context(hyp, "drug_repurposing")
	assert "Alzheimer's Disease" in ctx
	assert "drug_repurposing" in ctx
	assert "APOE" in ctx
	assert "Donepezil" in ctx


def test_build_prior_results_context_empty():
	ctx = _build_prior_results_context([])
	assert ctx == "No prior tool results."


def test_build_prior_results_context_with_results():
	results = [
		{
			"tool_name": "compound_lookup",
			"status": "success",
			"evidence_type": "supporting",
			"confidence_delta": 0.1,
			"summary": "Found compound",
		}
	]
	ctx = _build_prior_results_context(results)
	assert "compound_lookup" in ctx
	assert "supporting" in ctx


def test_parse_tool_decision_plain_json():
	text = '{"tool_name": "compound_lookup", "arguments": {"compound_name": "aspirin"}, "reasoning": "test"}'
	result = _parse_tool_decision(text)
	assert result["tool_name"] == "compound_lookup"
	assert result["arguments"]["compound_name"] == "aspirin"


def test_parse_tool_decision_markdown_block():
	text = '```json\n{"tool_name": "pathway_overlap", "arguments": {}, "reasoning": "test"}\n```'
	result = _parse_tool_decision(text)
	assert result["tool_name"] == "pathway_overlap"


def test_parse_tool_decision_embedded_json():
	text = 'I think we should use this tool: {"tool_name": "molecular_dock", "arguments": {}, "reasoning": "test"} because...'
	result = _parse_tool_decision(text)
	assert result["tool_name"] == "molecular_dock"


def test_parse_tool_decision_invalid():
	result = _parse_tool_decision("no json here")
	assert result == {}


async def test_run_validation_agent_no_api_key(harness_setup):
	harness, store = harness_setup
	hyp = _make_hypothesis()

	with patch("nexus.harness.validation_agent.settings") as mock_settings:
		mock_settings.anthropic_api_key = ""
		result = await run_validation_agent(
			hypothesis=hyp,
			hypothesis_type="drug_repurposing",
			session_id="s1",
			hypothesis_id="h1",
			harness=harness,
			event_store=store,
		)

	assert result["verdict"] == "inconclusive"
	assert result["confidence"] == 0.0
	assert result["tool_results"] == []
	assert result["reasoning"] == "No API key"


async def test_run_validation_agent_with_mocked_claude(harness_setup):
	harness, store = harness_setup
	hyp = _make_hypothesis()

	# Mock tool that returns supporting evidence
	mock_tool = AsyncMock(return_value=ToolResponse(
		status="success",
		confidence_delta=0.3,
		evidence_type="supporting",
		summary="Found supporting evidence",
		raw_data={"result": "positive"},
	))

	mock_registry = {
		"compound_lookup": mock_tool,
		"molecular_dock": mock_tool,
		"literature_validate": mock_tool,
	}

	# Track call count to alternate tool suggestions
	call_count = {"n": 0}
	tool_sequence = ["compound_lookup", "molecular_dock", "literature_validate"]

	def make_response(tool_name: str):
		mock_content = MagicMock()
		mock_content.text = f'{{"tool_name": "{tool_name}", "arguments": {{}}, "reasoning": "test"}}'
		mock_resp = MagicMock()
		mock_resp.content = [mock_content]
		return mock_resp

	async def mock_create(**kwargs):
		idx = min(call_count["n"], len(tool_sequence) - 1)
		tool_name = tool_sequence[idx]
		call_count["n"] += 1
		return make_response(tool_name)

	mock_client_instance = MagicMock()
	mock_client_instance.messages = MagicMock()
	mock_client_instance.messages.create = mock_create

	with (
		patch("nexus.harness.validation_agent.settings") as mock_settings,
		patch("nexus.harness.validation_agent.TOOL_REGISTRY", mock_registry),
		patch("anthropic.AsyncAnthropic", return_value=mock_client_instance),
	):
		mock_settings.anthropic_api_key = "test-key"
		result = await run_validation_agent(
			hypothesis=hyp,
			hypothesis_type="drug_repurposing",
			session_id="s1",
			hypothesis_id="h1",
			harness=harness,
			event_store=store,
		)

	assert result["verdict"] == "validated"
	assert result["confidence"] > 0
	assert len(result["tool_results"]) >= 2
	assert result["reasoning"] != ""
