from __future__ import annotations

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse


TAMARIND_SUBMIT_URL = "https://api.tamarind.bio/submit-job"


async def molecular_dock(compound_name: str, protein_name: str) -> ToolResponse:
	"""Submit a molecular docking job to Tamarind Bio API."""
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

	try:
		headers = {
			"x-api-key": settings.tamarind_bio_api_key,
			"Content-Type": "application/json",
		}

		payload = {
			"compound_name": compound_name,
			"protein_name": protein_name,
			"species": "human",
		}

		async with httpx.AsyncClient(timeout=60.0) as client:
			resp = await client.post(TAMARIND_SUBMIT_URL, json=payload, headers=headers)
			resp.raise_for_status()
			data = resp.json()

		job_id = data.get("job_id", "")
		status = data.get("status", "submitted")

		if status == "completed":
			score = data.get("docking_score", 0.0)
			# Negative docking scores indicate better binding
			if score < -7.0:
				confidence_delta = 0.5
				evidence_type = "supporting"
			elif score < -5.0:
				confidence_delta = 0.3
				evidence_type = "supporting"
			elif score < -3.0:
				confidence_delta = 0.1
				evidence_type = "neutral"
			else:
				confidence_delta = -0.1
				evidence_type = "contradicting"

			return ToolResponse(
				status="success",
				confidence_delta=confidence_delta,
				evidence_type=evidence_type,
				summary=f"Docking of {compound_name} to {protein_name}: score={score}.",
				raw_data=data,
			)

		# Job submitted but not yet completed
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Docking job submitted (ID: {job_id}). Status: {status}. Poll for results later.",
			raw_data={"job_id": job_id, "status": status, **data},
		)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Tamarind Bio docking submission failed: {exc}",
			raw_data={"error": str(exc)},
		)
