"""Decision tree: hypothesis → assay type.

Selects the appropriate assay based on the hypothesis type, intermediary entity
type, and available structural/functional data.
"""

from __future__ import annotations

import json
from pathlib import Path

from nexus.lab.protocols.spec import AssaySpec, ControlSpec, ReadoutSpec, SuccessCriteria

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_protocol_library() -> dict:
	path = DATA_DIR / "assay_protocols.json"
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)


def _normalize_entity_type(raw: str) -> str:
	"""Normalize entity type strings across knowledge graphs (Hetionet, PrimeKG)."""
	mapping = {
		# PrimeKG types → canonical
		"gene/protein": "Gene",
		"drug": "Compound",
		"biological_process": "BiologicalProcess",
		"molecular_function": "MolecularFunction",
		"cellular_component": "CellularComponent",
		"effect/phenotype": "SideEffect",
		"exposure": "Exposure",
		"anatomy": "Anatomy",
		# Hetionet types (already canonical)
		"gene": "Gene",
		"compound": "Compound",
		"disease": "Disease",
		"biologicalprocess": "BiologicalProcess",
		"pathway": "Pathway",
		"pharmacologicclass": "PharmacologicClass",
		"sideeffect": "SideEffect",
		"symptom": "Symptom",
	}
	return mapping.get(raw.lower().replace(" ", ""), raw)


def select_assay(
	hypothesis_type: str,
	intermediary_type: str = "",
	has_pdb_structure: bool = False,
	is_receptor_or_enzyme: bool = False,
	has_known_reporter: bool = False,
) -> AssaySpec:
	"""Select assay type using a decision tree based on hypothesis characteristics.

	Accepts entity types from Hetionet ("Gene") or PrimeKG ("gene/protein").

	Decision logic:
	- Gene intermediary + PDB structure + receptor/enzyme → fluorescence_polarization
	- Gene intermediary + no structural data → MTT_viability
	- Pathway intermediary + known reporter → luciferase_reporter
	- BiologicalProcess intermediary → MTT_viability
	- Default fallback → MTT_viability
	"""
	assay_type = "MTT_viability"
	normalized = _normalize_entity_type(intermediary_type)

	if normalized == "Gene":
		if has_pdb_structure and is_receptor_or_enzyme:
			assay_type = "fluorescence_polarization"
		else:
			assay_type = "MTT_viability"
	elif normalized == "Pathway":
		if has_known_reporter:
			assay_type = "luciferase_reporter"
		else:
			assay_type = "MTT_viability"
	elif normalized == "BiologicalProcess":
		assay_type = "MTT_viability"

	return _build_assay_spec(assay_type)


def _build_assay_spec(assay_type: str) -> AssaySpec:
	"""Load assay spec from the protocol library JSON."""
	library = _load_protocol_library()
	proto = library.get(assay_type)

	if not proto:
		proto = library.get("MTT_viability", {})
		assay_type = "MTT_viability"

	readout_data = proto.get("readout", {})
	readout = ReadoutSpec(
		readout_type=readout_data.get("readout_type", "absorbance"),
		wavelength_nm=readout_data.get("wavelength_nm", 570),
		excitation_nm=readout_data.get("excitation_nm", 0),
		emission_nm=readout_data.get("emission_nm", 0),
		read_time_minutes=readout_data.get("read_time_minutes", 5),
		instrument=readout_data.get("instrument", "microplate_reader"),
	)

	controls = [
		ControlSpec(
			control_type=c.get("control_type", ""),
			description=c.get("description", ""),
			compound_name=c.get("compound_name", ""),
			concentration_uM=c.get("concentration_uM", 0),
			expected_response=c.get("expected_response", ""),
		)
		for c in proto.get("controls", [])
	]

	sc = proto.get("success_criteria", {})
	criteria = SuccessCriteria(
		min_z_factor=sc.get("min_z_factor", 0.5),
		max_cv_percent=sc.get("max_cv_percent", 20.0),
		min_signal_to_background=sc.get("min_signal_to_background", 3.0),
		significance_threshold=sc.get("significance_threshold", 0.05),
	)

	return AssaySpec(
		assay_type=assay_type,
		name=proto.get("name", assay_type),
		description=proto.get("description", ""),
		readout=readout,
		incubation_time_hours=proto.get("incubation_time_hours", 24),
		temperature_C=proto.get("temperature_C", 37),
		co2_percent=proto.get("co2_percent", 5),
		reagent_steps=proto.get("reagent_steps", []),
		total_time_hours=proto.get("total_time_hours", 48),
		controls=controls,
		success_criteria=criteria,
	)
