# Experiment Stage Wiring Design

## Problem

The pipeline orchestrator runs Literature -> Checkpoint -> Graph -> Checkpoint -> Reasoning -> Validation -> COMPLETED but never calls the lab module. `design_experiment()`, the simulator, and the interpreter all exist and work, but nothing wires them into the pipeline. The viz_agent (BioRender icons) is also unwired. The pipeline validates hypotheses computationally but never tests them experimentally or generates a final report.

## Solution

Add an Experiment stage between Validation and COMPLETED. For the top-ranked hypothesis:

1. **Design**: `design_experiment(hypothesis)` -> ExperimentSpec
2. **Execute**: `validate_and_execute_protocol(spec, backend="simulator")` -> simulated results
3. **Interpret**: `interpret_results(spec, results)` -> verdict
4. **Branch on verdict**:
   - **"validated"**: Run `run_viz_agent()` for BioRender icons, then `generate_full_output()` for narrative + SVG + pitch. Store both in `experiment_results`.
   - **"refuted"/"inconclusive"**: Run reasoning agent to analyze failure and suggest next steps. Store interpretation + analysis in `experiment_results`.
   - **Error** (validation_failed, code_generation_error): Log error with specific reason. Store in `experiment_results`.

## Data Flow

```
result.scored_hypotheses[0]  (top hypothesis after re-ranking)
        |
        v
design_experiment(hypothesis, budget_tier="minimal")
        |
        v
validate_and_execute_protocol(spec, backend="simulator")
        |
        v
interpret_results(spec, simulated_results)
        |
        +-- verdict == "validated" --> run_viz_agent() + generate_full_output()
        |
        +-- verdict == "refuted"/"inconclusive" --> generate_research_brief(with experimental context)
        |
        +-- status != "simulation_complete" --> log error, store failure reason
```

## Plausibility Score Mapping

The simulator's `hypothesis_plausibility` parameter controls whether the simulated compound is "active" (sigmoidal dose-response) or "inactive" (flat). We map the hypothesis `overall_score` to plausibility so simulation outcomes correlate with computational evidence:

```python
plausibility = min(max(top_hyp["overall_score"], 0.1), 0.9)
```

Clamped to [0.1, 0.9] to avoid trivially perfect or trivially null results.

## Pipeline Step Usage

`PipelineStep.EXPERIMENT` already exists in the enum. `PipelineStep.VISUALIZATION` also exists. The experiment stage sets `EXPERIMENT`, and within the validated branch, briefly transitions through `VISUALIZATION` before `COMPLETED`.

## Files Changed

- `backend/src/nexus/pipeline/orchestrator.py` -- Add experiment stage block, import lab tools + viz_agent + output module
- `tests/pipeline/test_orchestrator.py` -- Add tests for validated/refuted/error paths

## Files Unchanged

- `backend/src/nexus/lab/tools.py` -- APIs work as-is
- `backend/src/nexus/lab/execution/results_sim.py` -- No changes needed
- `backend/src/nexus/lab/interpretation/interpreter.py` -- No changes needed
- `backend/src/nexus/agents/viz_agent.py` -- No changes needed
- `backend/src/nexus/output/pitch.py` -- No changes needed
- `backend/src/nexus/output/narrative.py` -- No changes needed
