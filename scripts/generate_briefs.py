"""
Generate researcher-style reasoning briefs for all benchmark cases.
Tests that Nexus explains hypotheses like a scientist, not a database.
Run: PYTHONPATH=backend/src uv run python scripts/generate_briefs.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()

BENCHMARK_CASES = [
    {
        "drug": "Riluzole",
        "disease": "melanoma",
        "intermediary": "GRM1",
        "drug_gene_rel": "Riluzole inhibits glutamate release, functionally antagonizing GRM1 signaling (LITERATURE_ASSOCIATION, confidence: 0.92)",
        "gene_disease_rel": "GRM1 ectopically expressed in >60% of melanomas but not normal melanocytes (LITERATURE_ASSOCIATION, confidence: 0.95)",
        "path_count": 1,
        "novel_edges": "Both edges are literature-derived — neither exists in PrimeKG's curated database",
        "benchmark_rank": 1,
    },
    {
        "drug": "Thalidomide",
        "disease": "multiple myeloma",
        "intermediary": "TNF, CRBN, IL6, VEGFA",
        "drug_gene_rel": "Thalidomide binds CRBN (TARGET), downregulates TNF/IL6/VEGFA (LITERATURE_ASSOCIATION, confidence: 0.90-0.95)",
        "gene_disease_rel": "TNF/IL6 drive myeloma cell survival in bone marrow microenvironment (LITERATURE_ASSOCIATION, confidence: 0.94-0.95)",
        "path_count": 4,
        "novel_edges": "TNF->myeloma, IL6->myeloma, VEGFA->myeloma are literature-derived. CRBN->myeloma existed in PrimeKG.",
        "benchmark_rank": 1,
    },
    {
        "drug": "Sildenafil",
        "disease": "pulmonary arterial hypertension",
        "intermediary": "PDE5A",
        "drug_gene_rel": "Sildenafil inhibits PDE5A (TARGET, curated in PrimeKG)",
        "gene_disease_rel": "PDE5A abundantly expressed in pulmonary vasculature, degrades cGMP needed for vasodilation (LITERATURE_ASSOCIATION, confidence: 0.95)",
        "path_count": 1,
        "novel_edges": "PDE5A->PAH is literature-derived",
        "benchmark_rank": 1,
    },
    {
        "drug": "Auranofin",
        "disease": "ovarian cancer",
        "intermediary": "PRDX5, TXNRD1",
        "drug_gene_rel": "Auranofin targets PRDX5 (TARGET in PrimeKG), inhibits thioredoxin reductase TXNRD1",
        "gene_disease_rel": "PRDX5/TXNRD1 associated with ovarian cancer — redox defense system overexpressed in cisplatin-resistant tumors",
        "path_count": 2,
        "novel_edges": "Drug->gene edges curated in PrimeKG",
        "benchmark_rank": 1,
    },
    {
        "drug": "Metformin",
        "disease": "colorectal cancer",
        "intermediary": "ETFDH, SLC22A1, PRKAB1",
        "drug_gene_rel": "Metformin targets ETFDH and SLC22A1 (TARGET), activates AMPK (PRKAB1 subunit)",
        "gene_disease_rel": "Multiple metabolic and signaling genes associated with colorectal cancer",
        "path_count": 3,
        "novel_edges": "Curated PrimeKG edges",
        "benchmark_rank": 3,
    },
    {
        "drug": "Niclosamide",
        "disease": "colorectal cancer",
        "intermediary": "CYP2C9, CTNNB1, GSK3B",
        "drug_gene_rel": "Niclosamide metabolized by CYP2C9 (ENZYME), inhibits Wnt/beta-catenin signaling",
        "gene_disease_rel": "Wnt pathway aberrantly activated in >90% of colorectal cancers via APC mutations",
        "path_count": 2,
        "novel_edges": "Wnt mechanism is literature-derived",
        "benchmark_rank": 8,
    },
    {
        "drug": "Aspirin",
        "disease": "colorectal cancer",
        "intermediary": "PTGS1 (COX-1)",
        "drug_gene_rel": "Aspirin inhibits PTGS1/COX-1 (TARGET) and PTGS2/COX-2",
        "gene_disease_rel": "COX enzymes produce prostaglandins that promote colorectal tumor growth",
        "path_count": 1,
        "novel_edges": "Curated PrimeKG edges",
        "benchmark_rank": 19,
    },
    {
        "drug": "Imatinib",
        "disease": "gastrointestinal stromal tumor",
        "intermediary": "KIT",
        "drug_gene_rel": "Imatinib inhibits KIT tyrosine kinase (TARGET)",
        "gene_disease_rel": "KIT activating mutations drive >85% of GISTs",
        "path_count": 1,
        "novel_edges": "Curated PrimeKG edges",
        "benchmark_rank": 47,
    },
    {
        "drug": "Valproic Acid",
        "disease": "glioblastoma",
        "intermediary": "HDAC2",
        "drug_gene_rel": "Valproic acid inhibits histone deacetylases including HDAC2",
        "gene_disease_rel": "HDAC overexpression drives glioblastoma proliferation and resistance (LITERATURE_ASSOCIATION, confidence: 0.88)",
        "path_count": 1,
        "novel_edges": "HDAC2->glioblastoma is literature-derived",
        "benchmark_rank": 1,
    },
    {
        "drug": "Propranolol",
        "disease": "hemangioma",
        "intermediary": "ADRB1, ADRB2",
        "drug_gene_rel": "Propranolol blocks beta-adrenergic receptors ADRB1/ADRB2 (TARGET)",
        "gene_disease_rel": "Beta-adrenergic signaling promotes hemangioma growth and VEGF production (LITERATURE_ASSOCIATION, confidence: 0.88-0.93)",
        "path_count": 2,
        "novel_edges": "ADRB1/ADRB2->hemangioma are literature-derived",
        "benchmark_rank": 1,
    },
]

RESEARCHER_PROMPT = """You are a senior translational researcher reviewing a computationally-generated drug repurposing hypothesis. Think out loud as a researcher would — don't just report scores, reason through the biology.

