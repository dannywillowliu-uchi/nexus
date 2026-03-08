"""Molecular docking via Tamarind Bio -- supports multiple docking engines."""

from __future__ import annotations

from nexus.config import settings
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient

SUPPORTED_METHODS = {"autodock_vina", "diffdock", "gnina"}


def _score_to_evidence(score: float) -> tuple[float, str]:
	"""Convert a docking score to (confidence_delta, evidence_type)."""
	if score < -7.0:
		return 0.5, "supporting"
	elif score < -5.0:
		return 0.3, "supporting"
	elif score < -3.0:
		return 0.1, "neutral"
	else:
		return -0.1, "contradicting"


async def dock_compound(
	compound_smiles: str,
	protein_name: str,
	method: str = "autodock_vina",
) -> ToolResponse:
	"""Dock a compound against a protein target.

	Methods: autodock_vina, diffdock, gnina.
	"""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Docking skipped for {protein_name}: no Tamarind Bio API key configured.",
			raw_data={"protein": protein_name, "reason": "missing_api_key"},
		)

	if method not in SUPPORTED_METHODS:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Unsupported docking method: {method}. Use one of: {', '.join(sorted(SUPPORTED_METHODS))}.",
			raw_data={"reason": "unsupported_method", "method": method},
		)

	job_name = f"nexus-dock-{method}-{hash(compound_smiles + protein_name) % 100000:05d}"
	client = TamarindClient()

	try:
		result = await client.run_job(
			job_name=job_name,
			job_type=method,
			settings={
				"target": protein_name,
				"ligand": compound_smiles,
			},
		)
	except TimeoutError:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Docking job '{job_name}' timed out. Poll later for results.",
			raw_data={"job_name": job_name, "status": "polling_timeout"},
		)
	except Exception as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Docking submission failed: {exc}",
			raw_data={"error": str(exc)},
		)

	job_status = result.get("status", "")
	if job_status != "Complete":
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Docking job '{job_name}' ended with status: {job_status}.",
			raw_data={"job_name": job_name, "status": job_status},
		)

	result_data = result.get("result", {}) or {}
	score = result_data.get("docking_score", 0.0)
	confidence_delta, evidence_type = _score_to_evidence(score)

	return ToolResponse(
		status="success",
		confidence_delta=confidence_delta,
		evidence_type=evidence_type,
		summary=f"Docking of compound to {protein_name} via {method}: score={score}.",
		raw_data=result_data,
	)
