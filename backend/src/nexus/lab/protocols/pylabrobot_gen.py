"""ExperimentSpec → executable PyLabRobot Python code.

Generates async Python code using the PyLabRobot library that can run against
a SimulatorBackend or real liquid handler. Handles tip management with fresh
tips per compound transfer to avoid cross-contamination.
"""

from __future__ import annotations

from nexus.lab.protocols.spec import ExperimentSpec


def generate_pylabrobot_code(spec: ExperimentSpec) -> str:
	"""Generate complete async PyLabRobot script from an ExperimentSpec."""
	lines: list[str] = []

	lines.append('"""')
	lines.append(f"Auto-generated PyLabRobot protocol for: {spec.hypothesis_title}")
	lines.append(f"Assay: {spec.assay.name}")
	lines.append(f"Compound: {spec.compound.name}")
	lines.append(f"Cell model: {spec.cell_model.name}")
	lines.append('"""')
	lines.append("")
	lines.append("import asyncio")
	lines.append("")
	lines.append("from pylabrobot.liquid_handling import LiquidHandler")
	lines.append("from pylabrobot.liquid_handling.backends.simulation import SimulatorBackend")
	lines.append("from pylabrobot.resources import Coordinate, Deck")
	lines.append("from pylabrobot.resources.opentrons import (")
	lines.append("\tcorning_96_wellplate_360ul_flat,")
	lines.append("\topentrons_96_tiprack_300ul,")
	lines.append("\tnest_12_reservoir_15ml,")
	lines.append(")")
	lines.append("")
	lines.append("")
	lines.append("async def run_protocol():")
	lines.append('\t"""Execute the liquid handling protocol."""')
	lines.append("")

	# Setup
	lines.append("\t# Initialize liquid handler with simulator backend")
	lines.append("\tbackend = SimulatorBackend(open_browser=False)")
	lines.append("\tdeck = Deck()")
	lines.append("\tlh = LiquidHandler(backend=backend, deck=deck)")
	lines.append("\tawait lh.setup()")
	lines.append("")

	# Labware
	lines.append("\t# Load labware")
	lines.append(f'\tprint("Loading labware for {spec.assay.assay_type} assay...")')
	lines.append("\ttiprack = opentrons_96_tiprack_300ul(\"tiprack_1\")")
	lines.append("\tdeck.assign_child_resource(tiprack, Coordinate(0, 0, 0))")
	lines.append("")
	lines.append('\tplate = corning_96_wellplate_360ul_flat("assay_plate")')
	lines.append("\tdeck.assign_child_resource(plate, Coordinate(200, 0, 0))")
	lines.append("")
	lines.append('\treservoir = nest_12_reservoir_15ml("reservoir")')
	lines.append("\tdeck.assign_child_resource(reservoir, Coordinate(400, 0, 0))")
	lines.append("")

	# Tip tracking
	lines.append("\ttip_idx = 0")
	lines.append("")

	# Generate compound transfers
	layout = spec.plate_layout.layout
	dilution_map: dict[float, object] = {}
	for step in spec.dilution_steps:
		dilution_map[step.target_concentration_uM] = step

	compound_conditions = [
		(label, wells) for label, wells in layout.items() if "ctrl" not in label and "blank" not in label
	]

	if compound_conditions:
		lines.append(f'\tprint("Transferring {spec.compound.name} to assay plate...")')
		lines.append("")

		for label, wells in compound_conditions:
			# Parse concentration from label
			conc_str = label.rsplit("_", 1)[-1].replace("uM", "")
			try:
				conc = float(conc_str)
			except ValueError:
				conc = 0

			step = dilution_map.get(conc)
			vol = step.transfer_volume_uL if step else 10.0

			lines.append(f"\t# {spec.compound.name} at {conc_str} uM -> wells {', '.join(wells)}")
			for well in wells:
				lines.append(f"\t# Fresh tip for {well} to avoid cross-contamination")
				lines.append("\tawait lh.pick_up_tips(tiprack[tip_idx])")
				lines.append(f'\tawait lh.aspirate(reservoir["A1"], vol={vol})')
				lines.append(f'\tawait lh.dispense(plate["{well}"], vol={vol})')
				lines.append("\tawait lh.return_tips()")
				lines.append("\ttip_idx += 1")
			lines.append("")

	# Generate control transfers
	control_conditions = [(label, wells) for label, wells in layout.items() if "ctrl" in label or "blank" in label]

	if control_conditions:
		lines.append('\tprint("Adding controls...")')
		lines.append("")

		for label, wells in control_conditions:
			ctrl_type = label.replace("_ctrl", "").replace("_", " ")
			lines.append(f"\t# {ctrl_type} control -> wells {', '.join(wells)}")
			for well in wells:
				lines.append("\tawait lh.pick_up_tips(tiprack[tip_idx])")
				lines.append('\tawait lh.aspirate(reservoir["A2"], vol=10)')
				lines.append(f'\tawait lh.dispense(plate["{well}"], vol=10)')
				lines.append("\tawait lh.return_tips()")
				lines.append("\ttip_idx += 1")
			lines.append("")

	# Cleanup
	lines.append(f'\tprint("Protocol complete. {spec.plate_layout.total_wells_used} wells prepared.")')
	lines.append(f'\tprint("Assay: {spec.assay.name}")')
	lines.append(f'\tprint("Next: incubate {spec.assay.incubation_time_hours}h at {spec.assay.temperature_C}C")')
	lines.append("")
	lines.append("\tawait lh.stop()")
	lines.append("\treturn {")
	lines.append('\t\t"status": "complete",')
	lines.append(f'\t\t"wells_prepared": {spec.plate_layout.total_wells_used},')
	lines.append(f'\t\t"compound": "{spec.compound.name}",')
	lines.append(f'\t\t"assay": "{spec.assay.assay_type}",')
	lines.append("\t}")
	lines.append("")
	lines.append("")
	lines.append('if __name__ == "__main__":')
	lines.append("\tasyncio.run(run_protocol())")
	lines.append("")

	return "\n".join(lines)
