from unittest.mock import AsyncMock, MagicMock, patch

from nexus.tools.generate_protocol import generate_protocol


MOCK_CLAUDE_RESPONSE_TEXT = """{
  "objective": "Test the BRCA1-p53-breast cancer connection",
  "materials": ["Cell lines", "BRCA1 antibodies", "Western blot reagents"],
  "steps": ["Step 1: Culture cells", "Step 2: Knockdown BRCA1", "Step 3: Measure p53 levels"],
  "controls": {"positive": "Known BRCA1 mutant", "negative": "Wild-type cells"},
  "expected_results": "BRCA1 knockdown should increase p53 activity",
  "timeline": "2-3 weeks",
  "safety": "Standard BSL-2 precautions"
}"""


@patch("nexus.tools.generate_protocol.settings")
async def test_generate_protocol_no_api_key(mock_settings):
	mock_settings.anthropic_api_key = ""

	hypothesis = {
		"a_name": "BRCA1",
		"b_name": "p53",
		"c_name": "breast cancer",
		"ab_relationship": "REGULATES",
		"bc_relationship": "ASSOCIATES",
	}

	result = await generate_protocol(hypothesis)

	assert result.status == "partial"
	assert result.confidence_delta == 0.0
	assert result.raw_data["reason"] == "missing_api_key"


@patch("nexus.tools.generate_protocol.anthropic.AsyncAnthropic")
@patch("nexus.tools.generate_protocol.settings")
async def test_generate_protocol_success(mock_settings, mock_anthropic_cls):
	mock_settings.anthropic_api_key = "test-key"

	# Build mock message response
	mock_content_block = MagicMock()
	mock_content_block.text = MOCK_CLAUDE_RESPONSE_TEXT
	mock_message = MagicMock()
	mock_message.content = [mock_content_block]

	mock_client = MagicMock()
	mock_client.messages.create = AsyncMock(return_value=mock_message)
	mock_anthropic_cls.return_value = mock_client

	hypothesis = {
		"a_name": "BRCA1",
		"b_name": "p53",
		"c_name": "breast cancer",
		"ab_relationship": "REGULATES",
		"bc_relationship": "ASSOCIATES",
	}

	result = await generate_protocol(hypothesis)

	assert result.status == "success"
	assert result.confidence_delta == 0.0
	assert result.evidence_type == "neutral"
	assert "BRCA1" in result.summary
	assert result.raw_data["protocol"] == MOCK_CLAUDE_RESPONSE_TEXT
	assert result.raw_data["hypothesis"]["a_name"] == "BRCA1"

	# Verify Claude was called with correct params
	mock_client.messages.create.assert_called_once()
	call_kwargs = mock_client.messages.create.call_args[1]
	assert call_kwargs["model"] == "claude-sonnet-4-20250514"
	assert "BRCA1" in call_kwargs["messages"][0]["content"]


@patch("nexus.tools.generate_protocol.anthropic.AsyncAnthropic")
@patch("nexus.tools.generate_protocol.settings")
async def test_generate_protocol_api_error(mock_settings, mock_anthropic_cls):
	import anthropic

	mock_settings.anthropic_api_key = "test-key"

	mock_client = MagicMock()
	mock_client.messages.create = AsyncMock(
		side_effect=anthropic.APIError(
			message="Rate limited",
			request=MagicMock(),
			body=None,
		)
	)
	mock_anthropic_cls.return_value = mock_client

	hypothesis = {"a_name": "A", "b_name": "B", "c_name": "C"}
	result = await generate_protocol(hypothesis)

	assert result.status == "error"
	assert result.confidence_delta == 0.0
