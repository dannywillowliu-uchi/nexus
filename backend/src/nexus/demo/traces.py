"""Pre-built event traces for demo replay scenarios."""

from __future__ import annotations

TraceEvent = tuple[dict, float]
Trace = list[TraceEvent]


def _evt(event_type: str, **kwargs) -> dict:
	return {"type": event_type, **kwargs}


def get_demo_trace(demo_id: int) -> Trace:
	traces = {1: _demo_1, 2: _demo_2, 3: _demo_3}
	builder = traces.get(demo_id)
	if builder is None:
		raise ValueError(f"Unknown demo_id: {demo_id}")
	return builder()


def _demo_1() -> Trace:
	"""Fast ADMET case -- riluzole for melanoma."""
	return [
		(_evt(
			"stage_start",
			stage="Literature",
			message="Searching literature for riluzole melanoma interactions",
		), 0.5),
		(_evt(
			"entity_resolved",
			from_entity="riluzole",
			to_entity="Riluzole",
			entity_type="Compound",
		), 0.3),
		(_evt(
			"entity_resolved",
			from_entity="melanoma",
			to_entity="Melanoma",
			entity_type="Disease",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Literature",
			message="Literature search complete",
			papers_found=12,
			triples_extracted=28,
		), 2.0),
		(_evt(
			"triples_merged",
			count=28,
			message="Merged 28 knowledge triples into graph",
		), 0.5),
		(_evt(
			"checkpoint",
			decision="CONTINUE",
			reason="Strong literature signal linking riluzole to melanoma via glutamate pathway",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Graph",
			message="Generating hypotheses from knowledge graph",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Graph",
			message="Hypothesis generation complete",
			hypotheses_generated=5,
		), 2.0),
		(_evt(
			"stage_start",
			stage="Reasoning",
			message="Scoring and ranking hypotheses",
		), 0.3),
		(_evt(
			"hypothesis_scored",
			title="Riluzole modulates glutamate signaling to suppress melanoma cell proliferation via mGluR1",
			score=0.72,
			hypothesis_id="demo-1-hyp-1",
		), 1.0),
		(_evt(
			"hypothesis_scored",
			title="ADMET profile suggests riluzole as viable oral melanoma therapeutic",
			score=0.68,
			hypothesis_id="demo-1-hyp-2",
		), 0.8),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running ADMET and structural validation",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="ADMET validation: favorable oral bioavailability (F=0.78), acceptable toxicity profile, good aqueous solubility (LogS=-2.3)",
		), 3.0),
		(_evt(
			"hypothesis_scored",
			title="Riluzole modulates glutamate signaling to suppress melanoma cell proliferation via mGluR1",
			score=0.81,
			hypothesis_id="demo-1-hyp-1",
		), 0.5),
		(_evt(
			"pipeline_complete",
			message="Pipeline complete",
			hypothesis_id="demo-1-hyp-1",
		), 0.5),
	]


def _demo_2() -> Trace:
	"""Complex multi-tool case -- glioblastoma drug repurposing."""
	return [
		(_evt(
			"stage_start",
			stage="Literature",
			message="Searching literature for glioblastoma repurposing candidates",
		), 0.5),
		(_evt(
			"entity_resolved",
			from_entity="glioblastoma",
			to_entity="Glioblastoma",
			entity_type="Disease",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Literature",
			message="Literature search complete",
			papers_found=34,
			triples_extracted=87,
		), 3.0),
		(_evt(
			"triples_merged",
			count=87,
			message="Merged 87 knowledge triples into graph",
		), 0.5),
		(_evt(
			"checkpoint",
			decision="BRANCH",
			reason="Multiple promising pathways detected - branching into EGFR and VEGF targets",
		), 1.5),
		(_evt(
			"stage_start",
			stage="Graph",
			message="Generating hypotheses from knowledge graph",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Graph",
			message="Hypothesis generation complete",
			hypotheses_generated=8,
		), 3.0),
		(_evt(
			"stage_start",
			stage="Reasoning",
			message="Scoring and ranking hypotheses",
		), 0.3),
		(_evt(
			"hypothesis_scored",
			title="Erlotinib repurposing targets EGFR-amplified glioblastoma via blood-brain barrier penetrant mechanism",
			score=0.65,
			hypothesis_id="demo-2-hyp-1",
		), 1.0),
		(_evt(
			"hypothesis_scored",
			title="Bevacizumab-adjacent VEGF pathway inhibitor shows synergistic effect with temozolomide",
			score=0.61,
			hypothesis_id="demo-2-hyp-2",
		), 0.8),
		(_evt(
			"hypothesis_scored",
			title="Disulfiram-copper complex exploits glioblastoma stem cell vulnerability via ALDH pathway",
			score=0.58,
			hypothesis_id="demo-2-hyp-3",
		), 0.8),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running structural and ADMET validation",
		), 0.3),
		(_evt(
			"progress",
			stage="Validation",
			message="Running AlphaFold structure prediction for EGFR variant III...",
		), 2.0),
		(_evt(
			"progress",
			stage="Validation",
			message="AlphaFold complete: pLDDT=82.3, confident structure",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="Running DiffDock: erlotinib -> EGFRvIII binding...",
		), 3.0),
		(_evt(
			"progress",
			stage="Validation",
			message="DiffDock complete: top pose confidence=0.87, binding energy=-9.2 kcal/mol",
		), 1.0),
		(_evt(
			"progress",
			stage="Validation",
			message="Running ADMET prediction for erlotinib...",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="ADMET complete: BBB penetrant, oral bioavailability 0.72, hepatotoxicity low",
		), 1.0),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="Validation complete",
		), 0.5),
		(_evt(
			"hypothesis_scored",
			title="Erlotinib repurposing targets EGFR-amplified glioblastoma via blood-brain barrier penetrant mechanism",
			score=0.82,
			hypothesis_id="demo-2-hyp-1",
		), 0.5),
		(_evt(
			"stage_start",
			stage="Experiment",
			message="Designing experimental protocol",
		), 0.3),
		(_evt(
			"progress",
			stage="Experiment",
			message="Designing dose-response assay: erlotinib vs U87-MG glioblastoma cells",
		), 1.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Protocol generated: 96-well MTT viability, 8 concentrations (0.1-100 uM)",
		), 1.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Simulator: dose-dependent response detected, IC50=12.3 uM",
		), 2.0),
		(_evt(
			"stage_complete",
			stage="Experiment",
			message="Experiment complete",
		), 0.5),
		(_evt(
			"pipeline_complete",
			message="Pipeline complete",
			hypothesis_id="demo-2-hyp-1",
		), 0.5),
	]


