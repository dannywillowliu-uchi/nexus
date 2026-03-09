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


# --- Shared hypothesis detail data (for /hypothesis/:id page) ---

_DEMO_1_HYP_1 = {
	"title": "Riluzole modulates glutamate signaling to suppress melanoma cell proliferation via mGluR1",
	"hypothesis_id": "demo-1-hyp-1",
	"disease_area": "Melanoma",
	"hypothesis_type": "Drug Repurposing",
	"a_term": "Riluzole",
	"a_type": "Drug",
	"b_term": "GRM1 (mGluR1)",
	"b_type": "Gene",
	"c_term": "Melanoma",
	"c_type": "Disease",
	"description": "Riluzole, an FDA-approved ALS drug and glutamate release inhibitor, suppresses melanoma proliferation by antagonizing metabotropic glutamate receptor 1 (mGluR1), which is aberrantly expressed in melanoma cells. This A-B-C path (Drug->Gene->Disease) represents a strong repurposing candidate with existing clinical trial support.",
	"confidence_scores": {
		"graph": 0.85,
		"literature": 0.82,
		"plausibility": 0.78,
		"novelty": 0.71,
	},
	"research_brief": "Riluzole is an FDA-approved glutamate release inhibitor used in ALS. Multiple studies show mGluR1 is aberrantly expressed in ~60% of melanoma cell lines and patient tumors. Riluzole inhibits glutamate signaling through mGluR1, reducing MAPK/ERK pathway activation critical for melanoma cell survival. Phase 0 and Phase II clinical trials (NCT00866840) have demonstrated riluzole reduces metabolic activity in melanoma tumors as measured by FDG-PET. The drug shows favorable ADMET properties for oral administration with established safety profile from ALS use.",
	"evidence_chain": [
		{
			"title": "Namkoong et al. (2007) - Metabotropic glutamate receptor 1 and glutamate signaling in human melanoma",
			"snippet": "mGluR1 is ectopically expressed in human melanoma and promotes cell proliferation through the MAPK pathway. Riluzole treatment reduced melanoma cell growth in vitro and in xenograft models.",
			"confidence": 0.91,
		},
		{
			"title": "Yip et al. (2009) - Phase 0 clinical trial of riluzole in melanoma patients",
			"snippet": "Riluzole suppressed MAPK signaling in melanoma tumors and decreased FDG-PET metabolic activity, supporting glutamate pathway as therapeutic target.",
			"confidence": 0.88,
		},
		{
			"title": "PrimeKG Graph Evidence - Drug-Gene-Disease path",
			"snippet": "3-hop path: Riluzole -[TARGET]-> GRM1 -[ASSOCIATED_WITH]-> Melanoma. Path count: 7, weighted score: 3.85.",
			"confidence": 0.85,
		},
	],
	"experiment_status": "completed",
}

_DEMO_1_HYP_2 = {
	"title": "ADMET profile suggests riluzole as viable oral melanoma therapeutic",
	"hypothesis_id": "demo-1-hyp-2",
	"disease_area": "Melanoma",
	"hypothesis_type": "ADMET Validation",
	"a_term": "Riluzole",
	"a_type": "Drug",
	"b_term": "CYP1A2",
	"b_type": "Gene",
	"c_term": "Melanoma",
	"c_type": "Disease",
	"confidence_scores": {
		"graph": 0.72,
		"literature": 0.75,
		"plausibility": 0.70,
		"novelty": 0.55,
	},
}

