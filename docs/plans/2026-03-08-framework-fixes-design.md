# Framework Performance Fixes Design

## Problem

Five issues degrade hypothesis quality and pipeline reliability:

1. **Relationship weight mismatch**: `RELATIONSHIP_WEIGHTS` uses PrimeKG labels but old Hetionet labels (`TREATS_CtD`, `BINDS_CbG`) still exist in graph data and tests, falling back to default 0.5 weight instead of their true values.

2. **Fragile section extraction**: `_extract_sections()` in `reasoning_agent.py` does exact string matching on Claude response headers. Any formatting variation (markdown, numbering) causes structured fields (`connection_explanation`, etc.) to be empty.

3. **Empty validation tool maps**: `comorbidity` and `connection` hypothesis types map to zero Tamarind tools, skipping validation entirely despite having usable gene/protein intermediaries.

4. **Validation scores not feeding back**: Validation results (`confidence_delta`) sit in a list but don't affect `overall_score` or hypothesis ranking. The pipeline validates but doesn't learn from validation.

5. **Silent input resolution failures**: When PDB/SMILES/sequence fetching fails, tools are silently skipped with a generic "missing required inputs" message. No visibility into what failed.

## Fixes

### Fix 1: Relationship Alias Map

Add `RELATIONSHIP_ALIASES` dict mapping old Hetionet labels to PrimeKG labels in `graph/abc.py`. Update `rel_weight()` to check aliases before defaulting.

```python
RELATIONSHIP_ALIASES = {
    "TREATS_CtD": "INDICATION",
    "PALLIATES_CpD": "INDICATION",
    "BINDS_CbG": "TARGET",
    "ASSOCIATES_DaG": "ASSOCIATED_WITH",
    "DOWNREGULATES_CdG": "TARGET",
    "UPREGULATES_CuG": "TARGET",
    "RESEMBLES_DrD": "ASSOCIATED_WITH",
    "INCLUDES_PCiC": "CELLCOMP_PROTEIN",
    "PARTICIPATES_GpPW": "PATHWAY_PROTEIN",
    "PARTICIPATES_GpBP": "BIOPROCESS_PROTEIN",
    "PARTICIPATES_GpMF": "MOLFUNC_PROTEIN",
    "LOCALIZES_DlA": "ANATOMY_PROTEIN_PRESENT",
    "PRESENTS_DpS": "PHENOTYPE_PRESENT",
    "INTERACTS_GiG": "PROTEIN_PROTEIN",
    "COVARIES_GcG": "PROTEIN_PROTEIN",
}
```

Update tests to use PrimeKG labels in fixtures.

### Fix 2: Fuzzy Section Header Matching

Update `_extract_sections()` to normalize lines before matching: strip markdown markers (`#`, `*`), leading numbers/punctuation, and compare case-insensitively.

Update test mock to return a realistic narrative with section headers instead of raw JSON.

### Fix 3: Comorbidity/Connection Tool Maps

Map `comorbidity` to `[esmfold, deepfri, temstapro]` (gene intermediary is always present).

Map `connection` to best-effort based on available inputs: if Drug entity present, include `admet`; if Gene/Protein present, include `esmfold`.

### Fix 4: Post-Validation Re-ranking

After validation gather in orchestrator:
1. Compute `validation_boost` = mean of `confidence_delta` values per hypothesis
2. Store `pre_validation_score = overall_score`
3. Update `overall_score = overall_score * 0.8 + validation_boost * 0.2`
4. Re-sort `scored_hypotheses` by new `overall_score`

### Fix 5: Input Resolution Reporting

`_resolve_inputs()` returns a second value: `dict[str, str]` mapping input names to status (`"fetched"`, `"failed"`, `"not_needed"`).

`run_validation_plan()` includes skipped tools with specific reasons (e.g., "diffdock skipped: PDB fetch failed for BRCA1") in the response list.

## Files Changed

- `backend/src/nexus/graph/abc.py` -- alias map + `rel_weight()` update
- `backend/src/nexus/agents/reasoning_agent.py` -- `_extract_sections()` fuzzy matching
- `backend/src/nexus/tools/tamarind_tools.py` -- comorbidity/connection tool maps
- `backend/src/nexus/tools/validation_planner.py` -- input resolution reporting
- `backend/src/nexus/pipeline/orchestrator.py` -- post-validation re-ranking
- `tests/graph/test_abc.py` -- update fixtures to PrimeKG labels
- `tests/agents/test_reasoning_agent.py` -- update mock to return narrative
- `tests/tools/test_tamarind_tools.py` -- add comorbidity/connection tests
- `tests/tools/test_validation_planner.py` -- add resolution report tests
- `tests/pipeline/test_orchestrator.py` -- add re-ranking test
