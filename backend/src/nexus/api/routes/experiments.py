import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from nexus.db.models import ExperimentRequest

router = APIRouter()

# In-memory store for experiment tracking (replace with DB in production)
_experiments: dict[str, dict] = {}


class DesignRequest(BaseModel):
	hypothesis: dict
	compound_info: dict | None = None
	budget_tier: str = "minimal"


class ExecuteRequest(BaseModel):
	experiment_spec: dict
	backend: Literal["simulator", "strateos", "dry_run"] = "simulator"


async def _run_experiment_background(experiment_id: str, spec: dict, backend: str) -> None:
	"""Run experiment validation + execution in the background."""
	from nexus.lab.tools import interpret_results, validate_and_execute_protocol

	_experiments[experiment_id]["status"] = "running"
	try:
		result = await validate_and_execute_protocol(spec, backend=backend)
		_experiments[experiment_id]["execution"] = result

		# Interpret if we have results
		sim_data = result.get("simulated_results", result.get("cloud_lab_results", {}))
		if sim_data:
			interpretation = await interpret_results(spec, sim_data)
			_experiments[experiment_id]["interpretation"] = interpretation

		_experiments[experiment_id]["status"] = result.get("status", "complete")
	except Exception as exc:
		_experiments[experiment_id]["status"] = "failed"
		_experiments[experiment_id]["error"] = str(exc)


@router.post("/experiments")
async def submit_experiment(request: ExperimentRequest):
	"""Submit a hypothesis for full experiment pipeline: design → validate → execute → interpret."""
	from nexus.lab.tools import design_experiment

	experiment_id = str(uuid.uuid4())

	# Design the experiment from the hypothesis
	hypothesis = {
		"hypothesis_id": str(request.hypothesis_id),
		"hypothesis_type": "drug_repurposing",
	}

	spec = await design_experiment(hypothesis, budget_tier="minimal")

	# Run validation + execution synchronously for now
	from nexus.lab.tools import interpret_results, validate_and_execute_protocol

	result = await validate_and_execute_protocol(spec, backend="simulator")
	interpretation = None
	sim_data = result.get("simulated_results")
	if sim_data:
		interpretation = await interpret_results(spec, sim_data)

	_experiments[experiment_id] = {
		"experiment_id": experiment_id,
		"hypothesis_id": str(request.hypothesis_id),
		"provider": request.provider,
		"status": result.get("status", "complete"),
		"experiment_spec": spec,
		"execution": result,
		"interpretation": interpretation,
	}

	return {
		"experiment_id": experiment_id,
		"hypothesis_id": str(request.hypothesis_id),
		"provider": request.provider,
		"status": result.get("status", "complete"),
		"validation": result.get("validation"),
		"interpretation": interpretation,
	}


@router.get("/experiments/{experiment_id}")
async def get_experiment_status(experiment_id: str):
	"""Get full experiment status including results and interpretation."""
	exp = _experiments.get(experiment_id)
	if not exp:
		raise HTTPException(status_code=404, detail="Experiment not found")
	return exp


@router.post("/experiments/design")
async def design_only(request: DesignRequest):
	"""Design an experiment without executing it. Returns the full ExperimentSpec."""
	from nexus.lab.tools import design_experiment

	spec = await design_experiment(
		hypothesis=request.hypothesis,
		compound_info=request.compound_info,
		budget_tier=request.budget_tier,
	)
	return spec


@router.post("/experiments/execute")
async def execute_protocol(request: ExecuteRequest, background_tasks: BackgroundTasks):
	"""Execute a previously designed experiment spec."""
	experiment_id = str(uuid.uuid4())
	_experiments[experiment_id] = {
		"experiment_id": experiment_id,
		"status": "queued",
		"experiment_spec": request.experiment_spec,
	}

	background_tasks.add_task(
		_run_experiment_background,
		experiment_id,
		request.experiment_spec,
		request.backend,
	)

	return {
		"experiment_id": experiment_id,
		"status": "queued",
		"backend": request.backend,
	}


@router.post("/experiments/resolve-compound")
async def resolve_compound_endpoint(name: str):
	"""Resolve a compound name to structured identifiers."""
	from nexus.lab.tools import resolve_compound

	return await resolve_compound(name)
