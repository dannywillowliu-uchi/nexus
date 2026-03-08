# PrimeKG Knowledge Graph — Nexus Data Reference

**Last updated:** 2026-03-08
**Source:** Harvard Zitnik Lab — Precision Medicine Knowledge Graph (PrimeKG)
**Publication:** Chandak et al., "Building a knowledge graph to enable precision medicine," Scientific Data, 2023
**GitHub:** https://github.com/mims-harvard/PrimeKG
**Data download:** https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/IXA7BM

---

## Overview

Nexus uses PrimeKG as its foundational knowledge graph. PrimeKG integrates 20 high-quality biomedical resources including DrugBank, DisGeNET, Reactome, SIDER, Gene Ontology, Human Phenotype Ontology, MONDO, UBERON, and others.

**Full dataset:** 129,375 nodes, 4,050,249 edges, 10 node types, 30 relationship types
**What we loaded:** All 129,375 nodes + ~395,000 priority edges (Neo4j Aura free tier cap)

We chose PrimeKG over Hetionet (47K nodes, 2.25M edges, last updated 2017) because:
- Nearly 2x edges with better disease coverage
- Updated through 2023 (including Dec 2023 OMIM update)
- Includes indication, contraindication, and off-label use edges (critical for drug repurposing)
- Includes Phenotype nodes that Hetionet lacks
- Multimodal: includes text descriptions for drugs and diseases
- Active maintenance from Harvard research group

---

## Node Types (all loaded)

| Label in Neo4j | PrimeKG type | Count (approx) | Description |
|---|---|---|---|
| `Gene` | gene/protein | ~27,000 | Proteins and genes from UniProt/NCBI |
| `Drug` | drug | ~8,000 | Approved and experimental drugs from DrugBank |
| `Disease` | disease | ~17,000 | Diseases from MONDO ontology |
| `BiologicalProcess` | biological_process | ~28,000 | GO biological processes |
| `MolecularFunction` | molecular_function | ~11,000 | GO molecular functions |
| `CellularComponent` | cellular_component | ~4,000 | GO cellular components |
| `Pathway` | pathway | ~2,500 | Reactome pathways |
| `Anatomy` | anatomy | ~14,000 | Anatomical structures from UBERON |
| `Phenotype` | phenotype | ~15,000 | Phenotypes from HPO |
| `Exposure` | exposure | ~800 | Environmental exposures from CTD |

### Node Properties
Every node has:
- `primekg_index` (int) — unique PrimeKG identifier, used for MERGE operations
- `name` (string) — human-readable name (e.g., "Riluzole", "melanoma", "GRM1")
- `node_id` (string) — source database ID (e.g., DrugBank ID, MONDO ID, UniProt ID)
- `source` (string) — originating database
- `node_type` (string) — original PrimeKG type string

### Node Name Conventions
- **Drugs:** Standard DrugBank names, title case (e.g., "Riluzole", "Thalidomide", "Metformin")
- **Diseases:** MONDO ontology names, lowercase (e.g., "melanoma", "multiple myeloma")
- **Genes/Proteins:** HGNC symbols or UniProt names (e.g., "GRM1", "TNF", "PDE5A")
- **ALWAYS search case-insensitive** when looking up entities: `WHERE n.name =~ '(?i).*riluzole.*'`

---

## Edge Types — What Was Loaded

We loaded edges in priority order to maximize drug repurposing ABC traversal value within the 400K edge cap.

### Priority 1 — Drug-Disease and Drug-Gene edges (LOADED)

| Relationship type in Neo4j | PrimeKG display_relation | Connects | Count | Why it matters |
|---|---|---|---|---|
| `INDICATION` | indication | Drug → Disease | 18,776 | Ground truth — "drug treats disease." We remove these for benchmarking. |
| `CONTRAINDICATION` | contraindication | Drug → Disease | 61,350 | Drug should NOT be used for this disease. Useful negative signal. |
| `OFF_LABEL_USE` | off-label use | Drug → Disease | 5,136 | Drug used for disease without official approval. Gold for repurposing. |
| `TARGET` | target | Drug → Gene | 32,760 | Primary pharmacological targets. Core of ABC traversal. |
| `CARRIER` | carrier | Drug → Gene | 1,728 | Proteins that carry the drug. |
| `ENZYME` | enzyme | Drug → Gene | 10,634 | Enzymes that metabolize the drug. |
| `TRANSPORTER` | transporter | Drug → Gene | 6,184 | Proteins that transport the drug. |

