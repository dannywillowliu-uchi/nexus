from __future__ import annotations

from nexus.config import settings
from nexus.tools.dock_compound import _score_to_evidence
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient


async def molecular_dock(compound_name: str, protein_name: str) -> ToolResponse:
	"""Submit a molecular docking job to Tamarind Bio API and poll for results.

	Backward-compatible wrapper around TamarindClient. Uses autodock_vina.
	"""
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
	client = TamarindClient()

	try:
		result = await client.run_job(
			job_name=job_name,
			job_type="autodock_vina",
			settings={
				"target": protein_name,
				"ligand": compound_name,
			},
		)
	except TimeoutError:
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
	except Exception as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Tamarind Bio docking submission failed: {exc}",
			raw_data={"error": str(exc)},
		)

	job_status = result.get("status", "")
	if job_status != "Complete":
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

	result_data = result.get("result", {}) or {}
	score = result_data.get("docking_score", 0.0)
	confidence_delta, evidence_type = _score_to_evidence(score)

	return ToolResponse(
		status="success",
		confidence_delta=confidence_delta,
		evidence_type=evidence_type,
		summary=f"Docking of {compound_name} to {protein_name}: score={score}.",
		raw_data=result_data,
	)
