# Nexus Design Document
**Date:** 2026-03-08
**Status:** Approved

## Overview

Nexus is an autonomous biological discovery platform that finds unknown connections in scientific research, validates them computationally and experimentally, and learns from its results. It combines Swanson-style literature-based discovery with an adaptive checkpoint/pivot system, computational validation, cloud lab integration, and a persistent learning system.

The core loop: **Discover -> Hypothesize -> Validate -> Experiment -> Learn -> Repeat**

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      NEXT.JS FRONTEND                        │
│  Landing | Query Builder | Discovery Feed | Graph Explorer   │
│  Session Monitor (live SSE) | Hypothesis Detail | Dashboard  │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST + SSE
                           v
┌──────────────────────────────────────────────────────────────┐
│                      FASTAPI GATEWAY                         │
│  Supabase Auth | Credits | asyncio Job Queue | SSE Stream    │
└─────────┬──────────────────────────────┬─────────────────────┘
          │                              │
          v                              v
┌───────────────────────┐     ┌─────────────────────────┐
│  ADAPTIVE PIPELINE    │     │  HEARTBEAT ENGINE       │
│                       │     │  (scheduled, autonomous) │
│  Literature Agent     │     └─────────────────────────┘
│    CHECKPOINT ◆       │
│  Graph Agent          │     ┌─────────────────────────┐
│    CHECKPOINT ◆       │     │  LEARNING SYSTEM        │
│  Reasoning Agent      │     │  learning/              │
│  Validation Agent     │     │  ├── sessions/          │
│    CHECKPOINT ◆       │     │  ├── playbooks/         │
│  Viz Agent (BioRender)│     │  ├── pivot-rules.md     │
│  Protocol Agent       │     │  └── compaction-log.md  │
│    CHECKPOINT ◆       │     └─────────────────────────┘
│  [Parse results,      │
│   pivot or confirm]   │     ┌─────────────────────────┐
└───────────────────────┘     │  CLOUDLAB ADAPTER       │
                              │  Strateos (day one)     │
                              │  Ginkgo (future)        │
                              └─────────────────────────┘
```

## Adaptive Pipeline with Checkpoints

The pipeline is not linear. At each checkpoint (◆), a Checkpoint Agent evaluates results and decides:

- **CONTINUE** - results are on track, proceed to next stage
- **PIVOT** - a more interesting entity emerged, restart pipeline from Literature Agent with new target
- **BRANCH** - run a parallel investigation on the new entity while continuing the original

Checkpoint logic:
1. Read pivot-rules.md and relevant domain playbook
2. Evaluate current results against learned heuristics
3. Make decision based on rules + current context

Pivot budget: each session has a max pivot/branch count (default 3) to prevent infinite recursion.

### Checkpoint Placement

- **After Literature Agent:** if >3 triples mention an entity not in the original query, consider branching
- **After Graph Agent:** if top ABC hypothesis reveals a surprising intermediary, consider pivoting literature search
- **After Validation:** if computational validation reveals unexpected interactions, consider new discovery branch
- **After CloudLab results:** if experiment confirms/refutes, decide whether to follow up or pivot

## Agent Pipeline Detail

### Stage 1: Literature Agent
- Searches PubMed (NCBI E-utilities) and Semantic Scholar
- Uses Claude to extract (subject, predicate, object) triples from paper abstracts
- Output: LiteratureResult with papers, triples, confidence scores

### Stage 2: Graph Agent
- Merges new triples into Neo4j as new edges
- Runs Swanson ABC traversal: any source type -> any intermediary -> any target type
- Ranks by composite score: novelty, evidence density, path strength
- Output: ranked ABCHypothesis list

### Stage 3: Reasoning Agent
- Quick summaries for all hypotheses (single Claude call)
- Full research briefs for top N (parallel Claude calls)
- Structured confidence: graph evidence, literature support, biological plausibility, novelty

### Stage 4: Validation Agent
- Claude-driven tool selection loop with budget enforcement
- 7 MCP tools: literature_validate, compound_lookup, pathway_overlap, protein_interaction, expression_correlate, molecular_dock, generate_protocol
- Tamarind Bio for computational validation (AlphaFold, DiffDock, docking)
- Output: verdict per hypothesis (validated/refuted/inconclusive)

### Stage 5: Visualization Agent
- BioRender MCP for scientific mechanism-of-action figures
- Generates traceable visual diagrams showing the full discovery path including pivots

### Stage 6: Protocol Agent
- Generates experimental protocols based on validated hypotheses
- Formats for target CloudLab (Autoprotocol JSON for Strateos)
- Submits, polls, parses results
- Results feed back into checkpoint system

## Graph Evolution

The Neo4j knowledge graph is a living entity that grows with every session:

- **Literature Agent** extracts triples -> new edges (`source: "literature"`, `is_novel: true`)
- **ABC Discovery** finds connections -> hypothesized edges (`source: "abc_discovery"`, `status: "hypothesized"`)
- **Validation** confirms/refutes -> edge updated (`status: "validated"` or `"refuted"`, `validation_score`)
- **CloudLab results** -> experimental evidence (`status: "experimentally_confirmed"`, `experiment_id`)
- **Pivot discoveries** -> new edges from branched investigations also merged

Each edge carries provenance: origin, timestamp, evidence, confidence level.

Seeded from Hetionet v1.0: 47,031 nodes (11 types), 2,250,197 edges (24 types).

## Learning System

Three layers of .md files under `learning/`:

### Layer 1: Session Logs (`learning/sessions/<session-id>.md`)
Written after each session. Contains: query, entities explored, pivots taken, hypotheses, validation outcomes, learnings.

### Layer 2: Domain Playbooks (`learning/playbooks/<domain>.md`)
Per-domain heuristics distilled from session logs. Example: "for neurodegenerative diseases, Gene intermediaries outperform Pathway intermediaries."

### Layer 3: Pivot Rules (`learning/pivot-rules.md`)
Cross-domain rules for checkpoint decisions. Natural language heuristics the agent reads before each checkpoint.

### Auto-Compaction
- Session logs: after 50 sessions, summarize oldest 40 into archive digest, delete originals
- Domain playbooks: when >200 lines, rewrite keeping only patterns confirmed by 3+ sessions
- Pivot rules: when >50 entries, rank by productive outcome rate, prune bottom 20%
- All compaction events logged in `learning/compaction-log.md`

## CloudLab Integration

Abstract provider interface so any platform can plug in.

**Day one: Strateos**
- Autoprotocol JSON format for protocol submission
- `transcriptic analyze` for dry-run validation
- REST API for live submission when sales access secured
- Python client: `pip install transcriptic`

**Future: Ginkgo Cloud Lab**
- Same interface, swap provider when public API ships

**Result loop:** CloudLab results feed back into checkpoints. Confirm -> publish. Refute -> check alternative targets. Inconclusive -> redesign experiment.

## Data Model

### Neo4j (Knowledge Graph)
- 11 node types from Hetionet + extensions
- 24 relationship types + novel edges from pipeline
- Edge properties: evidence_count, confidence, source_papers[], is_novel, discovery_date, status, validation_score

### Supabase (Postgres)
- `profiles` - user auth, tier, credits
- `jobs` - session queue, status, pipeline_step
- `hypotheses` - ABC paths, evidence chains, validation results, briefs
- `feed_entries` - public Discovery Feed
- `subscriptions` - user -> disease area alerts
- `sessions` - session metadata, pivot trace
- `experiments` - CloudLab submissions, status, results
- `api_keys` - enterprise keys
- Row-level security on all tables

## API Surface

```
POST /api/sessions              Create research session
GET  /api/sessions/{id}/stream  SSE stream of live events
GET  /api/sessions/{id}/events  All events for session
GET  /api/sessions/{id}/report  Final hypothesis report

