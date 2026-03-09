"""Generate realistic simulated assay results for demo purposes.

Produces dose-response curves, QC metrics (Z-factor, S/B, CV%), and
analysis summaries based on the hypothesis plausibility score.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from nexus.lab.protocols.spec import ExperimentSpec


@dataclass
class SimulatedResults:
	raw_data: dict[str, list[float]] = field(default_factory=dict)
	qc_metrics: dict = field(default_factory=dict)
	analysis: dict = field(default_factory=dict)
	dose_response: list[dict] = field(default_factory=list)

	def to_dict(self) -> dict:
		return {
			"raw_data": self.raw_data,
			"qc_metrics": self.qc_metrics,
			"analysis": self.analysis,
			"dose_response": self.dose_response,
		}


def _sigmoidal(x: float, ic50: float, hill: float, bottom: float, top: float) -> float:
	"""4-parameter logistic (sigmoidal) dose-response curve."""
	if x <= 0:
		return top
	return bottom + (top - bottom) / (1 + (x / ic50) ** hill)


def generate_simulated_results(
	spec: ExperimentSpec,
	hypothesis_plausibility: float = 0.5,
	seed: int | None = None,
) -> SimulatedResults:
	"""Generate realistic dose-response data based on plausibility score.

	If plausibility > 0.5 ("active"): sigmoidal curve with IC50 in tested range.
	If plausibility <= 0.5 ("inactive"): flat response near negative control.
	"""
	rng = random.Random(seed)
	result = SimulatedResults()
	concentrations = sorted(spec.compound.test_concentrations_uM, reverse=True)
	replicates = spec.plate_layout.replicates

	# Determine if compound is "active"
	is_active = hypothesis_plausibility > 0.5

	# Negative control (full viability) baseline
	neg_ctrl_mean = 1.0
	neg_ctrl_std = 0.05
	neg_ctrl_values = [max(0, rng.gauss(neg_ctrl_mean, neg_ctrl_std)) for _ in range(replicates)]

	# Positive control (dead cells) baseline
	pos_ctrl_mean = 0.1
	pos_ctrl_std = 0.03
	pos_ctrl_values = [max(0, rng.gauss(pos_ctrl_mean, pos_ctrl_std)) for _ in range(replicates)]

	result.raw_data["negative_ctrl"] = [round(v, 4) for v in neg_ctrl_values]
	result.raw_data["positive_ctrl"] = [round(v, 4) for v in pos_ctrl_values]

	if is_active:
		# Active compound: sigmoidal dose-response
		hill = rng.uniform(0.8, 2.0)
		# IC50 somewhere within the tested concentration range
		min_conc = min(concentrations)
		max_conc = max(concentrations)
		ic50 = 10 ** rng.uniform(
			_log10_safe(min_conc * 2),
			_log10_safe(max_conc / 2),
		)
		bottom = rng.uniform(0.05, 0.2)
		top = rng.uniform(0.9, 1.05)
	else:
		# Inactive: flat response
		hill = 1.0
		ic50 = max(concentrations) * 100  # IC50 far above tested range
		bottom = 0.1
		top = 1.0

	dose_response = []
	all_compound_values: list[float] = []

	for conc in concentrations:
		mean_response = _sigmoidal(conc, ic50, hill, bottom, top)
		noise_std = 0.03 * mean_response + 0.01  # Proportional noise: ~4% CV at high signal, ~10% at low
		values = [max(0, rng.gauss(mean_response, noise_std)) for _ in range(replicates)]
		all_compound_values.extend(values)

		label = f"{conc}uM"
		result.raw_data[label] = [round(v, 4) for v in values]

		mean_val = sum(values) / len(values)
		std_val = (sum((v - mean_val) ** 2 for v in values) / max(len(values) - 1, 1)) ** 0.5
		cv = (std_val / mean_val * 100) if mean_val > 0 else 0

		dose_response.append({
			"concentration_uM": conc,
			"mean_response": round(mean_val, 4),
			"std": round(std_val, 4),
			"cv_percent": round(cv, 2),
			"n": replicates,
		})

	result.dose_response = dose_response

	# QC metrics
	mean_neg = sum(neg_ctrl_values) / len(neg_ctrl_values)
	std_neg = (sum((v - mean_neg) ** 2 for v in neg_ctrl_values) / max(len(neg_ctrl_values) - 1, 1)) ** 0.5
	mean_pos = sum(pos_ctrl_values) / len(pos_ctrl_values)
	std_pos = (sum((v - mean_pos) ** 2 for v in pos_ctrl_values) / max(len(pos_ctrl_values) - 1, 1)) ** 0.5

	separation = abs(mean_neg - mean_pos)
	z_factor = 1 - 3 * (std_neg + std_pos) / separation if separation > 0 else -1
	signal_to_background = mean_neg / mean_pos if mean_pos > 0 else 0

	# Max within-concentration CV (not pooled across curve, which inflates CV for active compounds)
	per_conc_cvs = [dr["cv_percent"] for dr in dose_response if dr["cv_percent"] > 0]
	overall_cv = max(per_conc_cvs) if per_conc_cvs else 0

	result.qc_metrics = {
		"z_factor": round(z_factor, 4),
		"signal_to_background": round(signal_to_background, 2),
		"cv_percent": round(overall_cv, 2),
		"negative_ctrl_mean": round(mean_neg, 4),
		"negative_ctrl_std": round(std_neg, 4),
		"positive_ctrl_mean": round(mean_pos, 4),
		"positive_ctrl_std": round(std_pos, 4),
		"pass_z_factor": z_factor >= spec.assay.success_criteria.min_z_factor,
		"pass_s2b": signal_to_background >= spec.assay.success_criteria.min_signal_to_background,
	}

	# Analysis summary
	if is_active:
		result.analysis = {
			"active": True,
			"ic50_uM": round(ic50, 3),
			"hill_coefficient": round(hill, 3),
			"max_inhibition_percent": round((1 - bottom / top) * 100, 1),
			"summary": (
				f"{spec.compound.name} shows dose-dependent activity against {spec.cell_model.name} cells "
				f"with an estimated IC50 of {ic50:.2f} uM (Hill coefficient: {hill:.2f}). "
				f"Maximum inhibition reached {(1 - bottom / top) * 100:.0f}%. "
				f"Assay QC passed with Z-factor {z_factor:.3f}."
			),
		}
	else:
		result.analysis = {
			"active": False,
			"ic50_uM": None,
			"hill_coefficient": None,
			"max_inhibition_percent": round((1 - min(all_compound_values) / max(all_compound_values)) * 100, 1) if all_compound_values else 0,
			"summary": (
				f"{spec.compound.name} shows no significant dose-dependent activity against "
				f"{spec.cell_model.name} cells across the tested concentration range "
				f"({min(concentrations)}-{max(concentrations)} uM). "
				f"Assay QC passed with Z-factor {z_factor:.3f}."
			),
		}

	return result


def _log10_safe(x: float) -> float:
	import math
	return math.log10(max(x, 1e-10))
