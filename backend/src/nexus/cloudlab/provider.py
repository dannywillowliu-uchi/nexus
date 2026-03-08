from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExperimentProtocol:
	hypothesis_id: str
	title: str
	description: str
	protocol_json: dict  # Provider-specific format
	estimated_cost: float | None = None


@dataclass
class ExperimentSubmission:
	submission_id: str
	provider: str
	status: str  # "submitted", "running", "completed", "failed"


@dataclass
class ExperimentResults:
	submission_id: str
	status: str
	data: dict
	summary: str


class CloudLabProvider(Protocol):
	async def validate_protocol(self, protocol: ExperimentProtocol) -> dict: ...
	async def submit_experiment(self, protocol: ExperimentProtocol) -> ExperimentSubmission: ...
	async def poll_status(self, submission_id: str) -> str: ...
	async def get_results(self, submission_id: str) -> ExperimentResults: ...
