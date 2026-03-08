# Hetionet Knowledge Graph Reference

## Overview
Hetionet v1.0: integrative biomedical network for drug repurposing and disease mechanism discovery.
- **47,031 nodes** across 11 types
- **2,250,197 relationships** across 24 types
- Created for Project Rephetio (eLife, 2017, DOI: 10.7554/elife.26726)

## Node Types (11)
1. Anatomy
2. Biological Process
3. Cellular Component
4. Compound (drugs)
5. Disease
6. Gene
7. Molecular Function
8. Pathway
9. Pharmacologic Class
10. Side Effect
11. Symptom

## Relationship Types (24) - Format: Type_SourceTargetAbbrev
- `ASSOCIATES_DaG` - Disease associates with Gene
- `DOWNREGULATES_DdG` - Disease downregulates Gene
- `UPREGULATES_DuG` - Disease upregulates Gene
- `LOCALIZES_DlA` - Disease localizes to Anatomy
- `PRESENTS_DpS` - Disease presents Symptom
- `RESEMBLES_DrD` - Disease resembles Disease
- `PALLIATES_CpD` - Compound palliates Disease
- `TREATS_CtD` - Compound treats Disease
- `CAUSES_CcSE` - Compound causes Side Effect
- `BINDS_CbG` - Compound binds Gene
- `DOWNREGULATES_CdG` - Compound downregulates Gene
- `UPREGULATES_CuG` - Compound upregulates Gene
- `INTERACTS_GiG` - Gene interacts with Gene
- `REGULATES_GrG` - Gene regulates Gene
- `COVARIES_GcG` - Gene covaries with Gene
- `PARTICIPATES_GpBP` - Gene participates in Biological Process
- `PARTICIPATES_GpCC` - Gene participates in Cellular Component
- `PARTICIPATES_GpMF` - Gene participates in Molecular Function
- `PARTICIPATES_GpPW` - Gene participates in Pathway
- `EXPRESSES_AeG` - Anatomy expresses Gene
- `INCLUDES_PCiC` - Pharmacologic Class includes Compound
- Plus additional relationship types

## Neo4j Import

### Option 1: Neo4j dump (fastest)
Download `hetionet-v1.0-neo4j.dump` from GitHub releases.
```bash
neo4j-admin database load --from-path=./dump hetionet
```

### Option 2: CSV import (~70 seconds)
Convert JSON to CSV, then upload:
```bash
# JSON-to-CSV conversion: ~30 seconds
# CSV-to-Neo4j upload: ~40 seconds
```

### Option 3: Public read-only instance
```python
driver = GraphDatabase.driver("bolt://neo4j.het.io")
```
120-second query timeout. For heavy use, run locally.

## Essential Cypher Queries

### Find a disease
```cypher
MATCH (d:Disease {name: "lung cancer"}) RETURN d
```

### Disease-gene associations
```cypher
MATCH (d:Disease {name: "lung cancer"})-[:ASSOCIATES_DaG]-(g:Gene)
RETURN g.name, g.description
```

### Shared genes between diseases (Swanson ABC pattern)
```cypher
MATCH (d1:Disease)-[:ASSOCIATES_DaG]-(g:Gene)-[:ASSOCIATES_DaG]-(d2:Disease)
WHERE d1.name = "liver cancer" AND d2.name = "kidney cancer"
RETURN g.name, g.description ORDER BY g.name
```

### Compounds treating a disease
```cypher
MATCH (c:Compound)-[:TREATS_CtD]->(d:Disease {name: "epilepsy"})
RETURN c.name, c.description
```

### Full Swanson ABC: Disease -> Gene -> Compound (drug repurposing)
```cypher
MATCH (d:Disease {name: "Parkinson's disease"})-[:ASSOCIATES_DaG]-(g:Gene)-[:BINDS_CbG]-(c:Compound)
WHERE NOT (c)-[:TREATS_CtD]->(d)
RETURN DISTINCT c.name AS drug, g.name AS gene,
	count(*) AS paths
ORDER BY paths DESC LIMIT 20
```

### Gene in pathway expressed in tissue
```cypher
MATCH path = (bp:BiologicalProcess)-[:PARTICIPATES_GpBP]-(g:Gene)-[:EXPRESSES_AeG]-(a:Anatomy)
WHERE bp.name = "apoptotic process" AND a.name = "liver"
RETURN path
```

### Count all relationship types
```cypher
MATCH ()-[r]->()
RETURN type(r) AS rel_type, count(*) AS count
ORDER BY count DESC
```

## Data Download
- GitHub: https://github.com/hetio/hetionet
- Zenodo: https://zenodo.org/records/268568
- Formats: JSON, TSV, Neo4j dump, Matrix (HetMat)
- License: CC0 Public Domain (repository content); mixed for integrated data

## Git LFS Required
Large files use Git LFS. Install before cloning:
```bash
git lfs install
git clone https://github.com/hetio/hetionet.git
```

## Neo4j Aura Free Tier Compatibility
47K nodes + 2.25M edges fits within Aura free tier (200K nodes limit).

## Source
- https://github.com/hetio/hetionet
- https://neo4j.het.io/guides/hetionet.html
- https://het.io/explore/
