from unittest.mock import AsyncMock, patch

import pytest

from nexus.agents.literature.agent import LiteratureResult
from nexus.agents.literature.extract import Triple
from nexus.checkpoint.models import CheckpointDecision, CheckpointResult
from nexus.graph.abc import ABCHypothesis
from nexus.graph.client import ResolvedEntity
from nexus.output.models import ResearchOutput, VisualAsset
from nexus.pipeline.orchestrator import PipelineStep, score_hypothesis, run_pipeline
from nexus.tools.schema import ToolResponse


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


@patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment"))
@patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip"))
@patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_basic(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc, _mock_sum, _mock_brief, _mock_val, _mock_exp):
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


@patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment"))
@patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip"))
@patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_with_pivot(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc, _mock_sum, _mock_brief, _mock_val, _mock_exp):
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


@patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment"))
@patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip"))
@patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_on_event(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc, _mock_sum, _mock_brief, _mock_val, _mock_exp):
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


@patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment"))
@patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip"))
@patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_graph_pivot(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc, _mock_sum, _mock_brief, _mock_val, _mock_exp):
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


@patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment"))
@patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip"))
@patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock, return_value=[])
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_branch_bounded(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc, _mock_sum, _mock_brief, _mock_val, _mock_exp):
	"""BRANCH decision runs lightweight graph-only branches, max 3 concurrent."""
	branch_result = CheckpointResult(
		decision=CheckpointDecision.BRANCH,
		reason="Explore BACE1 and TREM2 in parallel",
		pivot_entity="BACE1",
		pivot_entity_type="Gene",
		branch_entities=[
			{"name": "BACE1", "type": "Gene"},
			{"name": "TREM2", "type": "Gene"},
		],
		confidence=0.85,
	)

	mock_cp.side_effect = [branch_result, CONTINUE_RESULT]
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
	assert len(result.branches) >= 1
	assert len(result.scored_hypotheses) >= 1


@pytest.mark.asyncio
async def test_run_pipeline_validation_uses_planner():
	"""Validation stage calls run_validation_plan for each top hypothesis."""
	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock) as mock_brief, \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock) as mock_validate, \
		 patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment")):

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="continue",
			confidence=0.8,
		)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])

		mock_abc.return_value = [
			ABCHypothesis(
				a_id="D1", a_name="RA", a_type="Disease",
				b_id="G1", b_name="TNF", b_type="Gene",
				c_id="C1", c_name="Drug1", c_type="Drug",
				ab_relationship="ASSOCIATES", bc_relationship="TARGET",
				path_count=3, novelty_score=0.9,
			)
		]
		mock_sum.return_value = ["summary1"]
		mock_brief.side_effect = Exception("skip brief")

		mock_validate.return_value = [
			ToolResponse(
				status="success",
				confidence_delta=0.3,
				evidence_type="supporting",
				summary="diffdock completed",
				raw_data={"tool_type": "diffdock"},
			)
		]

		result = await run_pipeline("test query", start_entity="RA", start_type="Disease")

	assert mock_validate.called
	assert len(result.validation_results) > 0


@pytest.mark.asyncio
async def test_run_pipeline_validation_reranks():
	"""Validation results feed back into overall_score and re-rank hypotheses."""
	hyp_strong = ABCHypothesis(
		a_id="D1", a_name="RA", a_type="Disease",
		b_id="G1", b_name="TNF", b_type="Gene",
		c_id="C1", c_name="Drug1", c_type="Drug",
		ab_relationship="ASSOCIATED_WITH", bc_relationship="TARGET",
		path_count=3, novelty_score=0.7, path_strength=0.5,
	)
	hyp_weak = ABCHypothesis(
		a_id="D1", a_name="RA", a_type="Disease",
		b_id="G2", b_name="IL6", b_type="Gene",
		c_id="C2", c_name="Drug2", c_type="Drug",
		ab_relationship="ASSOCIATED_WITH", bc_relationship="TARGET",
		path_count=5, novelty_score=0.9, path_strength=0.8,
	)

	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock) as mock_brief, \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock) as mock_validate, \
		 patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock) as mock_merge, \
		 patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock, side_effect=Exception("skip experiment")):

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(
			decision=CheckpointDecision.CONTINUE, reason="ok", confidence=0.8,
		)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])
		mock_merge.return_value = 0

		# hyp_weak has higher base score, hyp_strong has lower base score
		mock_abc.return_value = [hyp_weak, hyp_strong]
		mock_sum.return_value = ["s1", "s2"]
		mock_brief.side_effect = Exception("skip")

		# hyp_strong (Drug1) gets great validation, hyp_weak (Drug2) gets bad validation
		async def validation_side_effect(hypothesis):
			if "Drug1" in hypothesis.get("title", ""):
				return [ToolResponse(
					status="success", confidence_delta=0.8,
					evidence_type="supporting", summary="strong docking",
					raw_data={"tool_type": "diffdock"},
				)]
			else:
				return [ToolResponse(
					status="success", confidence_delta=-0.1,
					evidence_type="contradicting", summary="weak docking",
					raw_data={"tool_type": "diffdock"},
				)]

		mock_validate.side_effect = validation_side_effect

		result = await run_pipeline("test", start_entity="RA", start_type="Disease", target_types=["Drug"])

	# After re-ranking, both should have pre_validation_score and updated overall_score
	for sh in result.scored_hypotheses:
		assert "pre_validation_score" in sh

	# hyp_strong (Drug1) should now rank higher despite lower base score
	# because validation gave it +0.8 delta
	drug1 = next(sh for sh in result.scored_hypotheses if "Drug1" in sh["title"])
	drug2 = next(sh for sh in result.scored_hypotheses if "Drug2" in sh["title"])
	assert drug1["overall_score"] > drug2["overall_score"]
	assert drug1["pre_validation_score"] < drug2["pre_validation_score"]


