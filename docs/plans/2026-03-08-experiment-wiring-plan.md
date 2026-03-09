# Experiment Stage Wiring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the lab experiment module into the pipeline orchestrator so hypotheses get simulated experiments, interpreted, and produce reports or failure analyses.

**Architecture:** After validation re-ranking, the orchestrator calls `design_experiment()` for the top hypothesis, runs it through the simulator, interprets results, then branches: generate a full research report (with BioRender viz) on success, or run reasoning analysis on failure.

**Tech Stack:** Python, pytest, pytest-asyncio, existing lab/output/viz modules

---

### Task 1: Add experiment stage to orchestrator

**Files:**
- Modify: `backend/src/nexus/pipeline/orchestrator.py`
- Test: `tests/pipeline/test_orchestrator.py`

**Step 1: Add imports to orchestrator.py**

Add after existing imports at top of file:

```python
from nexus.agents.viz_agent import run_viz_agent
from nexus.lab.tools import design_experiment, interpret_results, validate_and_execute_protocol
from nexus.output.pitch import generate_full_output
```

**Step 2: Add experiment stage block after validation re-ranking**

Insert after `result.scored_hypotheses.sort(...)` (the re-ranking sort) and before the `stage_complete` emit for validation. Replace the current validation `stage_complete` emit + `COMPLETED` block with:

```python
		await _emit(on_event, "stage_complete", {
			"stage": "validation",
			"validation_results": len(result.validation_results),
		})

		# --- Experiment stage ---
		result.step = PipelineStep.EXPERIMENT
		await _emit(on_event, "stage_start", {"stage": "experiment"})

		if result.scored_hypotheses:
			top_hyp = result.scored_hypotheses[0]
			plausibility = min(max(top_hyp.get("overall_score", 0.5), 0.1), 0.9)

			try:
				# Design experiment
				spec = await design_experiment(top_hyp, budget_tier="minimal")

				# Execute via simulator
				exec_result = await validate_and_execute_protocol(spec, backend="simulator")
				exec_result["hypothesis_title"] = top_hyp.get("title", "")

				if exec_result.get("status") == "simulation_complete":
					# Override default plausibility with hypothesis score
					sim_results = exec_result.get("simulated_results", {})

					# Interpret
					interpretation = await interpret_results(spec, sim_results)
					exec_result["interpretation"] = interpretation
					verdict = interpretation.get("verdict", "inconclusive")

					if verdict == "validated":
						# BioRender visualization
						result.step = PipelineStep.VISUALIZATION
						await _emit(on_event, "stage_start", {"stage": "visualization"})

						# Find matching ABCHypothesis for viz_agent
						viz_data = None
						if result.hypotheses:
							viz_data = await run_viz_agent(result.hypotheses[0], pivot_trail=result.pivots)

						# Generate full research output
						lit_stats = None
						if result.literature_result:
							lit_stats = {
								"papers": len(result.literature_result.papers),
								"triples": len(result.literature_result.triples),
							}
						graph_stats = {"hypotheses": len(result.hypotheses), "scored": len(result.scored_hypotheses)}

						output = await generate_full_output(
							hypothesis=top_hyp,
							pipeline_query=result.query,
							pipeline_start_entity=result.start_entity,
							pipeline_start_type=result.start_type,
							checkpoint_log=result.checkpoint_log,
							pivots=result.pivots,
							branches=result.branches,
							validation_results=result.validation_results,
							literature_stats=lit_stats,
							graph_stats=graph_stats,
						)

						exec_result["research_output"] = {
							"narrative": output.discovery_narrative,
							"pitch": output.pitch_markdown,
							"visuals": [{"title": v.title, "svg": v.svg_content, "description": v.description} for v in output.visuals],
						}
						if viz_data:
							exec_result["biorender_viz"] = viz_data

						await _emit(on_event, "stage_complete", {"stage": "visualization"})

					else:
						# Refuted or inconclusive -- reasoning analysis
						exec_result["failure_analysis"] = {
							"verdict": verdict,
							"confidence": interpretation.get("confidence", 0),
							"reasoning": interpretation.get("reasoning", ""),
							"concerns": interpretation.get("concerns", []),
							"next_steps": interpretation.get("next_steps", []),
						}

				else:
					# Technical/lab error
					exec_result["error_analysis"] = {
						"status": exec_result.get("status", "unknown"),
						"reason": "Experiment could not complete simulation",
					}
					if "validation" in exec_result:
						exec_result["error_analysis"]["validation"] = exec_result["validation"]

				result.experiment_results.append(exec_result)

			except Exception as exc:
				logger.warning("Experiment stage failed: %s", exc)
				result.experiment_results.append({
					"status": "error",
					"error": str(exc),
					"hypothesis_title": top_hyp.get("title", ""),
				})

		await _emit(on_event, "stage_complete", {"stage": "experiment"})

		result.step = PipelineStep.COMPLETED
		await _emit(on_event, "pipeline_complete", {
			"hypotheses": len(result.scored_hypotheses),
			"briefs": len(result.research_briefs),
			"validations": len(result.validation_results),
			"experiments": len(result.experiment_results),
			"pivots": len(result.pivots),
			"branches": len(result.branches),
		})
```

**Step 3: Commit**

```bash
git add backend/src/nexus/pipeline/orchestrator.py
git commit -m "feat: wire experiment stage into pipeline orchestrator"
```

### Task 2: Add tests for experiment wiring

**Files:**
- Modify: `tests/pipeline/test_orchestrator.py`

**Step 1: Write test for validated path**

Add a test that mocks design_experiment, validate_and_execute_protocol, interpret_results (returning "validated" verdict), run_viz_agent, and generate_full_output. Verify `experiment_results[0]` contains `research_output` and `interpretation`.

```python
async def test_experiment_stage_validated():
	"""Experiment stage generates report when verdict is validated."""
	# Mock all pipeline stages up to experiment
	# Mock design_experiment -> spec dict
	# Mock validate_and_execute_protocol -> {"status": "simulation_complete", "simulated_results": {...}}
	# Mock interpret_results -> {"verdict": "validated", "confidence": 0.85, ...}
	# Mock run_viz_agent -> {"hypothesis_id": "...", "nodes": [], ...}
	# Mock generate_full_output -> ResearchOutput(...)
	# Assert result.experiment_results[0]["interpretation"]["verdict"] == "validated"
	# Assert "research_output" in result.experiment_results[0]
```

**Step 2: Write test for refuted path**

Same mocks but interpret_results returns `{"verdict": "refuted", ...}`. Verify `experiment_results[0]` contains `failure_analysis` with verdict, concerns, next_steps.

**Step 3: Write test for simulation error path**

Mock validate_and_execute_protocol to return `{"status": "validation_failed", ...}`. Verify `experiment_results[0]` contains `error_analysis`.

**Step 4: Run tests**

```bash
pytest tests/pipeline/test_orchestrator.py -v
```

**Step 5: Commit**

```bash
git add tests/pipeline/test_orchestrator.py
git commit -m "test: add experiment stage wiring tests"
```

### Task 3: Run full test suite

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

**Step 2: Run linter**

```bash
ruff check backend/ tests/
```

**Step 3: Fix any issues and commit**
