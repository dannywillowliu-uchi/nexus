from __future__ import annotations

import asyncio

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse


TAMARIND_BASE_URL = "https://app.tamarind.bio/api"
POLL_INTERVAL = 5.0
MAX_POLL_ATTEMPTS = 10


def _score_to_evidence(score: float) -> tuple[float, str]:
	"""Convert a docking score to (confidence_delta, evidence_type)."""
	# Negative docking scores indicate better binding
	if score < -7.0:
		return 0.5, "supporting"
	elif score < -5.0:
		return 0.3, "supporting"
	elif score < -3.0:
		return 0.1, "neutral"
	else:
		return -0.1, "contradicting"


async def molecular_dock(compound_name: str, protein_name: str) -> ToolResponse:
	"""Submit a molecular docking job to Tamarind Bio API and poll for results."""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Molecular docking skipped for {compound_name} + {protein_name}: no Tamarind Bio API key configured.",
			raw_data={
				"compound": compound_name,
				"protein": protein_name,
				"reason": "missing_api_key",
			},
		)

	job_name = f"nexus-dock-{compound_name}-{protein_name}"

	headers = {
		"x-api-key": settings.tamarind_bio_api_key,
		"Content-Type": "application/json",
	}

	payload = {
		"jobName": job_name,
		"type": "autodock_vina",
		"settings": {
			"target": protein_name,
			"ligand": compound_name,
		},
	}

	try:
		async with httpx.AsyncClient(timeout=60.0) as client:
			# Step 1: Submit the docking job
			submit_resp = await client.post(
				f"{TAMARIND_BASE_URL}/submit-job",
				json=payload,
				headers=headers,
			)
			submit_resp.raise_for_status()

			# Step 2: Poll for completion
			for _ in range(MAX_POLL_ATTEMPTS):
				await asyncio.sleep(POLL_INTERVAL)

				poll_resp = await client.get(
					f"{TAMARIND_BASE_URL}/jobs",
					params={"jobName": job_name},
					headers=headers,
				)
				poll_resp.raise_for_status()
				poll_data = poll_resp.json()

				jobs = poll_data.get("jobs", [])
				if not jobs:
					continue

				job = jobs[0]
				status = job.get("status", "")

				if status == "Complete":
					# Step 3: Fetch results
					result_resp = await client.post(
						f"{TAMARIND_BASE_URL}/result",
						json={"jobName": job_name, "pdbsOnly": False},
						headers=headers,
					)
					result_resp.raise_for_status()
					result_data = result_resp.json()

					score = result_data.get("docking_score", 0.0)
					confidence_delta, evidence_type = _score_to_evidence(score)

					return ToolResponse(
						status="success",
						confidence_delta=confidence_delta,
						evidence_type=evidence_type,
						summary=f"Docking of {compound_name} to {protein_name}: score={score}.",
						raw_data=result_data,
					)

			# Polling exhausted without completion
			return ToolResponse(
				status="partial",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"Docking job '{job_name}' submitted but not yet complete. Poll later for results.",
				raw_data={
					"job_name": job_name,
					"status": "polling_timeout",
				},
			)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Tamarind Bio docking submission failed: {exc}",
			raw_data={"error": str(exc)},
		)