_DEMO_2_HYP_1 = {
	"title": "Erlotinib repurposing targets EGFR-amplified glioblastoma via blood-brain barrier penetrant mechanism",
	"hypothesis_id": "demo-2-hyp-1",
	"disease_area": "Glioblastoma",
	"hypothesis_type": "Drug Repurposing",
	"a_term": "Erlotinib",
	"a_type": "Drug",
	"b_term": "EGFR",
	"b_type": "Gene",
	"c_term": "Glioblastoma",
	"c_type": "Disease",
	"description": "Erlotinib targets EGFR, which is amplified in ~50% of glioblastoma cases. Unlike many kinase inhibitors, erlotinib demonstrates partial BBB penetration, making it a candidate for CNS tumors. DiffDock binding simulation confirms strong binding to EGFRvIII mutant with -9.2 kcal/mol energy.",
	"confidence_scores": {
		"graph": 0.88,
		"literature": 0.79,
		"plausibility": 0.82,
		"novelty": 0.62,
	},
	"research_brief": "EGFR amplification occurs in approximately 50% of glioblastoma cases, with EGFRvIII being the most common variant. Erlotinib, an FDA-approved EGFR inhibitor for NSCLC, has partial blood-brain barrier penetrance (CSF:plasma ratio ~5-10%). AlphaFold structure prediction of EGFRvIII yielded confident structure (pLDDT=82.3). DiffDock molecular docking predicted strong binding of erlotinib to EGFRvIII active site (confidence=0.87, binding energy=-9.2 kcal/mol). ADMET profiling confirms BBB penetration and acceptable oral bioavailability (F=0.72).",
	"evidence_chain": [
		{
			"title": "Raizer et al. (2010) - Phase II trial of erlotinib in recurrent glioblastoma",
			"snippet": "Erlotinib demonstrated modest single-agent activity in recurrent GBM. Patients with EGFR amplification showed improved PFS compared to wild-type.",
			"confidence": 0.82,
		},
		{
			"title": "Tamarind Bio - AlphaFold Structure Prediction",
			"snippet": "EGFRvIII variant structure predicted with pLDDT=82.3. Active site geometry compatible with erlotinib binding.",
			"confidence": 0.87,
		},
		{
			"title": "Tamarind Bio - DiffDock Molecular Docking",
			"snippet": "Erlotinib -> EGFRvIII: top pose confidence=0.87, binding energy=-9.2 kcal/mol. Hydrogen bonds to M793, T854.",
			"confidence": 0.87,
		},
	],
	"experiment_status": "completed",
}