HYPOTHESIS:
{drug} may have therapeutic activity against {disease} via {intermediary}.

EVIDENCE:
- Drug->Gene link: {drug_gene_rel}
- Gene->Disease link: {gene_disease_rel}
- Path redundancy: {path_count} independent intermediaries
- Novel edges: {novel_edges}
- Benchmark rank: {benchmark_rank} (out of all diseases tested)

Structure your analysis EXACTLY in these 5 sections:

1. BIOLOGICAL PLAUSIBILITY
Think through the mechanism step by step. What does the intermediary gene actually do in the cell? What happens when the drug affects it? Why would that matter for this disease? Be specific about the molecular cascade — name the signaling steps, the downstream effectors, what goes wrong in the disease. Don't say "it's involved in the pathway" — explain the causal chain.

2. STRENGTH OF EVIDENCE
What's the strongest piece of evidence? What's the weakest? If the drug-gene link is from metabolic enzymes (CYP450s), say that's weaker than a direct pharmacological target. If the connection is from epidemiological observation, note confounders. Be honest about what's proven vs speculated.

3. HOW TO TEST THIS — FIRST EXPERIMENT
Describe exactly what a researcher would do first:
- Name specific cell lines (e.g., C8161 for GRM1+ melanoma, not just "cancer cell lines")
- Name the specific assay (MTS viability, Western blot for specific phospho-proteins, reporter assay, ELISA)
- Give exact drug concentrations based on known pharmacology (what are typical plasma concentrations? what range for in vitro?)
- Name positive controls (a known drug that hits this target) and negative controls (cell line without the target)
- State what readout means success vs failure
- Estimate time and approximate cost
- If relevant, describe the second experiment that would follow if the first succeeds

4. WHY THIS MIGHT FAIL — TOP 3 RISKS
For each risk:
- State the specific concern (bioavailability, selectivity, resistance, wrong patient population, concentration issues)
- Explain what would need to be true for the hypothesis to succeed despite this risk
- If there's a way to mitigate (combination therapy, patient selection, prodrug), mention it

5. CLINICAL SIGNIFICANCE
If this IS real: How many patients have this disease annually? What are current treatment options? What are their limitations? What specific gap would this drug fill? Is there a patient subpopulation that would benefit most (e.g., treatment-resistant, specific mutation status, specific stage)?

Write as a scientist talking to another scientist. Use specific gene names, drug concentrations, cell line names, assay types. No vague statements. Every claim should be concrete and testable."""


def generate_brief(case: dict) -> str:
    prompt = RESEARCHER_PROMPT.format(**case)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def main():
    all_briefs = []

    for i, case in enumerate(BENCHMARK_CASES):
        print(f"\n{'='*70}")
        print(f"CASE {i+1}/10: {case['drug']} -> {case['intermediary']} -> {case['disease']}")
        print(f"Benchmark rank: {case['benchmark_rank']}")
        print(f"{'='*70}\n")

        brief = generate_brief(case)
        print(brief)

        all_briefs.append({
            "case": f"{case['drug']} -> {case['disease']}",
            "intermediary": case["intermediary"],
            "rank": case["benchmark_rank"],
            "brief": brief,
        })

    # Save all briefs
    with open("benchmark_briefs.json", "w") as f:
        json.dump(all_briefs, f, indent=2)

    print(f"\n{'='*70}")
    print(f"All 10 briefs generated and saved to benchmark_briefs.json")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
