from unittest.mock import AsyncMock, patch

from nexus.agents.literature.agent import LiteratureResult
from nexus.agents.literature.extract import Triple
from nexus.checkpoint.models import CheckpointDecision, CheckpointResult
from nexus.graph.abc import ABCHypothesis
from nexus.graph.client import ResolvedEntity
from nexus.pipeline.orchestrator import PipelineStep, score_hypothesis, run_pipeline


def _mock_resolve_multi(name: str = "Alzheimer", resolved_name: str = "Alzheimer", entity_type: str = "Disease"):
	"""Create an AsyncMock for graph_client.resolve_entity_multi that returns a single candidate."""
	mock = AsyncMock(return_value=[ResolvedEntity(
		name=resolved_name,
		type=entity_type,
		identifier="",
		match_method="exact",
		original_query=name,
	)])
	return mock


MOCK_TRIPLES = [
	Triple(
		subject="Alzheimer",
		subject_type="Disease",
		predicate="associated_with",
		object="APOE",
		object_type="Gene",
		confidence=0.9,
		source_paper_id="1",
	),
	Triple(
		subject="APOE",
		subject_type="Gene",
		predicate="interacts_with",
		object="Donepezil",
		object_type="Compound",
		confidence=0.85,
		source_paper_id="2",
	),
]

MOCK_LIT_RESULT = LiteratureResult(
	papers=[],
	triples=MOCK_TRIPLES,
	errors=[],
)

MOCK_HYPOTHESIS = ABCHypothesis(
	a_id="1",
	a_name="Alzheimer",
	a_type="Disease",
	b_id="2",
	b_name="APOE",
	b_type="Gene",
	c_id="3",
	c_name="Donepezil",
	c_type="Compound",
	ab_relationship="ASSOCIATES",
	bc_relationship="BINDS",
	path_count=3,
	novelty_score=0.95,
	path_strength=0.87,
	intermediaries=[],
)

CONTINUE_RESULT = CheckpointResult(
	decision=CheckpointDecision.CONTINUE,
	reason="On track",
	confidence=0.8,
)


def test_score_hypothesis():
	scored = score_hypothesis(MOCK_HYPOTHESIS, MOCK_TRIPLES)

	assert scored["hypothesis_type"] == "drug_repurposing"
	assert scored["novelty_score"] == 0.95
	assert scored["path_strength"] == 0.87
	# 2 triples mention path entities -> evidence = 2/5 = 0.4
	assert scored["evidence_score"] == 0.4
	# overall = 0.95*0.3 + 0.4*0.4 + 0.87*0.3 = 0.285 + 0.16 + 0.261 = 0.706
	assert scored["overall_score"] == 0.706
	assert scored["abc_path"]["a"]["name"] == "Alzheimer"
	assert scored["abc_path"]["c"]["name"] == "Donepezil"
	assert scored["title"] == "Alzheimer -> Donepezil via APOE"


def test_score_hypothesis_comorbidity():
	abc = ABCHypothesis(
		a_id="1", a_name="Diabetes", a_type="Disease",
		b_id="2", b_name="IL6", b_type="Gene",
		c_id="3", c_name="Alzheimer", c_type="Disease",
		ab_relationship="ASSOCIATES", bc_relationship="ASSOCIATES",
		path_count=5, novelty_score=0.95, path_strength=0.85,
		intermediaries=[],
	)
	scored = score_hypothesis(abc, [])
	assert scored["hypothesis_type"] == "comorbidity"


def test_score_hypothesis_mechanism():
	abc = ABCHypothesis(
		a_id="1", a_name="Diabetes", a_type="Disease",
		b_id="2", b_name="INS", b_type="Gene",
		c_id="3", c_name="Insulin Signaling", c_type="BiologicalProcess",
		ab_relationship="ASSOCIATES", bc_relationship="PARTICIPATES",
		path_count=4, novelty_score=0.95, path_strength=0.8,
		intermediaries=[],
	)
	scored = score_hypothesis(abc, [])
	assert scored["hypothesis_type"] == "mechanism"


