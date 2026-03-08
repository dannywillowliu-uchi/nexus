"""ExperimentSpec → ECL Symbolic Lab Language.

ECL is declarative — describes WHAT to do, not HOW. Uses Emerald Cloud Lab's
symbolic notation for experiments with built-in unit system.
"""

from __future__ import annotations

from nexus.lab.protocols.spec import ExperimentSpec


# Mapping from assay types to ECL experiment functions
ECL_EXPERIMENT_MAP = {
	"MTT_viability": "ExperimentMTT",
	"resazurin_viability": "ExperimentAlamarBlue",
	"fluorescence_polarization": "ExperimentFluorescencePolarization",
	"luciferase_reporter": "ExperimentLuciferaseReporter",
	"ELISA": "ExperimentELISA",
	"qPCR": "ExperimentqPCR",
}


def generate_ecl_code(spec: ExperimentSpec) -> str:
	"""Generate ECL Symbolic Lab Language from an ExperimentSpec."""
	ecl_func = ECL_EXPERIMENT_MAP.get(spec.assay.assay_type, "ExperimentMTT")
	lines: list[str] = []

	lines.append(f"(* Auto-generated ECL protocol for: {spec.hypothesis_title} *)")
	lines.append(f"(* Assay: {spec.assay.name} *)")
	lines.append(f"(* Compound: {spec.compound.name} *)")
	lines.append("")

	lines.append(f"protocol = {ecl_func}[")

	# Cell line
	if spec.cell_model.name != "unknown":
		lines.append(f'\tCellLine -> Model[CellLine, "{spec.cell_model.name}"],')

	# Analytes with concentrations
	concs = spec.compound.test_concentrations_uM
	conc_list = ", ".join(f"{c} Micromolar" for c in sorted(concs, reverse=True))
	lines.append(f'\tAnalytes -> {{Model[Molecule, "{spec.compound.name}"]}},')
	lines.append(f"\tAnalyteConcentrations -> {{{{{conc_list}}}}},")

	# Controls
	controls_ecl = []
	for ctrl in spec.assay.controls:
		if ctrl.control_type == "positive":
			controls_ecl.append(f'\t\tPositiveControl -> "{ctrl.description}"')
		elif ctrl.control_type == "negative":
			controls_ecl.append(f'\t\tNegativeControl -> "{ctrl.description}"')
		elif ctrl.control_type == "blank":
			controls_ecl.append(f'\t\tBlankControl -> "{ctrl.description}"')
	if controls_ecl:
		lines.append("\tControls -> {")
		lines.append(",\n".join(controls_ecl))
		lines.append("\t},")

	# Detection
	readout = spec.assay.readout
	if readout.readout_type == "absorbance":
		lines.append(f"\tDetectionWavelength -> {readout.wavelength_nm} Nanometer,")
	elif readout.readout_type == "fluorescence":
		lines.append(f"\tExcitationWavelength -> {readout.excitation_nm} Nanometer,")
		lines.append(f"\tEmissionWavelength -> {readout.emission_nm} Nanometer,")

	# Replicates and incubation
	lines.append(f"\tNumberOfReplicates -> {spec.plate_layout.replicates},")
	lines.append(f"\tIncubationTime -> {spec.assay.incubation_time_hours} Hour,")
	lines.append(f"\tIncubationTemperature -> {spec.assay.temperature_C} Celsius,")

	# Plate format
	plate_wells = 384 if "384" in spec.plate_layout.plate_type else 96
	lines.append(f"\tPlateFormat -> {plate_wells}Well,")

	# QC criteria
	sc = spec.assay.success_criteria
	lines.append(f"\tMinZFactor -> {sc.min_z_factor},")
	lines.append(f"\tMaxCV -> {sc.max_cv_percent} Percent")

	lines.append("]")
	lines.append("")

	return "\n".join(lines)
