"""Agent tool wrappers for the lab package.

Exports 6 functions that the reasoning/validation agents call:
- resolve_compound: Name → structured compound data
- design_experiment: Hypothesis → full ExperimentSpec
- validate_and_execute_protocol: ExperimentSpec → simulation or cloud lab results
- submit_to_cloud_lab: ExperimentSpec → submission ID
- poll_and_retrieve: Submission ID → results + interpretation
- interpret_results: ExperimentSpec + results → verdict
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from nexus.lab.design.assay_selector import select_assay
from nexus.lab.design.dilution import calculate_dilutions
from nexus.lab.design.plate_layout import generate_plate_layout
from nexus.lab.design.validator import validate_protocol
from nexus.lab.execution.results_sim import generate_simulated_results
from nexus.lab.execution.simulator import dry_run
from nexus.lab.interpretation.interpreter import interpret_results as _interpret
from nexus.lab.protocols.pylabrobot_gen import generate_pylabrobot_code
from nexus.lab.protocols.spec import (
	CellModelSpec,
	CompoundSpec,
	ExperimentSpec,
)
from nexus.lab.resolvers.cell_line import resolve_cell_line_local
from nexus.lab.resolvers.compound import resolve_compound as _resolve_compound

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"


async def resolve_compound(compound_name: str) -> dict:
	"""Resolve a compound name to structured identifiers.

	Checks local cache, then queries PubChem + UniChem.
	Returns a JSON-serializable dict with CID, SMILES, InChIKey, MW, CAS, etc.
	"""
	spec = await _resolve_compound(compound_name)
	return spec.to_dict()


async def design_experiment(
	hypothesis: dict,
	compound_info: dict | None = None,
	budget_tier: str = "minimal",
) -> dict:
	"""Design a complete experiment from a hypothesis.

	Takes a hypothesis dict (from the pipeline) and optional pre-resolved
	compound info. Returns a full ExperimentSpec as a JSON-serializable dict.
	"""
	# Extract hypothesis fields
	hypothesis_id = hypothesis.get("id", hypothesis.get("hypothesis_id", ""))
	hypothesis_title = hypothesis.get("title", hypothesis.get("hypothesis_title", ""))
	hypothesis_type = hypothesis.get("hypothesis_type", "drug_repurposing")
	disease_area = hypothesis.get("disease_area", "")

	# Extract ABC path info
	abc_path = hypothesis.get("abc_path", {})
	a_entity = abc_path.get("a", {})
	b_entity = abc_path.get("b", {})
	c_entity = abc_path.get("c", {})

	# Resolve compound
	if compound_info:
		compound = CompoundSpec.from_dict(compound_info)
	else:
		compound_name = c_entity.get("name", "") or a_entity.get("name", "")
		if compound_name:
			compound = await _resolve_compound(compound_name)
		else:
			compound = CompoundSpec(name="unknown")

	# Adjust concentrations based on budget tier
	# Max concentration is capped so DMSO stays below 0.5% of well volume:
	# max_conc = stock * 0.005  (e.g. 10,000 uM stock → 50 uM max)
	max_conc = compound.stock_concentration_uM * 0.005
	if budget_tier == "minimal":
		concs = [50, 10, 1, 0.1]
	elif budget_tier == "standard":
		concs = [50, 25, 10, 5, 1, 0.5, 0.1]
	else:  # full
		concs = [50, 25, 10, 5, 2.5, 1, 0.5, 0.25, 0.1, 0.01]
	compound.test_concentrations_uM = [c for c in concs if c <= max_conc]
	if not compound.test_concentrations_uM:
		compound.test_concentrations_uM = [max_conc, max_conc / 5, max_conc / 50, max_conc / 500]

	# Resolve cell model
	cell_model = resolve_cell_line_local(disease_area)
	if not cell_model:
		cell_model = CellModelSpec(name="HeLa", atcc_number="CCL-2", culture_medium="DMEM", serum="10% FBS")

	# Resolve protein target if intermediary is a gene
	from nexus.lab.design.assay_selector import _normalize_entity_type

	protein_target = None
	b_type = _normalize_entity_type(b_entity.get("type", ""))
	if b_type == "Gene":
		from nexus.lab.resolvers.protein import has_structural_data, is_receptor_or_enzyme, resolve_protein
		protein_target = await resolve_protein(b_entity.get("name", ""))
		has_pdb = has_structural_data(protein_target)
		is_rec_enz = is_receptor_or_enzyme(protein_target)
	else:
		has_pdb = False
		is_rec_enz = False

	# Select assay
	assay = select_assay(
		hypothesis_type=hypothesis_type,
		intermediary_type=b_type,
		has_pdb_structure=has_pdb,
		is_receptor_or_enzyme=is_rec_enz,
	)

	# Calculate dilutions
	dilution_steps = calculate_dilutions(
		stock_concentration_uM=compound.stock_concentration_uM,
		target_concentrations_uM=compound.test_concentrations_uM,
		solvent=compound.solvent,
	)

	# Generate plate layout
	plate_layout = generate_plate_layout(
		concentrations_uM=compound.test_concentrations_uM,
		compound_name=compound.name.lower().replace(" ", "_"),
		replicates=3,
		controls=assay.controls,
	)

	# Build spec
	spec = ExperimentSpec(
		hypothesis_id=str(hypothesis_id),
		hypothesis_title=hypothesis_title,
		hypothesis_type=hypothesis_type,
		disease_area=disease_area,
		compound=compound,
		cell_model=cell_model,
		protein_target=protein_target,
		assay=assay,
		plate_layout=plate_layout,
		dilution_steps=dilution_steps,
		budget_tier=budget_tier,
	)

	return spec.to_dict()


async def validate_and_execute_protocol(
	experiment_spec: dict,
	backend: str = "simulator",
	hypothesis_plausibility: float = 0.6,
) -> dict:
	"""Validate an experiment spec and execute the protocol.

	Backends:
	- "simulator": Generate simulated results (no real lab)
	- "strateos": Submit to Strateos cloud lab, poll until complete, retrieve
	- "dry_run": Validate + generate code only (no execution)

	Returns a dict with validation, code, and results.
	"""
	spec = ExperimentSpec.from_dict(experiment_spec)

	# Validate
	validation = validate_protocol(spec)
	result: dict = {
		"validation": validation.to_dict(),
	}

	if not validation.valid:
		result["status"] = "validation_failed"
		return result

	# Generate protocol code
	code = generate_pylabrobot_code(spec)
	result["protocol_code"] = code

	# Dry run (syntax check)
	sim_result = await dry_run(code)
	result["dry_run"] = sim_result.to_dict()

	if not sim_result.success:
		result["status"] = "code_generation_error"
		return result

	if backend == "simulator":
		sim_results = generate_simulated_results(spec, hypothesis_plausibility=hypothesis_plausibility)
		result["simulated_results"] = sim_results.to_dict()
		result["status"] = "simulation_complete"

	elif backend == "strateos":
		submission = await submit_to_cloud_lab(experiment_spec, provider="strateos")
		result["submission"] = submission
		if submission.get("status") == "submitted":
			retrieval = await poll_and_retrieve(
				submission_id=submission["submission_id"],
				experiment_spec=experiment_spec,
				provider="strateos",
			)
			result["cloud_lab_results"] = retrieval
			result["status"] = retrieval.get("status", "error")
		else:
			result["status"] = "submission_failed"

	else:
		result["status"] = "code_ready"

	return result


async def submit_to_cloud_lab(
	experiment_spec: dict,
	provider: str = "strateos",
) -> dict:
	"""Submit an experiment to a cloud lab provider.

	Converts ExperimentSpec to the provider's protocol format, validates,
	and submits. Returns submission metadata.
	"""
	from nexus.cloudlab.provider import ExperimentProtocol

	spec = ExperimentSpec.from_dict(experiment_spec)

	# Build provider-specific protocol JSON from the ExperimentSpec
	protocol_json = _build_provider_protocol(spec, provider)
	protocol = ExperimentProtocol(
		hypothesis_id=spec.hypothesis_id,
		title=f"{spec.assay.name} - {spec.compound.name}",
		description=spec.hypothesis_title,
		protocol_json=protocol_json,
	)

	lab_provider = _get_provider(provider)

	# Validate with provider
	validation = await lab_provider.validate_protocol(protocol)
	if validation.get("error"):
		return {
			"status": "validation_failed",
			"provider": provider,
			"error": validation,
		}

	# Submit
	submission = await lab_provider.submit_experiment(protocol)
	return {
		"submission_id": submission.submission_id,
		"provider": submission.provider,
		"status": submission.status,
	}


async def poll_and_retrieve(
	submission_id: str,
	experiment_spec: dict,
	provider: str = "strateos",
	poll_interval_seconds: int = 60,
	max_polls: int = 120,
) -> dict:
	"""Poll a cloud lab for results, then interpret them.

	Polls until status is "completed" or "failed", retrieves raw results,
	converts to dose-response format, and runs interpretation.
	"""
	lab_provider = _get_provider(provider)

	# Poll loop
	for i in range(max_polls):
		status = await lab_provider.poll_status(submission_id)
		logger.info("Poll %d/%d for %s: %s", i + 1, max_polls, submission_id, status)

		if status == "completed":
			break
		elif "failed" in status or "error" in status:
			return {
				"status": "failed",
				"submission_id": submission_id,
				"error": status,
			}

		if i < max_polls - 1:
			await asyncio.sleep(poll_interval_seconds)
	else:
		return {
			"status": "timeout",
			"submission_id": submission_id,
			"polls": max_polls,
		}

	# Retrieve raw results
	results = await lab_provider.get_results(submission_id)

	if results.status != "completed":
		return {
			"status": "failed",
			"submission_id": submission_id,
			"error": results.data,
		}

	# Convert cloud lab results to our standard format for interpretation
	normalized_results = _normalize_cloud_results(results.data, experiment_spec)

	# Interpret
	interpretation = await interpret_results(experiment_spec, normalized_results)

	return {
		"status": "completed",
		"submission_id": submission_id,
		"raw_data": results.data,
		"normalized_results": normalized_results,
		"interpretation": interpretation,
	}


async def interpret_results(
	experiment_spec: dict,
	raw_results: dict,
) -> dict:
	"""Interpret experimental results and return a verdict.

	Uses Claude for intelligent interpretation, with a rule-based fallback
	if no API key is configured.

	Returns dict with verdict, confidence, reasoning, concerns, and next_steps.
	"""
	return await _interpret(experiment_spec, raw_results)


# --- Internal helpers ---


def _get_provider(provider: str):
	"""Instantiate a cloud lab provider by name."""
	if provider == "strateos":
		from nexus.cloudlab.strateos import StrateosProvider
		return StrateosProvider()
	raise ValueError(f"Unknown cloud lab provider: {provider}")


def _build_provider_protocol(spec: ExperimentSpec, provider: str) -> dict:
	"""Convert ExperimentSpec to provider-specific protocol JSON."""
	if provider == "strateos":
		return _build_autoprotocol(spec)
	return spec.to_dict()


def _build_autoprotocol(spec: ExperimentSpec) -> dict:
	"""Build Autoprotocol JSON from ExperimentSpec for Strateos."""
	instructions = []

	# Provision plate
	instructions.append({
		"op": "provision",
		"to": [{"well": well, "volume": f"{100}:microliter"} for wells in spec.plate_layout.layout.values() for well in wells],
		"resource_id": spec.plate_layout.plate_catalog,
	})

	# Compound transfers
	for step in spec.dilution_steps:
		condition_label = f"{spec.compound.name}_{step.target_concentration_uM}uM"
		wells = spec.plate_layout.layout.get(condition_label, [])
		for well in wells:
			instructions.append({
				"op": "pipette",
				"groups": [{
					"transfer": [{
						"from": "compound_stock/0",
						"to": f"assay_plate/{well}",
						"volume": f"{step.transfer_volume_uL}:microliter",
						"mix_after": {"volume": "50:microliter", "repetitions": 3},
					}],
				}],
			})

	# Incubation
	instructions.append({
		"op": "incubate",
		"object": "assay_plate",
		"where": "warm_37",
		"duration": f"{spec.assay.incubation_time_hours}:hour",
		"co2_percent": spec.assay.co2_percent,
	})

	# Readout
	readout = spec.assay.readout
	if readout.readout_type == "absorbance":
		instructions.append({
			"op": "absorbance",
			"object": "assay_plate",
			"wavelength": f"{readout.wavelength_nm}:nanometer",
			"dataref": "plate_read",
		})
	elif readout.readout_type == "fluorescence":
		instructions.append({
			"op": "fluorescence",
			"object": "assay_plate",
			"excitation": f"{readout.excitation_nm}:nanometer",
			"emission": f"{readout.emission_nm}:nanometer",
			"dataref": "plate_read",
		})
	elif readout.readout_type == "luminescence":
		instructions.append({
			"op": "luminescence",
			"object": "assay_plate",
			"dataref": "plate_read",
		})

	return {
		"refs": {
			"assay_plate": {
				"new": spec.plate_layout.plate_catalog,
				"store": {"where": "cold_4"},
			},
			"compound_stock": {
				"id": spec.compound.catalog_number or "user_provided",
				"store": {"where": "cold_20"},
			},
		},
		"instructions": instructions,
	}


def _normalize_cloud_results(raw_data: dict, experiment_spec: dict) -> dict:
	"""Convert cloud lab raw results to our standard dose-response format.

	Extracts plate reader data and organizes it by condition for interpretation.
	"""
	spec = ExperimentSpec.from_dict(experiment_spec)

	# Map well → condition from plate layout
	well_to_condition: dict[str, str] = {}
	for condition, wells in spec.plate_layout.layout.items():
		for well in wells:
			well_to_condition[well] = condition

	# Extract readout values from raw data
	plate_read = raw_data.get("plate_read", raw_data.get("data", {}))
	condition_values: dict[str, list[float]] = {}

	for well, value in plate_read.items():
		condition = well_to_condition.get(well, "unknown")
		if condition not in condition_values:
			condition_values[condition] = []
		try:
			condition_values[condition].append(float(value))
		except (ValueError, TypeError):
			continue

	# Build dose-response table
	dose_response = []
	concentrations = sorted(spec.compound.test_concentrations_uM, reverse=True)
	compound_key = spec.compound.name.lower().replace(" ", "_")

	for conc in concentrations:
		label = f"{compound_key}_{conc}uM"
		values = condition_values.get(label, [])
		if not values:
			continue
		mean_val = sum(values) / len(values)
		std_val = (sum((v - mean_val) ** 2 for v in values) / max(len(values) - 1, 1)) ** 0.5 if len(values) > 1 else 0
		cv = (std_val / mean_val * 100) if mean_val > 0 else 0
		dose_response.append({
			"concentration_uM": conc,
			"mean_response": round(mean_val, 4),
			"std": round(std_val, 4),
			"cv_percent": round(cv, 2),
			"n": len(values),
		})

	# QC from controls
	neg_values = condition_values.get("negative_ctrl", [])
	pos_values = condition_values.get("positive_ctrl", [])

	qc_metrics: dict = {}
	if neg_values and pos_values:
		mean_neg = sum(neg_values) / len(neg_values)
		mean_pos = sum(pos_values) / len(pos_values)
		std_neg = (sum((v - mean_neg) ** 2 for v in neg_values) / max(len(neg_values) - 1, 1)) ** 0.5 if len(neg_values) > 1 else 0
		std_pos = (sum((v - mean_pos) ** 2 for v in pos_values) / max(len(pos_values) - 1, 1)) ** 0.5 if len(pos_values) > 1 else 0
		separation = abs(mean_neg - mean_pos)
		z_factor = 1 - 3 * (std_neg + std_pos) / separation if separation > 0 else -1
		qc_metrics = {
			"z_factor": round(z_factor, 4),
			"signal_to_background": round(mean_neg / mean_pos, 2) if mean_pos > 0 else 0,
			"cv_percent": 0,
			"negative_ctrl_mean": round(mean_neg, 4),
			"positive_ctrl_mean": round(mean_pos, 4),
		}

	return {
		"raw_data": condition_values,
		"dose_response": dose_response,
		"qc_metrics": qc_metrics,
		"analysis": {"summary": f"Cloud lab results for {spec.compound.name}"},
	}