POST /api/query                 Quick query (no session tracking)
GET  /api/feed                  Discovery Feed (paginated, filterable)
GET  /api/graph/explore         Interactive graph query
GET  /api/hypotheses/{id}       Full hypothesis detail

POST /api/experiments           Submit protocol to CloudLab
GET  /api/experiments/{id}      Poll experiment status + results

POST /api/subscribe             Subscribe to disease area alerts
GET  /api/credits               Credit balance
GET  /api/health                System health
```

## Frontend Pages

1. **Landing** - live stats, sample discoveries, sign up
2. **Query Builder** - entity autocomplete, target type filters, reasoning depth, pivot budget
3. **Session Monitor** - real-time agent trace, hypothesis panel, metrics bar, pivot branches
4. **Discovery Feed** - scrollable discoveries, disease-area filters, subscriptions
5. **Graph Explorer** - interactive Neo4j visualization, clickable nodes, ABC path highlighting
6. **Hypothesis Detail** - evidence chain, ABC path, BioRender figures, confidence breakdown, brief, experiment status
7. **Dashboard** - credits, session history, subscriptions, API keys

Design: light/clean/medical. White backgrounds, slate text (#1e293b), teal accents (#0891b2).

## Tech Stack

**Backend:** Python 3.12, FastAPI, Anthropic SDK, PaperQA2, Neo4j async driver, Supabase, httpx, asyncio

**Frontend:** Next.js 14+ (App Router), React, Tailwind CSS, shadcn/ui, react-force-graph-2d, TanStack Query, Supabase client

**External:** Anthropic (Claude), NCBI E-utilities, Semantic Scholar, Neo4j Aura, Supabase, Tamarind Bio, BioRender MCP, Strateos

**Dev:** pytest, pytest-asyncio, ruff, mypy

## Build Phases

```
Phase 1:  Scaffolding + Data Layer
Phase 2:  Core ABC Engine
Phase 3:  Literature Agent
Phase 4:  Checkpoint System + Learning
Phase 5:  Pipeline Orchestrator
Phase 6:  Validation Agent + MCP Tools
Phase 7:  Reasoning Agent
Phase 8:  CloudLab Integration
Phase 9:  Visualization (BioRender)
Phase 10: Heartbeat Engine
Phase 11: Frontend
Phase 12: Integration + Deployment
```

## Available API Keys

- Anthropic (Claude) - live
- NCBI E-utilities - live
- Semantic Scholar - live
- Neo4j Aura - live
- Supabase - live
- Tamarind Bio - live
- Vercel - live
- BioRender - not yet
- Redis - not yet (using asyncio)
- Strateos - not yet (need sales contact)
