from unittest.mock import AsyncMock, MagicMock, patch

from nexus.checkpoint.agent import run_checkpoint
from nexus.checkpoint.models import CheckpointContext, CheckpointDecision


def _make_context(**overrides) -> CheckpointContext:
	defaults = {
		"stage": "literature",
		"original_query": "BRCA1 breast cancer",
		"current_entity": "BRCA1",
		"current_entity_type": "Gene",
		"pivot_count": 0,
		"max_pivots": 3,
	}
	defaults.update(overrides)
	return CheckpointContext(**defaults)


@patch("nexus.checkpoint.agent.settings")
async def test_checkpoint_continue(mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	mock_message = MagicMock()
	mock_message.content = [MagicMock(text='{"decision": "continue", "reason": "On track", "confidence": 0.8}')]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)

	with patch("nexus.checkpoint.agent.anthropic.AsyncAnthropic", return_value=mock_client):
		result = await run_checkpoint(_make_context())

	assert result.decision == CheckpointDecision.CONTINUE
	assert result.reason == "On track"
	assert result.confidence == 0.8
	assert result.pivot_entity is None


@patch("nexus.checkpoint.agent.settings")
async def test_checkpoint_pivot_budget_exhausted(mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	ctx = _make_context(pivot_count=3, max_pivots=3)
	result = await run_checkpoint(ctx)

	assert result.decision == CheckpointDecision.CONTINUE
	assert "budget exhausted" in result.reason.lower()
	assert result.confidence == 1.0


@patch("nexus.checkpoint.agent.settings")
async def test_checkpoint_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	ctx = _make_context()
	result = await run_checkpoint(ctx)

	assert result.decision == CheckpointDecision.CONTINUE
	assert "no api key" in result.reason.lower()
	assert result.confidence == 0.5
