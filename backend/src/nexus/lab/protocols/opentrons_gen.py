"""ExperimentSpec → Opentrons Protocol API v2.

Generates Python code for the Opentrons OT-2 robot using the Protocol API v2
with proper labware loading, pipette configuration, and transfer sequences.
"""

from __future__ import annotations

from nexus.lab.protocols.spec import ExperimentSpec


def generate_opentrons_code(spec: ExperimentSpec) -> str:
	"""Generate Opentrons Protocol API v2 Python script from an ExperimentSpec."""
	lines: list[str] = []

	lines.append('"""')
	lines.append(f"Auto-generated Opentrons OT-2 protocol for: {spec.hypothesis_title}")
	lines.append(f"Assay: {spec.assay.name}")
	lines.append(f"Compound: {spec.compound.name}")
	lines.append('"""')
	lines.append("")
	lines.append("from opentrons import protocol_api")
	lines.append("")
	lines.append("metadata = {")
	lines.append(f'\t"protocolName": "{spec.assay.name} - {spec.compound.name}",')
	lines.append('\t"author": "Nexus Autonomous Discovery Platform",')
	lines.append(f'\t"description": "{spec.hypothesis_title}",')
	lines.append('\t"apiLevel": "2.15",')
	lines.append("}")
	lines.append("")
	lines.append("")
	lines.append("def run(protocol: protocol_api.ProtocolContext):")
	lines.append("")

	# Labware
	lines.append('\t# Load labware')
	lines.append('\ttiprack = protocol.load_labware("opentrons_96_tiprack_300ul", 1)')
	plate_labware = "corning_384_wellplate_112ul_flat" if "384" in spec.plate_layout.plate_type else "corning_96_wellplate_360ul_flat"
	lines.append(f'\tplate = protocol.load_labware("{plate_labware}", 2)')
	lines.append('\treservoir = protocol.load_labware("nest_12_reservoir_15ml", 3)')
	lines.append("")

	# Pipette
	lines.append('\t# Load pipette')
	lines.append('\tp300 = protocol.load_instrument("p300_single_gen2", "right", tip_racks=[tiprack])')
	lines.append("")

	# Build dilution lookup
	lines.append(f'\tprotocol.comment("Starting {spec.assay.assay_type} protocol for {spec.compound.name}")')
	lines.append("")

	layout = spec.plate_layout.layout
	dilution_map: dict[float, object] = {}
	for step in spec.dilution_steps:
		dilution_map[step.target_concentration_uM] = step

	# Compound transfers
	compound_conditions = [
		(label, wells) for label, wells in layout.items() if "ctrl" not in label and "blank" not in label
	]

	if compound_conditions:
		lines.append(f'\tprotocol.comment("Transferring {spec.compound.name} dilutions...")')
		lines.append("")

		for label, wells in compound_conditions:
			conc_str = label.rsplit("_", 1)[-1].replace("uM", "")
			try:
				conc = float(conc_str)
			except ValueError:
				conc = 0

			step = dilution_map.get(conc)
			vol = step.transfer_volume_uL if step else 10.0

			lines.append(f'\t# {spec.compound.name} at {conc_str} uM')
			lines.append('\tp300.transfer(')
			lines.append(f"\t\t{vol},")
			lines.append('\t\treservoir["A1"],')
			well_list = ", ".join(f'plate["{w}"]' for w in wells)
			lines.append(f"\t\t[{well_list}],")
			lines.append("\t\tnew_tip='always',")
			lines.append("\t)")
			lines.append("")

	# Control transfers
	control_conditions = [(label, wells) for label, wells in layout.items() if "ctrl" in label or "blank" in label]

	if control_conditions:
		lines.append('\tprotocol.comment("Adding controls...")')
		lines.append("")

		for label, wells in control_conditions:
			ctrl_type = label.replace("_ctrl", "")
			lines.append(f"\t# {ctrl_type} control")
			lines.append("\tp300.transfer(")
			lines.append("\t\t10,")
			lines.append('\t\treservoir["A2"],')
			well_list = ", ".join(f'plate["{w}"]' for w in wells)
			lines.append(f"\t\t[{well_list}],")
			lines.append("\t\tnew_tip='always',")
			lines.append("\t)")
			lines.append("")

	lines.append(f'\tprotocol.comment("Protocol complete. {spec.plate_layout.total_wells_used} wells prepared.")')
	lines.append("")

	return "\n".join(lines)
