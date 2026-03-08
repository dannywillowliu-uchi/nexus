"""Generic async client for the Tamarind Bio API.

Handles any job type: submit, poll, result retrieval, file upload, and batch submission.
"""

from __future__ import annotations

import asyncio

import httpx

from nexus.config import settings

TAMARIND_BASE_URL = "https://app.tamarind.bio/api"
DEFAULT_POLL_INTERVAL = 5.0
DEFAULT_TIMEOUT = 300.0


class TamarindClient:
	"""Reusable async client for all Tamarind Bio API interactions."""

	def __init__(
		self,
		api_key: str | None = None,
		base_url: str = TAMARIND_BASE_URL,
		poll_interval: float = DEFAULT_POLL_INTERVAL,
	):
		self._api_key = api_key or settings.tamarind_bio_api_key
		self._base_url = base_url
		self._poll_interval = poll_interval

	@property
	def _headers(self) -> dict[str, str]:
		return {
			"x-api-key": self._api_key,
			"Content-Type": "application/json",
		}

	async def submit_job(self, job_name: str, job_type: str, settings: dict) -> str:
		"""Submit a single job. Returns the job name."""
		payload = {
			"jobName": job_name,
			"type": job_type,
			"settings": settings,
		}
		async with httpx.AsyncClient(timeout=60.0) as client:
			resp = await client.post(
				f"{self._base_url}/submit-job",
				json=payload,
				headers=self._headers,
			)
			resp.raise_for_status()
		return job_name

	async def submit_batch(self, batch_name: str, jobs: list[dict]) -> str:
		"""Submit multiple jobs as a batch. Returns the batch name."""
		payload = {
			"batchName": batch_name,
			"jobs": jobs,
		}
		async with httpx.AsyncClient(timeout=60.0) as client:
			resp = await client.post(
				f"{self._base_url}/submit-batch",
				json=payload,
				headers=self._headers,
			)
			resp.raise_for_status()
		return batch_name

	async def poll_until_complete(self, job_name: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
		"""Poll GET /jobs until the job status is 'Complete' or timeout is reached.

		Returns the job dict from the API response.
		Raises TimeoutError if the job does not complete within timeout seconds.
		"""
		elapsed = 0.0
		async with httpx.AsyncClient(timeout=60.0) as client:
			while elapsed < timeout:
				await asyncio.sleep(self._poll_interval)
				elapsed += self._poll_interval

				resp = await client.get(
					f"{self._base_url}/jobs",
					params={"jobName": job_name},
					headers=self._headers,
				)
				resp.raise_for_status()
				data = resp.json()

				# API returns indexed keys ("0", "1", ...) or "jobs" list
				jobs = data.get("jobs", [])
				if not jobs:
					# Try indexed format: {"0": {...}, "statuses": {...}}
					for key in sorted(data.keys()):
						if key.isdigit() and isinstance(data[key], dict):
							jobs.append(data[key])
				if not jobs:
					continue

				job = jobs[0]
				status = job.get("status", job.get("JobStatus", ""))

				if status == "Complete":
					return job
				if status in ("Failed", "Stopped"):
					return job

		raise TimeoutError(f"Job '{job_name}' did not complete within {timeout}s")

	async def poll_batch(self, batch_name: str, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
		"""Poll until all jobs in a batch reach a terminal state."""
		elapsed = 0.0
		async with httpx.AsyncClient(timeout=60.0) as client:
			while elapsed < timeout:
				await asyncio.sleep(self._poll_interval)
				elapsed += self._poll_interval

				resp = await client.get(
					f"{self._base_url}/jobs",
					params={"batch": batch_name, "includeSubjobs": "true"},
					headers=self._headers,
				)
				resp.raise_for_status()
				data = resp.json()

				jobs = data.get("jobs", [])
				if not jobs:
					continue

				terminal = {"Complete", "Failed", "Stopped"}
				if all(j.get("status", "") in terminal for j in jobs):
					return jobs

		raise TimeoutError(f"Batch '{batch_name}' did not complete within {timeout}s")

	async def get_result(self, job_name: str, pdbs_only: bool = False) -> dict:
		"""Fetch results for a completed job."""
		payload = {
			"jobName": job_name,
			"pdbsOnly": pdbs_only,
		}
		async with httpx.AsyncClient(timeout=60.0) as client:
			resp = await client.post(
				f"{self._base_url}/result",
				json=payload,
				headers=self._headers,
			)
			resp.raise_for_status()
			return resp.json()

	async def upload_file(self, filename: str, content: bytes, folder: str | None = None) -> str:
		"""Upload a file to Tamarind. Returns the file URL."""
		params = {}
		if folder:
			params["folder"] = folder

		headers = {
			"x-api-key": self._api_key,
			"Content-Type": "application/octet-stream",
		}
		async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
			resp = await client.put(
				f"{self._base_url}/upload/{filename}",
				content=content,
				params=params,
				headers=headers,
			)
			resp.raise_for_status()
			if resp.text.strip():
				data = resp.json()
				return data.get("fileUrl", data.get("signedUrl", filename))
			return filename

	async def list_job_types(self) -> list[str]:
		"""Fetch available job types from the Tamarind Bio API."""
		async with httpx.AsyncClient(timeout=30.0) as client:
			resp = await client.get(
				f"{self._base_url}/job-types",
				headers=self._headers,
			)
			resp.raise_for_status()
			data = resp.json()
			return data.get("jobTypes", [])

	async def run_job(self, job_name: str, job_type: str, settings: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
		"""Convenience: submit, poll, and return results in one call."""
		await self.submit_job(job_name, job_type, settings)
		job = await self.poll_until_complete(job_name, timeout=timeout)

		status = job.get("status", "")
		if status != "Complete":
			return {"job": job, "status": status, "result": None}

		result = await self.get_result(job_name)
		return {"job": job, "status": status, "result": result}