@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_basic(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc):
	mock_lit.return_value = MOCK_LIT_RESULT
	mock_abc.return_value = [MOCK_HYPOTHESIS]
	mock_cp.return_value = CONTINUE_RESULT
	mock_merge.return_value = 2
	mock_gc.resolve_entity_multi = _mock_resolve_multi()

	result = await run_pipeline(
		query="Alzheimer disease treatments",
		start_entity="Alzheimer",
		start_type="Disease",
		target_types=["Compound"],
	)

	assert result.step == PipelineStep.COMPLETED
	assert len(result.scored_hypotheses) >= 1
	assert result.scored_hypotheses[0]["hypothesis_type"] == "drug_repurposing"
	assert result.errors == []
	assert len(result.checkpoint_log) == 2
	mock_lit.assert_awaited_once()
	mock_merge.assert_awaited_once()


@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_with_pivot(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc):
	pivot_result = CheckpointResult(
		decision=CheckpointDecision.PIVOT,
		reason="APOE is more specific",
		pivot_entity="APOE",
		pivot_entity_type="Gene",
		confidence=0.9,
	)

	# First checkpoint returns PIVOT, rest return CONTINUE
	mock_cp.side_effect = [pivot_result, CONTINUE_RESULT]
	mock_lit.return_value = MOCK_LIT_RESULT
	mock_abc.return_value = [MOCK_HYPOTHESIS]
	mock_merge.return_value = 2
	mock_gc.resolve_entity_multi = _mock_resolve_multi(name="APOE", resolved_name="APOE", entity_type="Gene")

	result = await run_pipeline(
		query="Alzheimer disease",
		start_entity="Alzheimer",
		start_type="Disease",
		target_types=["Compound"],
		max_pivots=3,
	)

	assert result.step == PipelineStep.COMPLETED
	assert len(result.pivots) == 1
	assert result.pivots[0]["to_entity"] == "APOE"
	assert result.pivots[0]["stage"] == "literature"
	assert result.errors == []


@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_on_event(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc):
	mock_lit.return_value = MOCK_LIT_RESULT
	mock_abc.return_value = [MOCK_HYPOTHESIS]
	mock_cp.return_value = CONTINUE_RESULT
	mock_merge.return_value = 2
	mock_gc.resolve_entity_multi = _mock_resolve_multi()

	events: list[tuple[str, dict]] = []

	async def capture_event(event_type: str, data: dict) -> None:
		events.append((event_type, data))

	await run_pipeline(
		query="Alzheimer",
		start_entity="Alzheimer",
		target_types=["Compound"],
		on_event=capture_event,
	)

	event_types = [e[0] for e in events]
	assert "stage_start" in event_types
	assert "stage_complete" in event_types
	assert "triples_merged" in event_types
	assert "entity_resolved" in event_types
	assert "pipeline_complete" in event_types


@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_graph_pivot(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc):
	"""Checkpoint after graph stage returns PIVOT, triggering re-run."""
	graph_pivot = CheckpointResult(
		decision=CheckpointDecision.PIVOT,
		reason="Try BACE1 instead",
		pivot_entity="BACE1",
		pivot_entity_type="Gene",
		confidence=0.85,
	)

	# literature checkpoint -> CONTINUE, graph checkpoint -> PIVOT
	mock_cp.side_effect = [CONTINUE_RESULT, graph_pivot]
	mock_lit.return_value = MOCK_LIT_RESULT
	mock_abc.return_value = [MOCK_HYPOTHESIS]
	mock_merge.return_value = 2
	mock_gc.resolve_entity_multi = _mock_resolve_multi()

	result = await run_pipeline(
		query="Alzheimer",
		start_entity="Alzheimer",
		target_types=["Compound"],
	)

	assert result.step == PipelineStep.COMPLETED
	assert len(result.pivots) == 1
	assert result.pivots[0]["to_entity"] == "BACE1"
	assert result.pivots[0]["stage"] == "graph"
	# run_literature_agent called twice: initial + pivot re-run
	assert mock_lit.await_count == 2