_DEMO_3_HYP_1 = {
	"title": "Metformin activates AMPK pathway to inhibit pancreatic cancer cell growth and sensitize to gemcitabine",
	"hypothesis_id": "demo-3-hyp-1",
	"disease_area": "Pancreatic Cancer",
	"hypothesis_type": "Drug Repurposing",
	"a_term": "Metformin",
	"a_type": "Drug",
	"b_term": "PRKAA1 (AMPK)",
	"b_type": "Gene",
	"c_term": "Pancreatic Cancer",
	"c_type": "Disease",
	"description": "Metformin activates AMPK, which inhibits mTOR signaling critical for pancreatic cancer cell growth. Epidemiological studies show reduced pancreatic cancer incidence in diabetic patients taking metformin. Cloud lab experiment demonstrated dose-dependent growth inhibition (IC50=8.7 mM).",
	"confidence_scores": {
		"graph": 0.80,
		"literature": 0.85,
		"plausibility": 0.76,
		"novelty": 0.58,
	},
	"research_brief": "Metformin activates AMP-activated protein kinase (AMPK), which inhibits mTOR signaling and reduces pancreatic cancer cell proliferation. Large-scale epidemiological studies (Li et al., 2009; Sadeghi et al., 2012) show 62% reduced risk of pancreatic cancer in diabetic patients on metformin. The AMPK-mTOR axis is a validated therapeutic target in pancreatic cancer. Cloud lab validation via Strateos confirmed dose-dependent growth inhibition of PANC-1 cells with IC50=8.7 mM, which is within physiologically achievable plasma concentrations.",
	"evidence_chain": [
		{
			"title": "Li et al. (2009) - Metformin and pancreatic cancer risk in diabetic patients",
			"snippet": "Metformin use was associated with 62% reduced risk of pancreatic cancer (OR=0.38, 95% CI 0.22-0.69) in a case-control study of 973 patients.",
			"confidence": 0.90,
		},
		{
			"title": "Kisfalvi et al. (2009) - Metformin disrupts crosstalk between insulin/IGF-1 and GPCR signaling",
			"snippet": "Metformin inhibited pancreatic cancer cell growth via AMPK activation and mTOR inhibition, with synergistic effects when combined with gemcitabine.",
			"confidence": 0.85,
		},
		{
			"title": "Strateos Cloud Lab - Dose-Response Assay",
			"snippet": "96-well MTT viability assay: metformin vs PANC-1 cells. Dose-dependent response detected, IC50=8.7 mM (physiologically relevant at therapeutic doses).",
			"confidence": 0.78,
		},
	],
	"experiment_status": "completed",
}


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
			entity_type="Drug",
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
			score=0.72,
			**_DEMO_1_HYP_1,
		), 1.0),
		(_evt(
			"hypothesis_scored",
			score=0.68,
			**_DEMO_1_HYP_2,
		), 0.8),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running ADMET and structural validation via Tamarind Bio",
		), 0.3),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Running ADMET property prediction for riluzole...",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Complete: oral bioavailability F=0.78, LogS=-2.3, hERG safe, Ames negative",
		), 1.5),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="ADMET validation complete: favorable oral bioavailability (F=0.78), acceptable toxicity profile, good aqueous solubility (LogS=-2.3)",
		), 1.0),
		(_evt(
			"hypothesis_scored",
			score=0.81,
			**_DEMO_1_HYP_1,
		), 0.5),
		# --- Experiment stage (~30s cloud lab) ---
		(_evt(
			"stage_start",
			stage="Experiment",
			message="Designing experimental protocol for riluzole melanoma validation",
		), 0.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Designing dose-response assay: riluzole vs A375 melanoma cells",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Protocol generated: 96-well MTT viability, 8 concentrations (0.1-50 uM), 48h incubation",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Submitting to Strateos cloud lab...",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab accepted protocol. Queuing execution...",
		), 4.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: dispensing riluzole stock solution into 96-well plate...",
		), 5.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: serial dilution complete, incubating at 37C...",
		), 6.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: reading plate absorbance (MTT assay)...",
		), 5.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Simulator: dose-dependent response detected, IC50=4.2 uM (consistent with literature)",
		), 3.0),
		(_evt(
			"stage_complete",
			stage="Experiment",
			message="Experiment complete: IC50=4.2 uM confirmed riluzole anti-melanoma activity",
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
			score=0.65,
			**_DEMO_2_HYP_1,
		), 1.0),
		(_evt(
			"hypothesis_scored",
			title="Bevacizumab-adjacent VEGF pathway inhibitor shows synergistic effect with temozolomide",
			score=0.61,
			hypothesis_id="demo-2-hyp-2",
			disease_area="Glioblastoma",
			a_term="Bevacizumab", a_type="Drug",
			b_term="VEGFA", b_type="Gene",
			c_term="Glioblastoma", c_type="Disease",
			confidence_scores={"graph": 0.75, "literature": 0.70, "plausibility": 0.68, "novelty": 0.45},
		), 0.8),
		(_evt(
			"hypothesis_scored",
			title="Disulfiram-copper complex exploits glioblastoma stem cell vulnerability via ALDH pathway",
			score=0.58,
			hypothesis_id="demo-2-hyp-3",
			disease_area="Glioblastoma",
			a_term="Disulfiram", a_type="Drug",
			b_term="ALDH1A1", b_type="Gene",
			c_term="Glioblastoma", c_type="Disease",
			confidence_scores={"graph": 0.65, "literature": 0.62, "plausibility": 0.72, "novelty": 0.68},
		), 0.8),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running structural and ADMET validation via Tamarind Bio",
		), 0.3),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind AlphaFold] Running structure prediction for EGFR variant III...",
		), 2.0),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind AlphaFold] Complete: pLDDT=82.3, confident structure obtained",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind DiffDock] Running molecular docking: erlotinib -> EGFRvIII binding site...",
		), 3.0),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind DiffDock] Complete: top pose confidence=0.87, binding energy=-9.2 kcal/mol",
		), 1.0),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Running ADMET prediction for erlotinib...",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Complete: BBB penetrant, oral bioavailability 0.72, hepatotoxicity low",
		), 1.0),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="Validation complete: 3 Tamarind tools executed (AlphaFold, DiffDock, ADMET)",
		), 0.5),
		(_evt(
			"hypothesis_scored",
			score=0.82,
			**_DEMO_2_HYP_1,
		), 0.5),
		(_evt(
			"stage_start",
			stage="Experiment",
			message="Designing experimental protocol",
		), 0.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Designing dose-response assay: erlotinib vs U87-MG glioblastoma cells",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Protocol generated: 96-well MTT viability, 8 concentrations (0.1-100 uM)",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Submitting to Strateos cloud lab...",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab accepted protocol. Queuing execution...",
		), 4.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: dispensing erlotinib stock into 96-well plate...",
		), 5.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: serial dilution complete, incubating at 37C with U87-MG cells...",
		), 6.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: reading plate absorbance (MTT assay)...",
		), 5.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Simulator: dose-dependent response detected, IC50=12.3 uM",
		), 3.0),
		(_evt(
			"stage_complete",
			stage="Experiment",
			message="Experiment complete: IC50=12.3 uM confirms erlotinib anti-glioblastoma activity",
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
			entity_type="Drug",
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
			score=0.71,
			**_DEMO_3_HYP_1,
		), 1.0),
		(_evt(
			"stage_complete",
			stage="Reasoning",
			message="Reasoning complete",
		), 1.0),
		(_evt(
			"stage_start",
			stage="Validation",
			message="Running ADMET validation via Tamarind Bio",
		), 0.3),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Running ADMET prediction for metformin...",
		), 1.5),
		(_evt(
			"progress",
			stage="Validation",
			message="[Tamarind ADMET] Complete: oral bioavailability 0.95, renal clearance primary, hepatotoxicity minimal",
		), 1.0),
		(_evt(
			"stage_complete",
			stage="Validation",
			message="Validation complete",
		), 0.5),
		(_evt(
			"hypothesis_scored",
			score=0.78,
			**_DEMO_3_HYP_1,
		), 0.5),
		(_evt(
			"stage_start",
			stage="Experiment",
			message="Designing experimental protocol for cloud lab validation",
		), 0.5),
		(_evt(
			"progress",
			stage="Experiment",
			message="Designing dose-response assay: metformin vs PANC-1 cells",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Protocol generated: 96-well MTT viability assay, 8 concentrations",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Submitting to Strateos cloud lab...",
		), 3.0),
		(_evt(
			"experiment_error",
			stage="Experiment",
			message="CLOUD LAB ERROR: Reagent concentration out of range. Metformin stock at 500 mM exceeds maximum pipettable concentration (100 mM). Protocol rejected by Strateos.",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Agent adjusting: recalculating dilution series from 100 mM stock...",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="New protocol: intermediate dilution step added. Stock 500mM -> working stock 50mM -> serial dilution",
		), 2.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Resubmitting corrected protocol to Strateos...",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab accepted protocol. Queuing execution...",
		), 3.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: dispensing metformin working stock into 96-well plate...",
		), 4.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: serial dilution complete, incubating at 37C with PANC-1 cells...",
		), 5.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Cloud lab: reading plate absorbance (MTT assay)...",
		), 4.0),
		(_evt(
			"progress",
			stage="Experiment",
			message="Simulator: dose-dependent response detected, IC50=8.7 mM (physiologically relevant)",
		), 3.0),
		(_evt(
			"stage_complete",
			stage="Experiment",
			message="Experiment complete: cloud lab error recovered, IC50=8.7 mM confirmed",
		), 0.5),
		(_evt(
			"pipeline_complete",
			message="Pipeline complete",
			hypothesis_id="demo-3-hyp-1",
		), 0.5),
	]
