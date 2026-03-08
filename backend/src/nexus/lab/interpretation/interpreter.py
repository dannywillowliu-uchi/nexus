"""Claude-powered results interpretation.

Analyzes experimental results and returns a verdict:
validated, inconclusive, or refuted.
"""

from __future__ import annotations

import json

from nexus.config import settings


INTERPRETATION_PROMPT = """You are an expert pharmacologist interpreting assay results.

## Experiment
- Hypothesis: {hypothesis_title}
- Compound: {compound_name} (MW: {molecular_weight} Da)
- Cell model: {cell_model}
- Assay: {assay_name} ({assay_type})
- Concentrations tested: {concentrations} uM

## Results
### Dose-Response Data
{dose_response}

### QC Metrics
- Z-factor: {z_factor}
- Signal-to-background: {s2b}
- CV%: {cv}

### Automated Analysis
{analysis_summary}

## Instructions
Analyze these results and provide:
1. **verdict**: One of "validated", "inconclusive", or "refuted"
2. **confidence**: 0.0 to 1.0
3. **reasoning**: 2-3 sentences explaining the verdict
4. **concerns**: List any methodological concerns
5. **next_steps**: What should be done next

First check QC: Z-factor >= 0.5 and CV < 20% to trust the data.
Then evaluate dose-response: is there a clear sigmoidal curve with IC50 in the pharmacologically relevant range?

Respond in JSON format only."""


async def interpret_results(
	experiment_spec: dict,
	raw_results: dict,
) -> dict:
	"""Interpret experimental results using Claude.

	Returns a dict with verdict, confidence, reasoning, concerns, and next_steps.
	"""
	spec_data = experiment_spec
	results_data = raw_results

	# Build dose-response table
	dose_response_lines = []
	for dr in results_data.get("dose_response", []):
		dose_response_lines.append(
			f"  {dr['concentration_uM']} uM: "
			f"mean={dr['mean_response']:.4f}, "
			f"std={dr['std']:.4f}, "
			f"CV={dr['cv_percent']:.1f}%"
		)
	dose_response_text = "\n".join(dose_response_lines) if dose_response_lines else "No dose-response data available"

	qc = results_data.get("qc_metrics", {})
	analysis = results_data.get("analysis", {})
	compound = spec_data.get("compound", {})
	assay = spec_data.get("assay", {})
	cell_model = spec_data.get("cell_model", {})

	prompt = INTERPRETATION_PROMPT.format(
		hypothesis_title=spec_data.get("hypothesis_title", "Unknown"),
		compound_name=compound.get("name", "Unknown"),
		molecular_weight=compound.get("molecular_weight", 0),
		cell_model=cell_model.get("name", "Unknown"),
		assay_name=assay.get("name", "Unknown"),
		assay_type=assay.get("assay_type", "Unknown"),
		concentrations=", ".join(str(c) for c in compound.get("test_concentrations_uM", [])),
		dose_response=dose_response_text,
		z_factor=qc.get("z_factor", "N/A"),
		s2b=qc.get("signal_to_background", "N/A"),
		cv=qc.get("cv_percent", "N/A"),
		analysis_summary=analysis.get("summary", "No automated analysis available"),
	)

	if not settings.anthropic_api_key:
		return _fallback_interpretation(results_data)

	try:
		import anthropic

		client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
		response = client.messages.create(
			model="claude-sonnet-4-20250514",
			max_tokens=1024,
			messages=[{"role": "user", "content": prompt}],
		)

		text = response.content[0].text.strip()
		# Strip markdown code fences if present
		if text.startswith("```"):
			text = text.split("\n", 1)[1]
			if text.endswith("```"):
				text = text[:-3]
		return json.loads(text)

	except Exception as e:
		result = _fallback_interpretation(results_data)
		result["error"] = str(e)
		return result


def _fallback_interpretation(results_data: dict) -> dict:
	"""Rule-based fallback when Claude is unavailable."""
	qc = results_data.get("qc_metrics", {})
	analysis = results_data.get("analysis", {})

	z_factor = qc.get("z_factor", 0)
	is_active = analysis.get("active", False)
	ic50 = analysis.get("ic50_uM")

	# QC gate
	if z_factor < 0.5:
		return {
			"verdict": "inconclusive",
			"confidence": 0.3,
			"reasoning": f"Assay QC failed (Z-factor {z_factor:.3f} < 0.5). Data quality insufficient for reliable interpretation.",
			"concerns": ["Poor assay quality", "Z-factor below threshold"],
			"next_steps": ["Repeat experiment with optimized assay conditions", "Check cell seeding density and reagent quality"],
		}

	if is_active and ic50 is not None:
		if ic50 < 50:
			return {
				"verdict": "validated",
				"confidence": 0.85,
				"reasoning": f"Compound shows dose-dependent activity with IC50 = {ic50:.2f} uM in pharmacologically relevant range. Assay QC passed.",
				"concerns": [],
				"next_steps": ["Confirm in secondary assay", "Test in additional cell lines", "Evaluate selectivity"],
			}
		else:
			return {
				"verdict": "inconclusive",
				"confidence": 0.5,
				"reasoning": f"Compound shows weak activity (IC50 = {ic50:.2f} uM). May be pharmacologically relevant but requires confirmation.",
				"concerns": ["High IC50 may indicate weak or non-specific effect"],
				"next_steps": ["Test at higher concentrations", "Evaluate in more sensitive assay"],
			}
	else:
		return {
			"verdict": "refuted",
			"confidence": 0.7,
			"reasoning": "No significant dose-dependent activity observed across tested concentration range. Assay QC passed, suggesting genuine inactivity.",
			"concerns": [],
			"next_steps": ["Consider alternative mechanisms", "Test related analogs", "Pivot to different compound"],
		}
