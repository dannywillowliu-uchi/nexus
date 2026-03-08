# NCBI E-utilities API Reference

## Base URL
`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

## Authentication
API key required (since Dec 2018). Pass as `&api_key=YOUR_KEY` parameter.
- Without key: 3 requests/second
- With key: 10 requests/second

## Core Endpoints

### ESearch (esearch.fcgi)
Search Entrez databases and retrieve matching UIDs.

```
GET esearch.fcgi?db=pubmed&term=breast+cancer&retmax=100&api_key=KEY
```

**Parameters:**
- `db` (required): Target database (pubmed, gene, protein, etc.)
- `term` (required): Search query with field tags (e.g., `cancer AND 2024[pdat]`)
- `usehistory=y`: Store results on history server (returns QueryKey + WebEnv)
- `retstart`: Result offset (default: 0)
- `retmax`: Max results per call (default: 20)
- `retmode`: json or xml
- `sort`: relevance, pub_date, first_author

**Response:** UIDs, count, QueryKey, WebEnv

### EFetch (efetch.fcgi)
Download complete formatted records.

```
GET efetch.fcgi?db=pubmed&id=12345,67890&rettype=abstract&retmode=xml&api_key=KEY
```

**Parameters:**
- `db` (required): Target database
- `id` or `query_key`/`WebEnv`: Record identifiers
- `rettype`: Format (abstract, medline, full, xml)
- `retmode`: Delivery (xml, text, json)
- `retstart`/`retmax`: Pagination

### ESummary (esummary.fcgi)
Retrieve document summaries (DocSums).

```
GET esummary.fcgi?db=pubmed&id=12345&version=2.0&retmode=json&api_key=KEY
```

### ELink (elink.fcgi)
Find related records across databases.

```
GET elink.fcgi?dbfrom=pubmed&db=gene&id=12345&api_key=KEY
```

**Parameters:**
- `dbfrom` (required): Source database
- `db` (required): Destination database
- `id`: UID(s)
- `cmd`: neighbor, neighbor_history, acheck, llinks

### EInfo (einfo.fcgi)
Get database statistics and searchable fields.

```
GET einfo.fcgi?db=pubmed&retmode=json&api_key=KEY
```

### EPost (epost.fcgi)
Upload UID lists to history server.

### EGQuery (egquery.fcgi)
Global cross-database search returning hit counts.

### ESpell (espell.fcgi)
Spelling suggestions for queries.

### ECitMatch (ecitmatch.cgi)
Match bibliographic citations to PubMed records.

## Field Search Syntax
- `[tiab]` - Title/Abstract
- `[au]` - Author
- `[pdat]` - Publication Date
- `[mh]` - MeSH Terms
- `[journal]` - Journal Name
- `[pt]` - Publication Type

## History Server Pattern
1. ESearch with `usehistory=y` -> get QueryKey + WebEnv
2. EFetch with `query_key` + `WebEnv` -> paginate through results
3. Use `retstart` + `retmax` for batching large result sets

## Rate Limits
- With API key: 10 requests/second
- Without: 3 requests/second
- Large result sets: batch with retstart/retmax (max 10,000 per call)

## Source
https://www.ncbi.nlm.nih.gov/books/NBK25500/