@pytest.mark.asyncio
async def test_experiment_stage_validated():
	"""Experiment stage generates report when verdict is validated."""
	mock_output = ResearchOutput(
		hypothesis_title="Test",
		visuals=[VisualAsset(label="pathway", svg="<svg/>", asset_type="pathway")],
		discovery_narrative="The pipeline discovered...",
		pitch_markdown="# Test Pitch",
	)

	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip")), \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[]), \
		 patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock, return_value=0), \
		 patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock) as mock_design, \
		 patch("nexus.pipeline.orchestrator.validate_and_execute_protocol", new_callable=AsyncMock) as mock_exec, \
		 patch("nexus.pipeline.orchestrator.interpret_results", new_callable=AsyncMock) as mock_interp, \
		 patch("nexus.pipeline.orchestrator.run_viz_agent", new_callable=AsyncMock) as mock_viz, \
		 patch("nexus.pipeline.orchestrator.generate_full_output", new_callable=AsyncMock) as mock_output_gen:

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(decision=CheckpointDecision.CONTINUE, reason="ok", confidence=0.8)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])
		mock_abc.return_value = [MOCK_HYPOTHESIS]
		mock_sum.return_value = ["summary"]

		mock_design.return_value = {"hypothesis_id": "test", "compound": {"name": "Donepezil"}}
		mock_exec.return_value = {
			"status": "simulation_complete",
			"simulated_results": {"dose_response": [], "qc_metrics": {}, "analysis": {"active": True}},
		}
		mock_interp.return_value = {
			"verdict": "validated",
			"confidence": 0.85,
			"reasoning": "Compound active",
			"concerns": [],
			"next_steps": ["Confirm in secondary assay"],
		}
		mock_viz.return_value = {"hypothesis_id": "1-2-3", "nodes": [], "edges": [], "fallback": True}
		mock_output_gen.return_value = mock_output

		result = await run_pipeline("Alzheimer", start_entity="Alzheimer", target_types=["Compound"])

	assert result.step == PipelineStep.COMPLETED
	assert len(result.experiment_results) == 1
	exp = result.experiment_results[0]
	assert exp["interpretation"]["verdict"] == "validated"
	assert "research_output" in exp
	assert exp["research_output"]["narrative"] == "The pipeline discovered..."
	assert exp["research_output"]["pitch"] == "# Test Pitch"
	assert len(exp["research_output"]["visuals"]) == 1
	assert "biorender_viz" in exp


@pytest.mark.asyncio
async def test_experiment_stage_refuted():
	"""Experiment stage stores failure analysis when verdict is refuted."""
	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip")), \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[]), \
		 patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock, return_value=0), \
		 patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock) as mock_design, \
		 patch("nexus.pipeline.orchestrator.validate_and_execute_protocol", new_callable=AsyncMock) as mock_exec, \
		 patch("nexus.pipeline.orchestrator.interpret_results", new_callable=AsyncMock) as mock_interp:

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(decision=CheckpointDecision.CONTINUE, reason="ok", confidence=0.8)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])
		mock_abc.return_value = [MOCK_HYPOTHESIS]
		mock_sum.return_value = ["summary"]

		mock_design.return_value = {"hypothesis_id": "test", "compound": {"name": "Donepezil"}}
		mock_exec.return_value = {
			"status": "simulation_complete",
			"simulated_results": {"dose_response": [], "qc_metrics": {}, "analysis": {"active": False}},
		}
		mock_interp.return_value = {
			"verdict": "refuted",
			"confidence": 0.7,
			"reasoning": "No activity observed",
			"concerns": [],
			"next_steps": ["Try related analogs"],
		}

		result = await run_pipeline("Alzheimer", start_entity="Alzheimer", target_types=["Compound"])

	assert result.step == PipelineStep.COMPLETED
	assert len(result.experiment_results) == 1
	exp = result.experiment_results[0]
	assert exp["interpretation"]["verdict"] == "refuted"
	assert "failure_analysis" in exp
	assert exp["failure_analysis"]["verdict"] == "refuted"
	assert exp["failure_analysis"]["next_steps"] == ["Try related analogs"]
	assert "research_output" not in exp


@pytest.mark.asyncio
async def test_experiment_stage_simulation_error():
	"""Experiment stage stores error analysis when simulation fails."""
	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock, side_effect=Exception("skip")), \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock, return_value=[]), \
		 patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock, return_value=0), \
		 patch("nexus.pipeline.orchestrator.design_experiment", new_callable=AsyncMock) as mock_design, \
		 patch("nexus.pipeline.orchestrator.validate_and_execute_protocol", new_callable=AsyncMock) as mock_exec:

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(decision=CheckpointDecision.CONTINUE, reason="ok", confidence=0.8)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])
		mock_abc.return_value = [MOCK_HYPOTHESIS]
		mock_sum.return_value = ["summary"]

		mock_design.return_value = {"hypothesis_id": "test", "compound": {"name": "Donepezil"}}
		mock_exec.return_value = {
			"status": "validation_failed",
			"validation": {"valid": False, "errors": ["Missing plate layout"]},
		}

		result = await run_pipeline("Alzheimer", start_entity="Alzheimer", target_types=["Compound"])

	assert result.step == PipelineStep.COMPLETED
	assert len(result.experiment_results) == 1
	exp = result.experiment_results[0]
	assert "error_analysis" in exp
	assert exp["error_analysis"]["status"] == "validation_failed"
	assert "interpretation" not in exp
