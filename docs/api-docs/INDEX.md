# API Documentation Index

Reference docs for all external APIs used by Nexus.

## Core Pipeline APIs

| API | Doc File | Purpose | Auth |
|-----|----------|---------|------|
| PaperQA2 | [paperqa2.md](paperqa2.md) | Literature synthesis engine (RAG on papers) | Anthropic/OpenAI key |
| NCBI E-utilities | [ncbi-eutils.md](ncbi-eutils.md) | PubMed paper search and retrieval | NCBI API key (free) |
| Semantic Scholar | [semantic-scholar.md](semantic-scholar.md) | Paper search, citations, embeddings | x-api-key header (free) |
| Neo4j Python Driver | [neo4j-python.md](neo4j-python.md) | Knowledge graph storage and Cypher queries | Neo4j Aura credentials |
| Hetionet | [hetionet.md](hetionet.md) | Base knowledge graph (47K nodes, 2.25M edges) | None (public data) |
| Tamarind Bio | [tamarind-bio.md](tamarind-bio.md) | Protein structure, docking, design (200+ models) | x-api-key header |
| BioRender MCP | [biorender-mcp.md](biorender-mcp.md) | Scientific figure generation | OAuth via BioRender account |
| Supabase | [supabase-python.md](supabase-python.md) | Postgres DB, auth, storage | SUPABASE_URL + keys |

## Full OpenAPI Specs
- Tamarind Bio: `../../tamarind-api-openapi.yaml` (project root)

## Environment Variables
All keys configured in `../../.env` -- see that file for signup URLs.
