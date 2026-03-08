# Graph Reasoning Upgrade Design

**Goal:** Fix benchmark issues with graph traversal quality and unlock richer hypothesis discovery by loading full PrimeKG edges, supporting flexible intermediary types, and improving entity resolution.

**Architecture:** Tiered async fan-out for intermediary queries, bounded multi-entity exploration via asyncio, and Tamarind tool unification.

**Tech Stack:** Neo4j Aura (upgraded), asyncio, PrimeKG 3.37M edges, Tamarind Bio API

---

## Section 1: Full PrimeKG Edge Loading

Remove the 395K edge cap from `load_primekg.py`. Load all 3.37M edges in 4 tiers:

| Tier | Edge Types | ~Count |
|------|-----------|--------|
| 1 | indication, contraindication, off-label, drug_protein | ~120K |
| 2 | disease_protein | ~30K |
| 3 | protein_protein, bioprocess_protein, pathway_protein | ~1.3M |
| 4 | molfunc_protein, cellcomp_protein, anatomy_protein, phenotype, drug_drug, exposure, disease_disease | ~2.5M |

CLI: `python scripts/load_primekg.py --tier 4` (default), `--no-clear` to append, `--data-path` for custom CSV location.

**Status:** Script updated. Tiers 1-2 loaded (148K edges). Awaiting Neo4j Aura upgrade for full load.

## Section 2: Tiered Async Fan-Out for Intermediary Queries

Replace the single Gene-hardcoded Cypher query with async fan-out across intermediary types:

```
Tier 1 (always run):  Gene
Tier 2 (if < min_results): Pathway, BiologicalProcess
Tier 3 (if < min_results): Anatomy, Phenotype, MolecularFunction, CellularComponent
```

Within each tier, queries run concurrently via `asyncio.gather()` with 10s per-query timeout. Results merge into unified ranked list. `min_results` defaults to 10; if tier 1 returns enough, skip lower tiers.

`INTERMEDIARY_MULTIPLIERS` already handles type-based scoring (Gene=1.5x, Anatomy=1.3x, etc.).

## Section 3: Bounded Multi-Entity Exploration

When checkpoint agent returns BRANCH with candidate entities, run up to 3 concurrent pipeline branches:

- Max 3 concurrent branches (semaphore enforced)
- 30s timeout per branch
- Branches run graph search + scoring only (skip literature/reasoning for speed)
- Results merge into main scored_hypotheses and get re-ranked

Lightweight asyncio, not swarm-level. Swarm patterns reserved for future deep exploration mode.

## Section 4: Benchmark Issue Fixes

### Issue 1: Regex over-matching
After `resolve_entity()` returns canonical name, ABC query uses exact match (`WHERE a.name = $source_name`) instead of regex. `fuzzy: bool = False` parameter added for backward compatibility.

### Issue 2: Disease name specificity
Added `resolve_entity_multi()` returning multiple candidates ordered by specificity. Orchestrator emits all candidates in events so users see alternatives.

### Issue 3: Missing INDICATION edges
Fixed by loading full PrimeKG edges (more Gene intermediary paths become available).

### Issue 4: ENZYME vs TARGET intermediaries
Added `preferred_ab_rels` parameter to `find_abc_hypotheses()`. `find_drug_repurposing_candidates()` defaults to `["TARGET", "INDICATION", "ASSOCIATED_WITH", "DISEASE_PROTEIN"]` to prioritize pharmacological targets over metabolic enzymes.

## Section 5: Tamarind Tool Improvements

1. Unify `molecular_dock.py` to use `TamarindClient` (keep PDB/SDF fetching, use client.upload_file/submit_job)
2. Add `list_job_types()` to `TamarindClient` for dynamic tool discovery
3. No new individual tool wrappers for MVP. `TamarindClient.run_job()` accepts any job type.

Existing tools (dock, structure prediction, property prediction, batch screen, multi-engine dock) cover the core validation loop.

## Future Refinements (not implemented now)

- **Evidence scoring:** Uncap 5-triple limit, add recency weighting
- **Edge provenance:** Track source paper, confidence, timestamp per edge
- **Multi-entity swarm:** Full pipeline runs per entity using autonomous-dev swarm
- **Temporal graph analysis:** Weight edges by publication recency
