"""Protein structure prediction via Tamarind Bio."""

from __future__ import annotations

from nexus.config import settings
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient

SUPPORTED_METHODS = {"esmfold", "alphafold", "chai", "boltz", "openfold"}


async def predict_structure(protein_sequence: str, method: str = "esmfold") -> ToolResponse:
	"""Predict protein 3D structure from amino acid sequence.

	Methods: esmfold (fast), alphafold (accurate), chai, boltz, openfold.
	"""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Structure prediction skipped: no Tamarind Bio API key configured.",
			raw_data={"reason": "missing_api_key"},
		)

	if method not in SUPPORTED_METHODS:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Unsupported structure prediction method: {method}. Use one of: {', '.join(sorted(SUPPORTED_METHODS))}.",
			raw_data={"reason": "unsupported_method", "method": method},
		)

	job_name = f"nexus-struct-{method}-{hash(protein_sequence) % 100000:05d}"
	client = TamarindClient()

	try:
		result = await client.run_job(
			job_name=job_name,
			job_type=method,
			settings={"target": protein_sequence},
		)
	except TimeoutError:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Structure prediction job '{job_name}' timed out. Poll later for results.",
			raw_data={"job_name": job_name, "status": "polling_timeout"},
		)
	except Exception as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Structure prediction failed: {exc}",
			raw_data={"error": str(exc)},
		)

	job_status = result.get("status", "")
	if job_status != "Complete":
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Structure prediction job '{job_name}' ended with status: {job_status}.",
			raw_data={"job_name": job_name, "status": job_status},
		)

	result_data = result.get("result", {}) or {}
	plddt = result_data.get("plddt_score") or result_data.get("confidence_score")
	confidence_delta, evidence_type = _plddt_to_evidence(plddt)

	plddt_str = f", pLDDT={plddt:.1f}" if plddt is not None else ""
	return ToolResponse(
		status="success",
		confidence_delta=confidence_delta,
		evidence_type=evidence_type,
		summary=f"Structure predicted via {method} for sequence (len={len(protein_sequence)}){plddt_str}.",
		raw_data=result_data,
	)


def _plddt_to_evidence(plddt: float | None) -> tuple[float, str]:
	"""Map pLDDT confidence score to (confidence_delta, evidence_type)."""
	if plddt is None:
		return 0.1, "neutral"
	if plddt >= 90:
		return 0.4, "supporting"
	elif plddt >= 70:
		return 0.2, "supporting"
	elif plddt >= 50:
		return 0.1, "neutral"
	else:
		return -0.1, "contradicting"
