# Nexus

Autonomous biological discovery platform. Finds unknown connections in biomedical research, validates them computationally and experimentally, then generates research reports.

## What It Does

Given a disease, gene, or compound, Nexus autonomously:

1. **Searches literature** (PubMed, Semantic Scholar) and extracts structured triples
2. **Builds a knowledge graph** by merging findings into Neo4j alongside PrimeKG/Hetionet (47K nodes, 2.25M edges)
3. **Discovers hypotheses** via Swanson ABC traversal: finds A->B->C paths where A-C is novel
4. **Scores and ranks** hypotheses by novelty, evidence strength, and path weight
5. **Validates computationally** using Tamarind Bio tools (molecular docking, protein folding, ADMET, binding affinity)
6. **Designs and runs experiments** (simulated dose-response assays with realistic 4PL curves)
7. **Interprets results** and generates research reports with visualizations
8. **Adapts** at checkpoints: continues, pivots to a different entity, or branches into parallel investigations

## Architecture

```
                    Literature Search
                    (PubMed, S2)
                         |
                    Triple Extraction
                    (Claude)
                         |
                    Knowledge Graph
                    (Neo4j + PrimeKG)
                         |
                    Swanson ABC Traversal
                    (novel A->C via B)
                         |
                    Hypothesis Scoring
                    & Reasoning
                         |
                    Computational Validation
                    (Tamarind Bio: DiffDock, ESMFold, ADMET, etc.)
                         |
                    Post-Validation Re-ranking
                         |
                    Experiment Design & Simulation
                    (dose-response, QC metrics)
                         |
                    Interpretation
                    (Claude + rule-based)
                         |
              +---------+---------+
              |                   |
         Validated           Refuted/Inconclusive
              |                   |
         Research Report     Failure Analysis
         (narrative, SVG,    (reasoning, concerns,
          pitch markdown)     next steps)
```

### Adaptive Pipeline

The pipeline uses checkpoint agents at key stages. At each checkpoint, Claude evaluates progress and decides:
- **CONTINUE**: proceed with current entity
- **PIVOT**: switch to a more promising entity
- **BRANCH**: explore multiple entities in parallel (max 3 concurrent)

### Backend Stack

| Component | Technology |
|-----------|-----------|
| Pipeline orchestrator | Python async, checkpoint-driven |
| Knowledge graph | Neo4j with PrimeKG seed data |
| Literature agents | PubMed/Semantic Scholar APIs + Claude extraction |
| Computational validation | Tamarind Bio REST API (20 tools) |
| Lab simulation | 4-parameter logistic dose-response curves |
| Result interpretation | Claude + rule-based fallback |
| Research output | Claude-generated SVG, narrative, pitch |
| Database | Supabase (sessions, events) |
| API | FastAPI |

### Frontend

Next.js 15 + React dashboard with:
- Query interface for hypothesis discovery
- Interactive knowledge graph explorer (react-force-graph-2d)
- Live agent reasoning stream
- Hypothesis detail pages with research output
- Discovery feed

## Project Structure

```
backend/src/nexus/
  agents/           # Literature search, triple extraction, reasoning, visualization
  graph/            # Neo4j client, Swanson ABC algorithm, PrimeKG seeding
  lab/              # Experiment design, simulation, interpretation, protocol generation
  cloudlab/         # Cloud lab provider interface (Strateos)
  tools/            # Tamarind Bio validation tools + registry + planner
  pipeline/         # Multi-stage adaptive orchestrator
  output/           # Research report generation (narrative, SVG, pitch)
  harness/          # Agent orchestration, budget enforcement
  checkpoint/       # Adaptive decisions (continue/pivot/branch)
  learning/         # Session logs, playbooks, auto-compaction
  heartbeat/        # Background paper ingestion, change detection
  db/               # Supabase client + Pydantic models
  api/              # FastAPI routes
  config.py         # Pydantic Settings

frontend/src/       # Next.js 15 dashboard
tests/              # 217 tests, mirrors backend structure
docs/plans/         # Design documents
```

## Setup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill in API keys

# Frontend
cd frontend && npm install && npm run dev

# Seed knowledge graph
python -c "import asyncio; from nexus.graph.seed import seed_all; asyncio.run(seed_all())"
```

### Required Environment Variables

- `ANTHROPIC_API_KEY`
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`

### Optional

- `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`
- `TAMARIND_BIO_API_KEY`
- `STRATEOS_EMAIL`, `STRATEOS_TOKEN`, `STRATEOS_ORGANIZATION_ID`

## Testing

```bash
pytest tests/ -v          # 217 tests
ruff check backend/       # linter
mypy backend/src/nexus/   # type checker
```

## Key Concepts

- **Swanson ABC**: Given entity A, find intermediary B and target C where A-B and B-C relationships exist but A-C is novel
- **PrimeKG**: Biomedical knowledge graph (47K nodes, 2.25M edges, 11 node types, 24 edge types) used as seed data
- **Checkpoint**: Adaptive decision points where the pipeline evaluates whether to continue, pivot, or branch
- **Tamarind Bio**: Computational biology platform with 20 tools (DiffDock, ESMFold, DeepFRI, ADMET, etc.)
- **Hypothesis types**: drug_repurposing, comorbidity, mechanism, target_discovery, drug_interaction, connection
