import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.cloudlab.protocol_agent import run_protocol_agent
from nexus.graph.abc import ABCHypothesis


def _make_hypothesis(**overrides) -> ABCHypothesis:
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


MOCK_AUTOPROTOCOL = json.dumps({
	"refs": {"plate": {"new": "96-pcr", "store": {"where": "cold_4"}}},
	"instructions": [
		{"op": "pipette", "groups": [{"transfer": [{"from": "plate/A1", "to": "plate/B1", "volume": "10:microliter"}]}]},
	],
})


@pytest.mark.asyncio
@patch("nexus.cloudlab.protocol_agent.settings")
async def test_run_protocol_agent_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	hypothesis = _make_hypothesis()
	mock_provider = AsyncMock()

	result = await run_protocol_agent(hypothesis, "drug_repurposing", mock_provider)

	assert result is None
	mock_provider.validate_protocol.assert_not_called()
	mock_provider.submit_experiment.assert_not_called()


@pytest.mark.asyncio
@patch("nexus.cloudlab.protocol_agent.anthropic.AsyncAnthropic")
@patch("nexus.cloudlab.protocol_agent.settings")
async def test_run_protocol_agent_success(mock_settings, mock_anthropic_cls):
	mock_settings.anthropic_api_key = "test-key"

	# Mock Claude response
	mock_content_block = MagicMock()
	mock_content_block.text = MOCK_AUTOPROTOCOL

	mock_message = MagicMock()
	mock_message.content = [mock_content_block]

	mock_client = MagicMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	# Mock provider
	mock_provider = AsyncMock()
	mock_provider.validate_protocol = AsyncMock(return_value={"valid": True})
	from nexus.cloudlab.provider import ExperimentSubmission
	mock_submission = ExperimentSubmission(
		submission_id="run_test123",
		provider="strateos",
		status="submitted",
	)
	mock_provider.submit_experiment = AsyncMock(return_value=mock_submission)

	hypothesis = _make_hypothesis()
	result = await run_protocol_agent(hypothesis, "drug_repurposing", mock_provider)

	assert result is not None
	assert result.submission_id == "run_test123"
	assert result.provider == "strateos"
	assert result.status == "submitted"

	# Verify Claude was called
	mock_client.messages.create.assert_called_once()
	call_kwargs = mock_client.messages.create.call_args.kwargs
	assert call_kwargs["model"] == "claude-sonnet-4-20250514"
	assert "Diabetes" in call_kwargs["messages"][0]["content"]
	assert "PPARG" in call_kwargs["messages"][0]["content"]
	assert "Metformin" in call_kwargs["messages"][0]["content"]

	# Verify provider was called
	mock_provider.validate_protocol.assert_called_once()
	mock_provider.submit_experiment.assert_called_once()
