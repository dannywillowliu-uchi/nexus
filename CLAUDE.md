# Nexus - Autonomous Biological Discovery Platform

Discovers unknown connections in scientific research via Swanson ABC traversal,
validates computationally, and submits experiments to cloud labs.

Core loop: Discover -> Hypothesize -> Validate -> Experiment -> Learn -> Repeat

## Domain Ownership (Hackathon)

This is a hackathon project with parallel collaborators. Each person has a
**primary domain** they focus on. You are NOT restricted to your domain — touch
whatever files your implementation needs — but prefer working within your area
to minimize merge conflicts.

| Domain | Branch | Primary Owner | Primary Modules |
|--------|--------|---------------|-----------------|
| Protocol/Formatting | `domain/protocol` | Collaborator A | `cloudlab/`, `tools/generate_protocol.py`, `tools/schema.py` |
| Research Graph/Swanson | `domain/graph` | Collaborator B | `graph/`, `agents/literature/`, `agents/reasoning_agent.py` |
| Architecture/Integration | `dev` | Danny | `pipeline/`, `harness/`, `db/`, `checkpoint/`, `learning/`, `heartbeat/`, `config.py` |

### Shared Files (coordinate before changing)

These files are used across domains. If you need to modify them, mention it in
the group chat or leave a clear commit message so others know what changed:

- `backend/src/nexus/db/models.py` — Pydantic models shared by all modules
- `backend/src/nexus/tools/schema.py` — ToolResponse dataclass used by tools + harness
- `backend/src/nexus/config.py` — Global configuration
- `pyproject.toml` — Dependencies and tool config

### Branch Workflow

1. Clone the repo and checkout your domain branch (`domain/protocol` or `domain/graph`)
2. Push frequently to your branch — no PRs needed during the hackathon
3. Danny merges domain branches into `dev` for integration
4. `main` is the stable branch — only updated from `dev` after verification

### Conflict Resolution

If branches conflict at merge time, Danny (integrator) resolves them. Keep
commits small and focused to make this easy.

## Setup

```bash
./scripts/setup.sh
```

Or manually:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then fill in API keys
```

## Testing

```bash
pytest tests/ -v                   # all tests
pytest tests/graph/ -v             # domain-specific
ruff check backend/ tests/         # linter
mypy backend/src/nexus/            # type checker
```

## Project Structure

```
backend/src/nexus/
  agents/           # Literature search, triple extraction, reasoning
    literature/     # Paper search (PubMed, Semantic Scholar), Claude extraction
    reasoning_agent.py
  graph/            # Neo4j client, Swanson ABC algorithm, Hetionet seeding
  cloudlab/         # Lab provider interface (Strateos, future Ginkgo)
  tools/            # 7 validation tools + schema + registry
  pipeline/         # Multi-stage orchestrator with checkpoints
  harness/          # Agent orchestration, budget enforcement, validation loop
  checkpoint/       # Adaptive decisions (continue/pivot/branch)
  learning/         # Session logs, playbooks, auto-compaction
  heartbeat/        # Autonomous paper ingestion, change detection
  db/               # Supabase client + Pydantic models
  config.py         # Pydantic Settings (reads .env)

tests/              # Mirrors backend/src/nexus/ structure
docs/plans/         # Design documents
scripts/            # Utility scripts
learning/           # .md-based learning system (session logs, playbooks, pivot rules)
```

## Coding Conventions

- Python: tabs, double quotes, line-length 120
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
- All async functions use proper await
- Tests: pytest + pytest-asyncio (auto mode), 1:1 mapping with source files
- Type hints where beneficial, mypy strict mode
- Comments: minimal, only when logic is complex

## Environment Variables

Copy `.env.example` to `.env` and fill in API keys. Required:
- ANTHROPIC_API_KEY
- NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
- SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

Optional:
- NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY
- TAMARIND_BIO_API_KEY, BIORENDER_API_KEY
- STRATEOS_EMAIL, STRATEOS_TOKEN, STRATEOS_ORGANIZATION_ID

## Key Concepts

- **Swanson ABC**: Given entity A, find intermediary B and target C where A-B
  and B-C relationships exist but A-C is novel. Core algorithm in `graph/abc.py`.
- **Hetionet**: Biomedical knowledge graph (47K nodes, 2.25M edges, 11 node types,
  24 edge types) used as seed data for Neo4j.
- **Autoprotocol**: JSON format for cloud lab experiment submission (Strateos).
- **Checkpoint**: Adaptive decision points — CONTINUE, PIVOT (change entity),
  or BRANCH (parallel investigation).
- **Heartbeat**: Background loop ingesting new papers, detecting high-entropy
  changes to the knowledge graph.

## Key Architecture

- **Adaptive Pipeline**: Literature -> Checkpoint -> Graph -> Checkpoint -> Reasoning -> Validation -> Viz -> Protocol
- **Checkpoints**: Agent decides CONTINUE, PIVOT, or BRANCH at each stage
- **Learning System**: .md files auto-compact to prevent infinite growth
- **Graph Evolution**: Neo4j edges carry provenance and get updated through pipeline stages

## Seeding Hetionet

```bash
python -c "import asyncio; from nexus.graph.seed import seed_all; asyncio.run(seed_all())"
```
