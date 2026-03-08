# Semantic Scholar Academic Graph API Reference

## Base URL
`https://api.semanticscholar.org/graph/v1`

## Authentication
API key via header: `x-api-key: YOUR_KEY`
- Without key: 1 request/second
- With key: 100 requests/second

## Paper Endpoints

### GET /paper/search
Relevance-ranked paper search (max 1,000 results).

```
GET /paper/search?query=disease+mechanism&fields=title,abstract,year,citationCount&limit=100
```

**Parameters:**
- `query` (required): Plain-text search
- `fields`: Comma-separated (title, abstract, year, authors, citationCount, referenceCount, fieldsOfStudy, publicationDate, openAccessPdf, tldr, embedding)
- `offset` (default: 0), `limit` (default: 100, max: 100)
- `publicationTypes`: Review, JournalArticle, ClinicalTrial, MetaAnalysis, etc.
- `fieldsOfStudy`: Medicine, Biology, Chemistry, etc.
- `publicationDateOrYear`: Range like `2020-01-01:2025-12-31`
- `minCitationCount`: Minimum citations filter
- `openAccessPdf`: Filter for open access

### GET /paper/search/bulk
Bulk retrieval without ranking (up to 10M papers).

```
GET /paper/search/bulk?query=BRCA1+cancer&fields=title,abstract&sort=citationCount:desc
```

- Uses continuation `token` for pagination
- Boolean syntax: `+` (AND), `|` (OR), `-` (NOT), `"phrase"`
- `sort`: paperId, publicationDate, citationCount (asc/desc)

### GET /paper/{paper_id}
Single paper details. Supports multiple ID formats:
- Semantic Scholar ID, `DOI:`, `PMID:`, `PMCID:`, `ARXIV:`, `URL:`

```
GET /paper/PMID:12345678?fields=title,abstract,authors,citations,references
```

### POST /paper/batch
Batch lookup (max 500 papers per request).

```json
POST /paper/batch?fields=title,abstract
{"ids": ["DOI:10.1234/abc", "PMID:12345"]}
```

### GET /paper/{paper_id}/citations
Papers citing this paper (max 1,000 per page).

### GET /paper/{paper_id}/references
Papers referenced by this paper (max 1,000 per page).

### GET /snippet/search
Text snippet search across paper corpus.

## Author Endpoints

### GET /author/search
Search authors by name.

### GET /author/{author_id}
Author details with optional papers.

### GET /author/{author_id}/papers
Paginated papers by author.

### POST /author/batch
Batch author lookup (max 1,000 per request).

## Key Paper Fields
- `paperId`, `corpusId`, `title`, `abstract`
- `year`, `venue`, `publicationDate`
- `authors` (array: authorId, name)
- `citationCount`, `referenceCount`
- `isOpenAccess`, `openAccessPdf` (url, status)
- `fieldsOfStudy` (array)
- `embedding` (Specter vector)
- `tldr` (auto-generated summary)
- `citations`, `references` (with contexts, intents, isInfluential)

## Identifier Formats
- `CorpusId:123456`
- `DOI:10.1234/abc`
- `PMID:12345678`
- `PMCID:PMC1234567`
- `ARXIV:2301.12345`
- `URL:https://arxiv.org/abs/...`

## Rate Limits
- 10 MB max response size
- 1,000 max results for ranked search
- 10,000,000 max for bulk search
- 500 max IDs per batch request

## Date Filtering
Flexible ranges: `2019`, `2019-03`, `2019-03-05`, `2016:2020`, `2020-01-01:`, `:2023`

## Source
https://api.semanticscholar.org/api-docs/graph
