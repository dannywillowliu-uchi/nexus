"""Batch compound screening via Tamarind Bio."""

from __future__ import annotations

from nexus.config import settings
from nexus.tools.dock_compound import _score_to_evidence
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient

SUPPORTED_METHODS = {"autodock_vina", "diffdock", "gnina"}


async def batch_screen(
	compounds: list[str],
	protein_target: str,
	method: str = "autodock_vina",
	top_n: int = 10,
) -> ToolResponse:
	"""Screen multiple compounds against a target, return top N hits.

	Submits all docking jobs as a batch, polls for completion, ranks by score.
	"""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Batch screening skipped: no Tamarind Bio API key configured.",
			raw_data={"reason": "missing_api_key"},
		)

	if method not in SUPPORTED_METHODS:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Unsupported screening method: {method}. Use one of: {', '.join(sorted(SUPPORTED_METHODS))}.",
			raw_data={"reason": "unsupported_method", "method": method},
		)

	if not compounds:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary="No compounds provided for screening.",
			raw_data={"reason": "empty_compounds"},
		)

	batch_hash = hash(protein_target + str(len(compounds))) % 100000
	batch_name = f"nexus-screen-{batch_hash:05d}"

	jobs = []
	for i, smiles in enumerate(compounds):
		jobs.append({
			"jobName": f"{batch_name}-{i:04d}",
			"type": method,
			"settings": {
				"target": protein_target,
				"ligand": smiles,
			},
		})

	client = TamarindClient()

	try:
		await client.submit_batch(batch_name, jobs)
		completed_jobs = await client.poll_batch(batch_name)
	except TimeoutError:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Batch screening '{batch_name}' timed out. Poll later for results.",
			raw_data={"batch_name": batch_name, "status": "polling_timeout"},
		)
	except Exception as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Batch screening failed: {exc}",
			raw_data={"error": str(exc)},
		)

	# Fetch results for completed jobs
	hits: list[dict] = []
	errors: list[str] = []
	for job in completed_jobs:
		job_name = job.get("jobName", "")
		status = job.get("status", "")

		if status != "Complete":
			errors.append(f"{job_name}: {status}")
			continue

		try:
			result_data = await client.get_result(job_name)
			score = result_data.get("docking_score", 0.0)
			# Map job index back to compound
			idx_str = job_name.rsplit("-", 1)[-1]
			try:
				idx = int(idx_str)
				compound = compounds[idx] if idx < len(compounds) else job_name
			except (ValueError, IndexError):
				compound = job_name

			hits.append({
				"compound": compound,
				"docking_score": score,
				"job_name": job_name,
				"result": result_data,
			})
		except Exception as exc:
			errors.append(f"{job_name}: result fetch failed ({exc})")

	# Sort by docking score (more negative = better binding)
	hits.sort(key=lambda h: h["docking_score"])
	top_hits = hits[:top_n]

	if not top_hits:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Batch screening completed but no successful results. Errors: {'; '.join(errors)}.",
			raw_data={"errors": errors, "batch_name": batch_name},
		)

	best_score = top_hits[0]["docking_score"]
	confidence_delta, evidence_type = _score_to_evidence(best_score)

	return ToolResponse(
		status="success",
		confidence_delta=confidence_delta,
		evidence_type=evidence_type,
		summary=(
			f"Screened {len(compounds)} compounds against {protein_target} via {method}. "
			f"Top hit score: {best_score}. Returned top {len(top_hits)} hits."
		),
		raw_data={
			"top_hits": top_hits,
			"total_screened": len(compounds),
			"total_completed": len(hits),
			"errors": errors,
			"batch_name": batch_name,
		},
	)
