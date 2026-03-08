# Nexus - Autonomous Biological Discovery Platform

## Quick Start

### Backend
```bash
cd /Users/dannyliu/personal_projects/nexus
source .venv/bin/activate
pip install -e ".[dev]"
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Backend Server
```bash
uvicorn nexus.api.app:app --reload --port 8000
```

## Testing

```bash
# All tests
.venv/bin/pytest tests/ -v

# Specific module
.venv/bin/pytest tests/graph/ -v
.venv/bin/pytest tests/harness/ -v

# Linter
.venv/bin/ruff check backend/ tests/

# Type checker
.venv/bin/mypy backend/src/nexus/
```

## Project Structure

```
backend/src/nexus/
  config.py          # Pydantic Settings (reads .env)
  graph/             # Neo4j client, Hetionet seed, ABC traversal
  db/                # Supabase models and migrations
  agents/            # Literature, Reasoning, Viz agents
  checkpoint/        # Adaptive checkpoint system
  learning/          # Session logs, playbooks, pivot rules, auto-compaction
  pipeline/          # Adaptive pipeline orchestrator
  tools/             # 7 validation MCP tools + registry
  harness/           # Agent harness, event store, validation agent, session runner
  cloudlab/          # CloudLab provider interface, Strateos adapter, protocol agent
  heartbeat/         # Autonomous paper ingestion + delta detection
  api/               # FastAPI gateway + routes

frontend/src/
  app/               # Next.js pages (landing, query, session, feed, graph, hypothesis, dashboard)
  lib/               # API client, utilities

learning/            # .md-based learning system (session logs, playbooks, pivot rules)
tests/               # Mirrors backend structure
```

## Coding Conventions

- Python: tabs, double quotes, line-length 120
- Frontend: 2-space indent (standard)
- Conventional commits: feat:, fix:, refactor:, docs:, test:
- All async functions use proper await
- Tests use pytest-asyncio with auto mode

## Environment Variables

Copy `.env.example` to `.env` and fill in API keys. Required:
- ANTHROPIC_API_KEY
- NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
- SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

Optional:
- NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY
- TAMARIND_BIO_API_KEY, BIORENDER_API_KEY
- STRATEOS_EMAIL, STRATEOS_TOKEN, STRATEOS_ORGANIZATION_ID

## Seeding Hetionet

```bash
python -c "import asyncio; from nexus.graph.seed import seed_all; asyncio.run(seed_all())"
```

## Key Architecture

- **Adaptive Pipeline**: Literature -> Checkpoint -> Graph -> Checkpoint -> Reasoning -> Validation -> Viz -> Protocol
- **Checkpoints**: Agent decides CONTINUE, PIVOT, or BRANCH at each stage
- **Learning System**: .md files auto-compact to prevent infinite growth
- **Graph Evolution**: Neo4j edges carry provenance and get updated through pipeline stages
