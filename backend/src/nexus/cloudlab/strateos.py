import httpx

from nexus.cloudlab.provider import ExperimentProtocol, ExperimentResults, ExperimentSubmission
from nexus.config import settings


class StrateosProvider:
	BASE_URL = "https://secure.transcriptic.com"

	def __init__(self) -> None:
		self._email = settings.strateos_email
		self._token = settings.strateos_token
		self._org_id = settings.strateos_organization_id

	def _headers(self) -> dict[str, str]:
		return {
			"X-User-Email": self._email,
			"X-User-Token": self._token,
			"Content-Type": "application/json",
		}

	def _check_credentials(self) -> None:
		if not self._email or not self._token or not self._org_id:
			raise ValueError("Missing Strateos credentials: email, token, and organization_id are required")

	async def validate_protocol(self, protocol: ExperimentProtocol) -> dict:
		self._check_credentials()
		url = f"{self.BASE_URL}/api/v1/organizations/{self._org_id}/runs/validate"
		try:
			async with httpx.AsyncClient() as client:
				response = await client.post(url, json=protocol.protocol_json, headers=self._headers())
				response.raise_for_status()
				return response.json()
		except httpx.HTTPStatusError as e:
			return {"error": True, "status_code": e.response.status_code, "detail": str(e)}

	async def submit_experiment(self, protocol: ExperimentProtocol) -> ExperimentSubmission:
		self._check_credentials()
		url = f"{self.BASE_URL}/api/v1/organizations/{self._org_id}/runs"
		try:
			async with httpx.AsyncClient() as client:
				response = await client.post(url, json=protocol.protocol_json, headers=self._headers())
				response.raise_for_status()
				data = response.json()
				return ExperimentSubmission(
					submission_id=data.get("id", ""),
					provider="strateos",
					status="submitted",
				)
		except httpx.HTTPStatusError as e:
			return ExperimentSubmission(
				submission_id="",
				provider="strateos",
				status=f"failed: {e.response.status_code}",
			)

	async def poll_status(self, submission_id: str) -> str:
		self._check_credentials()
		url = f"{self.BASE_URL}/api/v1/organizations/{self._org_id}/runs/{submission_id}"
		try:
			async with httpx.AsyncClient() as client:
				response = await client.get(url, headers=self._headers())
				response.raise_for_status()
				data = response.json()
				return data.get("status", "unknown")
		except httpx.HTTPStatusError as e:
			return f"error: {e.response.status_code}"

	async def get_results(self, submission_id: str) -> ExperimentResults:
		self._check_credentials()
		url = f"{self.BASE_URL}/api/v1/organizations/{self._org_id}/runs/{submission_id}/data"
		try:
			async with httpx.AsyncClient() as client:
				response = await client.get(url, headers=self._headers())
				response.raise_for_status()
				data = response.json()
				return ExperimentResults(
					submission_id=submission_id,
					status="completed",
					data=data,
					summary=data.get("summary", ""),
				)
		except httpx.HTTPStatusError as e:
			return ExperimentResults(
				submission_id=submission_id,
				status="failed",
				data={"error": str(e)},
				summary=f"Failed to retrieve results: {e.response.status_code}",
			)