### Priority 2 — Disease-Gene edges (LOADED)

| Relationship type in Neo4j | PrimeKG display_relation | Connects | Count | Why it matters |
|---|---|---|---|---|
| `ASSOCIATED_WITH` | associated with / disease_protein | Disease → Gene | 167,482 | **THE OTHER HALF OF ABC.** Without this, Drug→Gene→Disease paths don't exist. |

### Priority 3 — Phenotype edges (PARTIALLY LOADED)

| Relationship type in Neo4j | PrimeKG display_relation | Connects | Count | Why it matters |
|---|---|---|---|---|
| `PHENOTYPE_PROTEIN` | phenotype_protein | Phenotype → Gene | 6,660 | Enables Drug→Phenotype→Disease paths |
| `PHENOTYPE_PRESENT` | disease_phenotype_positive | Disease → Phenotype | 90,950 | Phenotype-based disease similarity (partially loaded — hit 395K cap) |

### NOT LOADED (excluded deliberately)

| Relationship type | PrimeKG display_relation | Approx count | Why excluded |
|---|---|---|---|
| `PPI` | ppi | ~500K+ | Protein-protein interactions. Would consume entire edge budget. Traps ABC traversal in gene-gene network. Published research (DREAMwalk, Nature Communications 2023) confirms PPI dominates random walks and hurts drug repurposing performance. |
| `PATHWAY` | pathway | variable | Low priority for drug repurposing per our pivot rules. Gene intermediaries outperform Pathway intermediaries. |
| Various GO edges | biological_process, molecular_function, cellular_component associations | ~1M+ | Too broad, not domain-specific. BMC Bioinformatics 2022 showed these node types are "uniformly reduced" after domain-specific filtering. |
| `DRUG_DRUG` | synergistic interaction | ~2.7M | Drug-drug synergy. Not relevant for ABC traversal. |
| `EXPRESSION_PRESENT` | expression present | ~3M | Gene→Anatomy expression. Too many edges for the budget. |

---

## ABC Traversal Queries

### The core drug repurposing query
```cypher
// Find diseases a drug might treat via shared gene targets
// A = Drug, B = Gene, C = Disease
MATCH (a:Drug {name: $drug_name})-[:TARGET|CARRIER|ENZYME|TRANSPORTER]-(b:Gene)-[:ASSOCIATED_WITH]-(c:Disease)
WHERE NOT (a)-[:INDICATION]-(c)
AND a <> c
RETURN c.name AS disease,
       c.node_id AS disease_id,
       collect(DISTINCT b.name) AS intermediary_genes,
       count(DISTINCT b) AS path_count
ORDER BY path_count DESC
LIMIT 50
```

### Comorbidity discovery
```cypher
// A = Disease, B = Gene, C = Disease
MATCH (a:Disease {name: $disease_name})-[:ASSOCIATED_WITH]-(b:Gene)-[:ASSOCIATED_WITH]-(c:Disease)
WHERE a <> c
RETURN c.name AS related_disease,
       collect(DISTINCT b.name) AS shared_genes,
       count(DISTINCT b) AS gene_overlap
ORDER BY gene_overlap DESC
LIMIT 50
```

### General ABC traversal (flexible)
```cypher
MATCH (a {name: $entity_name})-[r1]-(b)-[r2]-(c)
WHERE a <> c
AND NOT (a)-[]-(c)
AND labels(b)[0] IN $allowed_b_types
AND labels(c)[0] IN $allowed_c_types
RETURN labels(c)[0] AS target_type,
       c.name AS target_name,
       labels(b)[0] AS intermediary_type,
       collect(DISTINCT b.name)[..5] AS sample_intermediaries,
       count(DISTINCT b) AS path_redundancy
ORDER BY path_redundancy DESC
LIMIT 100
```

### CRITICAL QUERY RULES
1. **Always specify node types.** Never `MATCH (a)-[*2]-(c)`. Always `MATCH (a:Drug)-[:TARGET]-(b:Gene)-[:ASSOCIATED_WITH]-(c:Disease)`.
2. **Always exclude direct connections.** `WHERE NOT (a)-[:INDICATION]-(c)` ensures we only find novel paths.
3. **Always search names case-insensitive.** Use `=~ '(?i).*name.*'` or provide exact PrimeKG names.
4. **PPI edges were not loaded.** Do not write queries expecting Gene-Gene PPI edges.
5. **Disease-Gene relationship is `ASSOCIATED_WITH`**, not `DISEASE_PROTEIN`. The PrimeKG `disease_protein` relation loaded under the `display_relation` name `ASSOCIATED_WITH`.

