"""Well assignment algorithm for assay plates.

Assigns compound concentrations, controls, and blanks to plate wells
row-by-row with configurable replicates and plate formats.
"""

from __future__ import annotations

from nexus.lab.protocols.spec import ControlSpec, PlateLayout


def _well_labels(plate_type: str) -> list[str]:
	"""Generate well labels for a plate format, row-by-row."""
	if "384" in plate_type:
		rows = "ABCDEFGHIJKLMNOP"
		cols = range(1, 25)
	else:
		rows = "ABCDEFGH"
		cols = range(1, 13)
	return [f"{r}{c}" for r in rows for c in cols]


def generate_plate_layout(
	concentrations_uM: list[float],
	compound_name: str = "compound",
	replicates: int = 3,
	controls: list[ControlSpec] | None = None,
	plate_type: str = "96-well",
) -> PlateLayout:
	"""Assign wells row-by-row: compound concentrations (high→low), controls, blanks.

	Returns a PlateLayout with a dict mapping condition names to well lists.
	"""
	if controls is None:
		controls = [
			ControlSpec(control_type="positive", description="Cytotoxic positive control"),
			ControlSpec(control_type="negative", description="Vehicle control"),
			ControlSpec(control_type="blank", description="Medium only"),
		]

	wells = _well_labels(plate_type)
	plate_catalog = "corning_384_wellplate_112ul_flat" if "384" in plate_type else "corning_96_wellplate_360ul_flat"

	layout: dict[str, list[str]] = {}
	idx = 0

	# Compound concentrations (highest to lowest)
	sorted_concs = sorted(concentrations_uM, reverse=True)
	for conc in sorted_concs:
		label = f"{compound_name}_{conc}uM"
		assigned = wells[idx : idx + replicates]
		if assigned:
			layout[label] = assigned
			idx += len(assigned)

	# Controls
	for ctrl in controls:
		label = f"{ctrl.control_type}_ctrl"
		assigned = wells[idx : idx + replicates]
		if assigned:
			layout[label] = assigned
			idx += len(assigned)

	return PlateLayout(
		plate_type=plate_type,
		plate_catalog=plate_catalog,
		layout=layout,
		replicates=replicates,
	)
