from nexus.tools.schema import ToolResponse


def test_tool_response_defaults():
	resp = ToolResponse(
		status="success",
		confidence_delta=0.5,
		evidence_type="supporting",
		summary="Test summary",
	)
	assert resp.status == "success"
	assert resp.confidence_delta == 0.5
	assert resp.evidence_type == "supporting"
	assert resp.summary == "Test summary"
	assert resp.raw_data == {}


def test_tool_response_with_raw_data():
	resp = ToolResponse(
		status="error",
		confidence_delta=-0.3,
		evidence_type="contradicting",
		summary="Something failed",
		raw_data={"error": "timeout", "code": 408},
	)
	assert resp.status == "error"
	assert resp.confidence_delta == -0.3
	assert resp.evidence_type == "contradicting"
	assert resp.raw_data == {"error": "timeout", "code": 408}


def test_tool_response_partial_status():
	resp = ToolResponse(
		status="partial",
		confidence_delta=0.0,
		evidence_type="neutral",
		summary="Partial result",
		raw_data={"reason": "missing_api_key"},
	)
	assert resp.status == "partial"
	assert resp.confidence_delta == 0.0
	assert resp.evidence_type == "neutral"


def test_tool_response_raw_data_independent():
	"""Ensure raw_data default factory creates independent dicts."""
	resp1 = ToolResponse(status="success", confidence_delta=0.0, evidence_type="neutral", summary="A")
	resp2 = ToolResponse(status="success", confidence_delta=0.0, evidence_type="neutral", summary="B")
	resp1.raw_data["key"] = "value"
	assert "key" not in resp2.raw_data