---

## Novel Edges from Literature Agent

When the Literature Agent extracts new triples from PubMed, they are added with a distinct relationship type:
```cypher
MERGE (a:Gene {name: $gene_name})
ON CREATE SET a.node_type = 'gene/protein', a.source = 'literature_extraction'
MERGE (b:Disease {name: $disease_name})
ON CREATE SET b.node_type = 'disease', b.source = 'literature_extraction'
MERGE (a)-[r:LITERATURE_ASSOCIATION]->(b)
SET r.source = 'literature',
    r.is_novel = true,
    r.confidence = $confidence,
    r.source_papers = $paper_ids,
    r.extraction_date = datetime(),
    r.predicate = $predicate,
    r.evidence_type = $evidence_type,
    r.assertion_strength = $assertion_strength
```

ABC traversal queries should include LITERATURE_ASSOCIATION alongside curated edges:
```cypher
MATCH (a:Drug)-[:TARGET]-(b:Gene)-[:ASSOCIATED_WITH|LITERATURE_ASSOCIATION]-(c:Disease)
```

### Novel Edge Properties
| Property | Type | Description |
|---|---|---|
| `source` | string | Always "literature" for extracted edges |
| `is_novel` | boolean | Always true for extracted edges |
| `confidence` | float | 0-1, computed from corroboration x recency x journal x section weights |
| `source_papers` | string[] | PubMed IDs of source papers |
| `extraction_date` | datetime | When the edge was created |
| `predicate` | string | Constrained vocabulary: treats, binds, upregulates, downregulates, inhibits, activates, associated_with, expressed_in, participates_in, causes, negated |
| `evidence_type` | string | experimental, observational, computational, review |
| `assertion_strength` | string | direct, indirect, speculative, negated |

---

## Scoring Function for ABC Hypotheses
```
Composite = (0.3 x Novelty) + (0.25 x Path Redundancy) + (0.25 x Evidence Quality) + (0.2 x Clinical Relevance)
```

| Component | Formula | Notes |
|---|---|---|
| Novelty | 1.0 if no direct A-C edge; decays by publication count | Hub node penalty: 0.5x if B degree > 200 |
| Path Redundancy | min(independent_B_count / 5, 1.0) | Multiple independent paths = higher confidence |
| Evidence Quality | mean confidence of A-B and B-C edges | Uses the confidence scores on each edge |
| Clinical Relevance | 1.0 = druggable target/approved compound; 0.5 = known disease gene; 0.2 = other | |

**Multipliers:**
- Gene intermediary: 1.5x (over Pathway/BiologicalProcess)
- Anatomy intermediary: 1.3x (tissue-specific targets)
- PharmacologicClass intermediary: 0.7x (often rediscovers known relationships)
- Hub node (degree > 200): 0.5x novelty penalty

---

## Demo Entities — Exact PrimeKG Names

| Entity | PrimeKG name | PrimeKG node_id | Node type |
|---|---|---|---|
| Riluzole | Riluzole | DB00740 | Drug |
| GRM1 | GRM1 | 2911 | Gene |
| Melanoma | melanoma (disease) | 21639 | Disease |
| Thalidomide | Thalidomide | DB01041 | Drug |
| Multiple Myeloma | multiple myeloma | 24901 | Disease |
| TNF | TNF | 7124 | Gene |
| Sildenafil | Sildenafil | DB00203 | Drug |
| PDE5A | PDE5A | 8654 | Gene |
| Imatinib | Imatinib | DB00619 | Drug |
| KIT | KIT | 3815 | Gene |
| Metformin | Metformin | DB00331 | Drug |
| Aspirin | Aspirin | DB00945 | Drug |
| PTGS2 | PTGS2 | 5743 | Gene |
| Valproic acid | Valproic acid | DB00313 | Drug |
| HDAC1 | HDAC1 | 3065 | Gene |

---

## File Locations

- Raw PrimeKG data: `data/primekg/kg.csv`
- Drug features: `data/primekg/drug_features.csv`
- Disease features: `data/primekg/disease_features.csv`
- Node info: `data/primekg/node_info.csv`
- Load script: `scripts/load_primekg.py`
- Benchmark script: `scripts/benchmark.py`
- This documentation: `docs/data/primekg.md`
