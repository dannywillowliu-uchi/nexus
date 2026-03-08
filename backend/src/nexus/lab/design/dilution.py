"""Serial dilution calculator with intermediate dilution detection.

Given a stock concentration and target concentrations, calculates transfer and
diluent volumes for each well. Flags concentrations that require intermediate
dilutions when the transfer volume falls below the pipette minimum.
"""

from __future__ import annotations

from nexus.lab.protocols.spec import DilutionStep


def calculate_dilutions(
	stock_concentration_uM: float,
	target_concentrations_uM: list[float],
	well_volume_uL: float = 100.0,
	min_pipette_volume_uL: float = 1.0,
	max_pipette_volume_uL: float = 200.0,
	max_dmso_fraction: float = 0.005,
	solvent: str = "DMSO",
) -> list[DilutionStep]:
	"""Calculate dilution steps for each target concentration.

	Returns a list of DilutionStep objects, flagging any that need intermediate
	dilutions due to pipette volume constraints.
	"""
	steps: list[DilutionStep] = []
	sorted_concs = sorted(target_concentrations_uM, reverse=True)

	for target in sorted_concs:
		if target <= 0 or stock_concentration_uM <= 0:
			continue

		# Direct dilution: C1*V1 = C2*V2 => V1 = (C2/C1) * V2
		transfer_uL = (target / stock_concentration_uM) * well_volume_uL
		diluent_uL = well_volume_uL - transfer_uL

		dmso_fraction = transfer_uL / well_volume_uL if solvent == "DMSO" else 0.0

		needs_intermediate = False
		intermediate_concentration_uM = 0.0
		intermediate_transfer_uL = 0.0
		intermediate_diluent_uL = 0.0

		if transfer_uL < min_pipette_volume_uL:
			# Need intermediate dilution
			needs_intermediate = True

			# Choose intermediate concentration so that the final transfer
			# volume is at least min_pipette_volume (aim for 2x minimum for safety)
			desired_transfer = min_pipette_volume_uL * 2
			intermediate_concentration_uM = (target * well_volume_uL) / desired_transfer

			# Ensure intermediate is less than stock
			if intermediate_concentration_uM >= stock_concentration_uM:
				intermediate_concentration_uM = stock_concentration_uM / 10

			# Volumes to prepare the intermediate (in a reservoir, e.g. 1000 uL total)
			intermediate_total_uL = 1000.0
			intermediate_transfer_uL = (intermediate_concentration_uM / stock_concentration_uM) * intermediate_total_uL
			intermediate_diluent_uL = intermediate_total_uL - intermediate_transfer_uL

			# Recalculate final transfer from intermediate
			transfer_uL = (target / intermediate_concentration_uM) * well_volume_uL
			diluent_uL = well_volume_uL - transfer_uL
			dmso_fraction = (
				(intermediate_transfer_uL / intermediate_total_uL) * (transfer_uL / well_volume_uL)
				if solvent == "DMSO"
				else 0.0
			)

		if transfer_uL > max_pipette_volume_uL:
			# Transfer volume too large — need to adjust well volume or stock
			transfer_uL = max_pipette_volume_uL
			diluent_uL = well_volume_uL - transfer_uL

		step = DilutionStep(
			target_concentration_uM=target,
			source_concentration_uM=intermediate_concentration_uM if needs_intermediate else stock_concentration_uM,
			transfer_volume_uL=round(transfer_uL, 3),
			diluent_volume_uL=round(max(diluent_uL, 0), 3),
			final_volume_uL=well_volume_uL,
			needs_intermediate=needs_intermediate,
			intermediate_concentration_uM=round(intermediate_concentration_uM, 3),
			intermediate_transfer_uL=round(intermediate_transfer_uL, 3),
			intermediate_diluent_uL=round(intermediate_diluent_uL, 3),
			dmso_fraction=round(dmso_fraction, 6),
		)
		steps.append(step)

	return steps
