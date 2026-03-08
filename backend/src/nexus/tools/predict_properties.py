"""Molecular/protein property prediction via Tamarind Bio."""

from __future__ import annotations

import asyncio

from nexus.config import settings
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient

SUPPORTED_PROPERTIES = {"solubility", "thermostability", "immunogenicity"}


async def predict_properties(
	sequence_or_smiles: str,
	properties: list[str] | None = None,
) -> ToolResponse:
	"""Predict molecular properties like solubility, thermostability, drug-likeness.

	Properties: solubility, thermostability, immunogenicity.
	If properties is None, all supported properties are predicted.
	"""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary="Property prediction skipped: no Tamarind Bio API key configured.",
			raw_data={"reason": "missing_api_key"},
		)

	requested = set(properties) if properties else SUPPORTED_PROPERTIES
	unsupported = requested - SUPPORTED_PROPERTIES
	if unsupported:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Unsupported properties: {', '.join(sorted(unsupported))}. Use: {', '.join(sorted(SUPPORTED_PROPERTIES))}.",
			raw_data={"reason": "unsupported_properties", "unsupported": sorted(unsupported)},
		)

	client = TamarindClient()
	input_hash = hash(sequence_or_smiles) % 100000

	async def _run_single(prop: str) -> tuple[str, dict | None, str | None]:
		"""Run a single property prediction. Returns (property, result_data, error)."""
		job_name = f"nexus-prop-{prop}-{input_hash:05d}"
		try:
			result = await client.run_job(
				job_name=job_name,
				job_type=prop,
				settings={"target": sequence_or_smiles},
			)
			if result.get("status") == "Complete":
				return prop, result.get("result", {}), None
			return prop, None, f"Job ended with status: {result.get('status')}"
		except TimeoutError:
			return prop, None, "timeout"
		except Exception as exc:
			return prop, None, str(exc)

	# Run all property predictions concurrently
	tasks = [_run_single(prop) for prop in sorted(requested)]
	outcomes = await asyncio.gather(*tasks)

	aggregated: dict[str, dict] = {}
	errors: list[str] = []
	for prop, result_data, error in outcomes:
		if error:
			errors.append(f"{prop}: {error}")
		else:
			aggregated[prop] = result_data or {}

	if not aggregated and errors:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"All property predictions failed: {'; '.join(errors)}.",
			raw_data={"errors": errors},
		)

	# Derive overall evidence from aggregated results
	confidence_delta, evidence_type = _aggregate_evidence(aggregated)

	status = "success" if not errors else "partial"
	prop_names = ", ".join(sorted(aggregated.keys()))
	summary = f"Predicted properties ({prop_names}) for input (len={len(sequence_or_smiles)})."
	if errors:
		summary += f" Errors: {'; '.join(errors)}."

	return ToolResponse(
		status=status,
		confidence_delta=confidence_delta,
		evidence_type=evidence_type,
		summary=summary,
		raw_data={"properties": aggregated, "errors": errors},
	)


def _aggregate_evidence(results: dict[str, dict]) -> tuple[float, str]:
	"""Combine property prediction results into a single evidence assessment."""
	if not results:
		return 0.0, "neutral"

	# Each successful prediction contributes a small positive delta
	delta = 0.1 * len(results)
	return min(delta, 0.3), "supporting"
