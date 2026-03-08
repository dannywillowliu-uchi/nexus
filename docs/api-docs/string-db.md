# STRING Database API Reference

## Base URL
`https://string-db.org/api`

## Authentication
None required (public API).

## Rate Limits
Not explicitly documented; be respectful. Batch endpoints preferred for multiple queries.

## Response Formats
Append format to URL: `/json/`, `/tsv/`, `/xml/`, `/psi-mi/`, `/psi-mi-tab/`

Example: `https://string-db.org/api/json/interaction_partners`

## Core Endpoints

### GET /json/interaction_partners
Get interaction partners for a protein.

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| `identifiers` | Yes | Protein name(s), newline-delimited for multiple |
| `species` | No | NCBI taxon ID (9606 for human) |
| `limit` | No | Max interactions returned (default 10) |
| `required_score` | No | Min combined score 0-1000 (default 400) |
| `network_type` | No | `functional` (default) or `physical` |

```
GET /api/json/interaction_partners?identifiers=TP53&species=9606&limit=20&required_score=700
```

**Response:**
```json
[
	{
		"stringId_A": "9606.ENSP00000269305",
		"stringId_B": "9606.ENSP00000352610",
		"preferredName_A": "TP53",
		"preferredName_B": "MDM2",
		"ncbiTaxonId": 9606,
		"score": 999,
		"nscore": 0,
		"fscore": 0,
		"pscore": 0,
		"ascore": 0,
		"escore": 953,
		"dscore": 927,
		"tscore": 975
	}
]
```

**Score channels:**
- `nscore` — Neighborhood
- `fscore` — Gene fusion
- `pscore` — Phylogenetic co-occurrence
- `ascore` — Co-expression
- `escore` — Experimental
- `dscore` — Database (curated)
- `tscore` — Text-mining
- `score` — Combined score (0-1000)

### GET /json/network
Get the full interaction network among a set of proteins.

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| `identifiers` | Yes | Newline-delimited protein names |
| `species` | No | NCBI taxon ID |
| `required_score` | No | Min combined score |
| `network_type` | No | `functional` or `physical` |

```
GET /api/json/network?identifiers=TP53%0AMDM2%0ABRCA1&species=9606
```

### GET /json/enrichment
Functional enrichment analysis for a set of proteins.

**Parameters:**
| Param | Required | Description |
|-------|----------|-------------|
| `identifiers` | Yes | Newline-delimited protein names |
| `species` | Yes | NCBI taxon ID |

**Response includes:**
- GO Biological Process, Molecular Function, Cellular Component
- KEGG pathways
- Pfam domains
- InterPro domains

```json
[
	{
		"category": "Process",
		"term": "GO:0006915",
		"description": "apoptotic process",
		"number_of_genes": 3,
		"number_of_genes_in_background": 1572,
		"p_value": 0.00012,
		"fdr": 0.0035
	}
]
```

### GET /json/resolve
Resolve protein names to STRING identifiers.

```
GET /api/json/resolve?identifier=TP53&species=9606
```

### GET /json/version
Get current STRING version info.

### GET /json/homology
Get homology relationships.

## Nexus Usage
- `tools/pathway_overlap.py` could be extended to use STRING for protein-protein interaction validation
- Useful for validating Swanson ABC hypotheses involving protein interactions
- Combined score > 700 = high confidence interaction
- Score > 900 = very high confidence

## Source
- https://string-db.org/cgi/help
- https://string-db.org/cgi/access