def _demo_3() -> Trace:
	"""Cloud lab failure/retry -- metformin for pancreatic cancer."""
	return [
		(_evt(
			"stage_start",
			stage="Literature",
			message="Searching literature for metformin pancreatic cancer interactions",
		), 0.5),
		(_evt(
			"entity_resolved",
			from_entity="metformin",
			to_entity="Metformin",
			entity_type="Compound",
		), 0.3),
		(_evt(
			"entity_resolved",
			from_entity="pancreatic cancer",
			to_entity="Pancreatic Cancer",
			entity_type="Disease",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Literature",
			message="Literature search complete",
			papers_found=21,
			triples_extracted=45,
		), 2.5),
		(_evt(
			"triples_merged",
			count=45,
			message="Merged 45 knowledge triples into graph",
		), 0.5),
		(_evt(
			"checkpoint",
			decision="CONTINUE",
			reason="Strong signal for metformin-AMPK-pancreatic cancer axis",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Graph",
			message="Generating hypotheses from knowledge graph",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Graph",
			message="Hypothesis generation complete",
			hypotheses_generated=4,
		), 2.0),
		(_evt(
			"stage_start",
			stage="Reasoning",
			message="Scoring and ranking hypotheses",
		), 0.3),
		(_evt(
			"hypothesis_scored",
			title="Metformin activates AMPK pathway to inhibit pancreatic cancer cell growth and sensitize to gemcitabine",
			score=0.71,
			hypothesis_id="demo-3-hyp-1",
		), 1.0),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running structural and ADMET validation",
		), 0.3),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="Validation complete",
		), 2.0),
		(_evt(
			"hypothesis_scored",
			title="Metformin activates AMPK pathway to inhibit pancreatic cancer cell growth and sensitize to gemcitabine",
			score=0.78,
			hypothesis_id="demo-3-hyp-1",
		), 0.5),
		(_evt(
			"stage_start",
			stage="Experiment",
			message="Designing experimental protocol",
		), 0.3),
		(_evt(
			"progress",
			stage="Experiment",
			message="Designing dose-response assay: metformin vs PANC-1 cells",
		), 1.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Protocol generated: 96-well MTT viability assay",
		), 1.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Submitting to Strateos cloud lab...",
		), 1.5),
		(_evt(
			"experiment_error",
			stage="Experiment",
			message="CLOUD LAB ERROR: Reagent concentration out of range. Metformin stock at 500 mM exceeds maximum pipettable concentration (100 mM). Protocol rejected.",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Agent adjusting: recalculating dilution series from 100 mM stock...",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="New protocol: intermediate dilution step added. Stock 500mM -> working stock 50mM -> serial dilution",
		), 1.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Resubmitting corrected protocol to Strateos...",
		), 1.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab accepted protocol. Execution starting...",
		), 1.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Simulator: dose-dependent response detected, IC50=8.7 mM (physiologically relevant)",
		), 2.0),
		(_evt(
			"stage_complete",
			stage="Experiment",
			message="Experiment complete",
		), 0.5),
		(_evt(
			"pipeline_complete",
			message="Pipeline complete",
			hypothesis_id="demo-3-hyp-1",
		), 0.5),
	]
