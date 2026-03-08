"""Protocol validation — catches errors before they hit the robot.

Checks transfer volumes, plate capacity, DMSO tolerance, control presence,
and solubility concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus.lab.protocols.spec import ExperimentSpec


@dataclass
class ValidationResult:
	errors: list[str] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)

	@property
	def valid(self) -> bool:
		return len(self.errors) == 0

	def to_dict(self) -> dict:
		return {
			"errors": self.errors,
			"warnings": self.warnings,
			"valid": self.valid,
		}


# Compounds with known aqueous solubility issues in DMSO
INSOLUBLE_IN_DMSO = {"proteins", "antibodies", "peptides", "biologics"}


def validate_protocol(spec: ExperimentSpec) -> ValidationResult:
	"""Validate an ExperimentSpec for pipetting feasibility and experimental correctness."""
	result = ValidationResult()

	# 1. Transfer volume checks
	for step in spec.dilution_steps:
		if step.transfer_volume_uL < 1.0 and not step.needs_intermediate:
			result.errors.append(
				f"Transfer volume {step.transfer_volume_uL} uL for {step.target_concentration_uM} uM "
				f"is below 1 uL minimum. Intermediate dilution required."
			)
		if step.transfer_volume_uL > 200.0:
			result.errors.append(
				f"Transfer volume {step.transfer_volume_uL} uL for {step.target_concentration_uM} uM "
				f"exceeds 200 uL maximum pipette capacity."
			)

	# 2. Plate capacity check
	total_wells = spec.plate_layout.total_wells_used
	max_wells = spec.plate_layout.max_wells
	if total_wells > max_wells:
		result.errors.append(
			f"Total wells used ({total_wells}) exceeds {spec.plate_layout.plate_type} "
			f"plate capacity ({max_wells})."
		)
	elif total_wells > max_wells * 0.9:
		result.warnings.append(
			f"Plate is {total_wells}/{max_wells} wells ({100 * total_wells / max_wells:.0f}%) full. "
			f"Consider using a larger plate format."
		)

	# 3. DMSO concentration check
	for step in spec.dilution_steps:
		if step.dmso_fraction > 0.005:
			result.errors.append(
				f"DMSO fraction {step.dmso_fraction:.4f} ({step.dmso_fraction * 100:.2f}%) "
				f"at {step.target_concentration_uM} uM exceeds 0.5% tolerance."
			)
		elif step.dmso_fraction > 0.003:
			result.warnings.append(
				f"DMSO fraction {step.dmso_fraction:.4f} ({step.dmso_fraction * 100:.2f}%) "
				f"at {step.target_concentration_uM} uM is approaching 0.5% limit."
			)

	# 4. Control presence check
	layout_keys = set(spec.plate_layout.layout.keys())
	has_positive = any("positive" in k for k in layout_keys)
	has_negative = any("negative" in k for k in layout_keys)

	if not has_positive:
		result.errors.append("Missing positive control wells in plate layout.")
	if not has_negative:
		result.errors.append("Missing negative control wells in plate layout.")
	if not any("blank" in k for k in layout_keys):
		result.warnings.append("No blank wells in plate layout. Background subtraction may be unreliable.")

	# 5. Compound solubility check
	solvent = spec.compound.solvent.lower()
	compound_type = spec.compound.name.lower()
	if solvent == "dmso":
		for keyword in INSOLUBLE_IN_DMSO:
			if keyword in compound_type:
				result.warnings.append(
					f"Compound '{spec.compound.name}' may be a {keyword} — "
					f"consider using aqueous solvent (PBS, water) instead of DMSO."
				)

	# 6. Molecular weight sanity check (biologics vs small molecules)
	if spec.compound.molecular_weight > 5000 and solvent == "dmso":
		result.warnings.append(
			f"Compound MW ({spec.compound.molecular_weight:.0f} Da) suggests a biologic. "
			f"DMSO may not be appropriate. Consider PBS or aqueous buffer."
		)

	# 7. Zero-concentration check
	if any(c <= 0 for c in spec.compound.test_concentrations_uM):
		result.errors.append("Test concentrations must all be positive.")

	return result
