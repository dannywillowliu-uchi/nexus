from unittest.mock import AsyncMock, patch

from nexus.db.models import SessionRequest
from nexus.graph.abc import ABCHypothesis
from nexus.harness.event_store import EventStore
from nexus.harness.runner import run_research_session
from nexus.pipeline.orchestrator import PipelineResult, PipelineStep


def _make_hypothesis() -> ABCHypothesis:
	return ABCHypothesis(
		a_id="D001",
		a_name="Alzheimer",
		a_type="Disease",
		b_id="G001",
		b_name="APOE",
		b_type="Gene",
		c_id="C001",
		c_name="Donepezil",
		c_type="Compound",
		ab_relationship="ASSOCIATES",
		bc_relationship="BINDS",
		path_count=3,
		novelty_score=0.95,
		path_strength=0.87,
	)


def _make_scored_hypothesis() -> dict:
	return {
		"title": "Alzheimer -> Donepezil via APOE",
		"description": "Alzheimer may be linked to Donepezil through APOE",
		"disease_area": "Alzheimer",
		"hypothesis_type": "drug_repurposing",
		"novelty_score": 0.95,
		"evidence_score": 0.4,
		"path_strength": 0.87,
		"overall_score": 0.75,
		"abc_path": {
			"a": {"id": "D001", "name": "Alzheimer", "type": "Disease"},
			"b": {"id": "G001", "name": "APOE", "type": "Gene"},
			"c": {"id": "C001", "name": "Donepezil", "type": "Compound"},
		},
		"intermediaries": [],
	}


def _make_pipeline_result() -> PipelineResult:
	hyp = _make_hypothesis()
	scored = _make_scored_hypothesis()
	return PipelineResult(
		query="Alzheimer drug repurposing",
		start_entity="Alzheimer",
		start_type="Disease",
		step=PipelineStep.COMPLETED,
		literature_result=None,
		hypotheses=[hyp],
		scored_hypotheses=[scored],
		pivots=[],
	)


def _make_request() -> SessionRequest:
	return SessionRequest(
		query="Alzheimer drug repurposing",
		disease_area="Alzheimer",
		start_entity="Alzheimer",
		start_type="Disease",
		target_types=["Compound"],
		max_hypotheses=10,
	)


@patch("nexus.harness.runner.write_session_log")
@patch("nexus.harness.runner.generate_quick_summaries", new_callable=AsyncMock)
@patch("nexus.harness.runner.run_validation_agent", new_callable=AsyncMock)
@patch("nexus.harness.runner.run_pipeline", new_callable=AsyncMock)
async def test_run_research_session_basic(
	mock_run_pipeline,
	mock_run_validation,
	mock_generate_summaries,
	mock_write_log,
):
	pipeline_result = _make_pipeline_result()
	mock_run_pipeline.return_value = pipeline_result
	mock_run_validation.return_value = {
		"verdict": "validated",
		"confidence": 0.8,
		"tool_results": [],
		"reasoning": "Strong evidence",
	}
	mock_generate_summaries.return_value = ["Alzheimer connects to Donepezil via APOE."]

	event_store = EventStore()
	request = _make_request()

	result = await run_research_session(
		session_id="test-session-1",
		request=request,
		event_store=event_store,
	)

	# Verify structure
	assert result["session_id"] == "test-session-1"
	assert isinstance(result["hypotheses"], list)
	assert len(result["hypotheses"]) == 1
	assert result["pivot_count"] == 0
	assert result["events_count"] > 0

	# Verify each step was called
	mock_run_pipeline.assert_called_once()
	mock_run_validation.assert_called_once()
	mock_generate_summaries.assert_called_once()
	mock_write_log.assert_called_once()

	# Verify hypothesis has validation result and summary
	hyp = result["hypotheses"][0]
	assert hyp["validation_result"]["verdict"] == "validated"
	assert hyp["summary"] == "Alzheimer connects to Donepezil via APOE."


@patch("nexus.harness.runner.write_session_log")
@patch("nexus.harness.runner.generate_quick_summaries", new_callable=AsyncMock)
@patch("nexus.harness.runner.run_validation_agent", new_callable=AsyncMock)
@patch("nexus.harness.runner.run_pipeline", new_callable=AsyncMock)
async def test_run_research_session_emits_events(
	mock_run_pipeline,
	mock_run_validation,
	mock_generate_summaries,
	mock_write_log,
):
	pipeline_result = _make_pipeline_result()
	mock_run_pipeline.return_value = pipeline_result
	mock_run_validation.return_value = {
		"verdict": "inconclusive",
		"confidence": 0.0,
		"tool_results": [],
		"reasoning": "No API key",
	}
	mock_generate_summaries.return_value = ["Summary"]

	event_store = EventStore()
	request = _make_request()

	await run_research_session(
		session_id="test-session-2",
		request=request,
		event_store=event_store,
	)

	# Check that session_created and session_completed events are present
	session_events = event_store.get_by_session("test-session-2")
	event_types = [e.event_type for e in session_events]

	assert "session_created" in event_types
	assert "session_completed" in event_types

	# session_created should be the first event
	assert session_events[0].event_type == "session_created"
	# session_completed should be the last event
	assert session_events[-1].event_type == "session_completed"
