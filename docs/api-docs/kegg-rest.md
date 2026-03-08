# KEGG REST API Reference

## Base URL
`https://rest.kegg.jp`

## Authentication
None required (public API).

## Rate Limits
- Max 3 requests per second
- Bulk downloads discouraged; use incremental queries
- HTTPS only (HTTP deprecated)

## Response Format
Tab-delimited text (not JSON). Parse by splitting on `\t` and `\n`.

## Core Operations

### /find — Search
Search KEGG databases by keyword.

```
GET /find/{database}/{query}
```

**Databases:** `genes`, `compound`, `pathway`, `disease`, `drug`, `enzyme`, `reaction`, `module`

```
GET /find/genes/hsa:TP53
GET /find/compound/curcumin
GET /find/pathway/apoptosis
GET /find/disease/cancer
```

**Response (tab-delimited):**
```
hsa:7157	TP53; tumor protein p53
```

### /get — Retrieve
Get full entry details.

```
GET /get/{entry_id}
GET /get/{entry_id}/{option}
```

Options: `aaseq` (amino acid), `ntseq` (nucleotide), `mol` (molecule), `kcf` (KCF), `image` (pathway image)

```
GET /get/hsa:7157
GET /get/hsa05200        # Pathways in cancer
GET /get/C00001          # Water compound
GET /get/hsa05200/image  # Pathway image (PNG)
```

### /link — Cross-references
Find linked entries between databases.

```
GET /link/{target_db}/{source_entry}
GET /link/{target_db}/{source_db}
```

```
GET /link/pathway/hsa:7157      # Pathways for TP53
GET /link/disease/hsa:7157      # Diseases for TP53
GET /link/compound/hsa05200     # Compounds in pathway
```

**Response:**
```
hsa:7157	path:hsa04115
hsa:7157	path:hsa04210
hsa:7157	path:hsa05200
```

### /list — Enumerate
List all entries in a database.

```
GET /list/{database}
GET /list/{database}/{organism}
```

```
GET /list/pathway/hsa     # All human pathways
GET /list/organism         # All organisms
```

### /conv — ID Conversion
Convert between KEGG IDs and external IDs.

```
GET /conv/{target_db}/{source_entry}
GET /conv/{target_db}/{source_db}
```

```
GET /conv/ncbi-geneid/hsa:7157    # KEGG -> NCBI Gene ID
GET /conv/uniprot/hsa:7157        # KEGG -> UniProt
```

## Organism Codes
- `hsa` — Homo sapiens (human)
- `mmu` — Mus musculus (mouse)
- `rno` — Rattus norvegicus (rat)
- `dme` — Drosophila melanogaster
- `sce` — Saccharomyces cerevisiae

## Compound IDs
- `C00001` — Water
- `C00002` — ATP
- `C07580` — Curcumin
- Format: `C` + 5-digit number

## Pathway IDs
- `hsa04115` — p53 signaling pathway
- `hsa04210` — Apoptosis
- `hsa05200` — Pathways in cancer
- Format: organism code + 5-digit number

## Parsing Example (Python)
```python
def parse_kegg_tab(text: str) -> list[list[str]]:
	rows = []
	for line in text.strip().split("\n"):
		if line.strip():
			rows.append(line.split("\t"))
	return rows
```

## Nexus Usage
- `tools/pathway_overlap.py` — Uses `/find/genes/` and `/link/pathway/` to check shared pathways between two genes
- Validates ABC hypotheses by checking if gene A and gene C share biological pathways through intermediary B

## Source
- https://rest.kegg.jp/
- https://www.kegg.jp/kegg/rest/keggapi.html
