# PaperQA2 Reference

## Installation
```bash
pip install paper-qa>=5
```
For local embeddings: `pip install paper-qa[local]`

## Required Environment
- `OPENAI_API_KEY` or configure alternative LiteLLM-compatible model
- Optional: `CROSSREF_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` (for 100+ docs)

## Algorithm Workflow
1. **Paper Search** - LLM generates keyword queries; papers chunked and embedded
2. **Gather Evidence** - Query embedding ranks top-k chunks; LLM re-scores
3. **Generate Answer** - Best summaries inserted into prompt for final response

## CLI Usage
```bash
pqa ask "What mechanisms drive disease X?"
pqa search "search term"
pqa -i index_name ask "question"
```

**Settings profiles:**
- `--settings high_quality` (evidence_k=15, best accuracy, higher cost)
- `--settings fast` (quick, economical)
- `--settings wikicrow` (Wikipedia-style article generation)
- `--settings contractrow` (contradiction detection)

## Python API - Agentic (recommended)
```python
from paperqa import Settings, ask

answer = ask(
	"What mechanisms drive disease X?",
	settings=Settings(
		temperature=0.5,
		llm="claude-sonnet-4-20250514",
		summary_llm="claude-haiku-4-5-20251001",
		agent={"index": {"paper_directory": "my_papers"}}
	),
)
print(answer.formatted_answer)
```

Returns: `formatted_answer`, `answer`, `question`, `context`

## Python API - Manual Document Management
```python
from paperqa import Docs, Settings

docs = Docs()
await docs.aadd("file.pdf")
await docs.aadd_url("https://example.com/paper.pdf")
session = await docs.aquery("Question", settings=Settings())
```

**Methods (sync/async):**
- `add()` / `aadd()` - Add documents
- `add_file()` / `aadd_file()` - Add specific files
- `add_url()` / `aadd_url()` - Fetch from URLs
- `query()` / `aquery()` - Execute queries
- `get_evidence()` / `aget_evidence()` - Retrieve supporting passages

## Model Configuration
```python
Settings(
	llm="claude-sonnet-4-20250514",
	summary_llm="claude-haiku-4-5-20251001",
	embedding="text-embedding-3-small",  # or local: "st-multi-qa-MiniLM-L6-cos-v1"
)
```

Supports all LiteLLM-compatible providers (OpenAI, Anthropic, etc.)

## Key Settings
- `temperature` - LLM randomness (0-1)
- `evidence_k` - Number of chunks to retrieve
- `answer_max_sources` - Citation limit
- `rate_limit` - Format: "30000 per 1 minute"
- `llm_config` - Main LLM settings
- `summary_llm_config` - Summarization model
- `agent_llm_config` - Agentic decision-making model
- `parsing` - Chunking config (chunk_size, overlap)

## Supported Formats
PDF, TXT, MD, HTML, DOCX, XLSX, PPTX, PY, TS, YAML, and more.

## Multimodal (Dec 2025+)
Supports tables, figures, equations via Docling and Nvidia nemotron-parse PDF readers.

## Index Management
Create named indices for reuse across queries. Auto-detects new/modified documents.

## Source
https://github.com/Future-House/paper-qa
