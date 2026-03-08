import uuid

from fastapi import APIRouter

from nexus.db.models import ExperimentRequest

router = APIRouter()


@router.post("/experiments")
async def submit_experiment(request: ExperimentRequest):
	experiment_id = str(uuid.uuid4())
	return {
		"experiment_id": experiment_id,
		"hypothesis_id": str(request.hypothesis_id),
		"provider": request.provider,
		"status": "submitted",
	}


@router.get("/experiments/{experiment_id}")
async def get_experiment_status(experiment_id: str):
	return {
		"experiment_id": experiment_id,
		"status": "placeholder",
		"result": None,
	}
