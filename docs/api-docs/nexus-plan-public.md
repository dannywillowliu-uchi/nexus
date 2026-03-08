# Nexus: Autonomous Biological Discovery Platform

## What is Nexus?

Nexus is an open platform that autonomously discovers unknown connections in biological research. It combines Swanson-style literature-based discovery with computational validation to continuously mine the scientific literature, traverse a biomedical knowledge graph for indirect connections, validate hypotheses computationally, and produce visualized, citation-backed results.

The core idea is simple: if entity A relates to entity B in one research context, and entity B relates to entity C in another context, then the A-C connection may be a novel, undiscovered relationship worth investigating. Nexus automates this process at scale across the entire biomedical knowledge space.

## Core Capabilities

### 1. Disease Mechanism Discovery (Core Engine)
Swanson ABC linkage across literature and knowledge graphs to find novel mechanistic pathways. Given any biological entity, Nexus traverses indirect connections to surface hypotheses that no single researcher would find by reading papers alone.

### 2. Drug Repurposing (Downstream)
Maps discovered mechanisms to existing approved compounds. If a disease shares a gene target with a compound approved for something else, that compound becomes a repurposing candidate.

### 3. Translation Gap Detection (Alerting)
Flags basic science findings that are ready for clinical translation but haven't crossed over yet.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  NEXT.JS FRONTEND                    │
│  Landing | Query Builder | Discovery Feed |          │
│  Graph Explorer | Hypothesis Detail | Dashboard      │
└──────────────────────┬──────────────────────────────┘
                       │ REST + SSE
                       v
┌─────────────────────────────────────────────────────┐
│                  FASTAPI GATEWAY                     │
│  Supabase Auth | Credits | Job Queue (Redis) | API   │
└──────────┬───────────────────────┬──────────────────┘
           │                       │
           v                       v
┌────────────────────┐  ┌──────────────────────┐
│  ON-DEMAND JOBS    │  │  HEARTBEAT ENGINE    │
│  (user queries)    │  │  (autonomous)        │
│                    │  │                      │
│  Agent SDK         │  │  Tiered frequency:   │
│  Orchestrator      │  │  Free: weekly        │
│       │            │  │  Pro: daily          │
│       v            │  │  Enterprise: realtime│
│  ┌────────────┐    │  │                      │
│  │ Literature │    │  │  Same agent pipeline │
│  │ Agent      │    │  │  but auto-triggered  │
│  │ (PaperQA2) │    │  └──────────────────────┘
│  └─────┬──────┘    │
│        v           │
│  ┌────────────┐    │
│  │ Graph      │    │
│  │ Agent      │    │
│  │ (Neo4j     │    │
│  │  ABC walk) │    │
│  └─────┬──────┘    │
│        v           │
│  ┌────────────┐    │
│  │ Validation │    │
│  │ Agent      │    │
│  │ (Tamarind  │    │
│  │  Bio API)  │    │
│  └─────┬──────┘    │
│        v           │
│  ┌────────────┐    │
│  │ Viz Agent  │    │
│  │ (BioRender │    │
│  │  MCP)      │    │
│  └────────────┘    │
└────────────────────┘
```

## Agent Pipeline

Each research job (user query or heartbeat-triggered) runs through a four-stage pipeline:

### Stage 1: Literature Agent
- Takes a disease name or research question as input
- Searches PubMed (NCBI E-utilities) and Semantic Scholar for relevant papers
- Extracts entity-relationship triples: e.g. (Gene A) --[mechanism]--> (Pathway B), (Pathway B) --[implicated in]--> (Disease C)
- Outputs structured triples with evidence citations and confidence scores

### Stage 2: Graph Agent
- Merges new triples into the knowledge graph (seeded from Hetionet: 47K nodes, 2.25M edges across 11 node types and 24 relationship types)
- Runs Swanson ABC traversal: finds indirect A-C paths through shared B intermediaries
- Ranks paths by novelty (not in existing literature), evidence density, and clinical relevance
- Outputs a ranked list of novel ABC hypotheses

### Stage 3: Validation Agent
- Takes top hypotheses involving protein targets
- Runs computational validation via Tamarind Bio: structure prediction (AlphaFold), binding prediction (DiffDock), molecular docking
- Adds a computational evidence score to each hypothesis

### Stage 4: Visualization Agent
- Generates scientific mechanism-of-action figures using BioRender
- Provides visual assets for each validated hypothesis

## Heartbeat Engine (Autonomous Discovery)

The heartbeat turns Nexus from a passive query tool into an active discovery engine that continuously monitors the scientific literature:

1. **Paper Ingestion.** Scheduled jobs pull new papers from PubMed and bioRxiv.
2. **Delta Detection.** Compares new edges against the existing graph. Flags "high-delta" events where a new A-B link creates novel ABC paths that didn't exist before.
3. **Autonomous ABC Sweep.** Runs Swanson traversal on the highest-delta new edges.
4. **Self-Prompting.** The heartbeat agent asks: "Given these new connections, what are the most surprising implications?"
5. **Scoring and Queuing.** Hypotheses scored by (novelty x clinical impact x validateability). Top candidates queued for computational validation.
6. **Discovery Feed.** Validated discoveries published to a public feed, with disease-area subscriptions for researchers.

### Tiered Access

| Tier | Heartbeat | Queries/month | Features |
|------|-----------|---------------|----------|
| Free | Weekly community digest | 3 | Browse Discovery Feed, view public hypotheses |
| Pro | Daily scans for subscribed diseases | 30 | Full results, graph explorer, export |
| Enterprise | Real-time continuous monitoring | Unlimited | Custom disease portfolios, API access, priority validation |

## Multi-Type Discovery (v2)

The initial version focuses on Disease-to-Compound discovery (drug repurposing). Version 2 generalizes to any entity type combination, unlocking a much broader space of discoveries:

| A Type | B Type | C Type | Discovery Category |
|--------|--------|--------|--------------------|
| Disease | Gene | Compound | Drug repurposing |
| Disease | Gene | Disease | Comorbidity mechanism |
| Disease | BiologicalProcess | Disease | Shared pathology |
| Compound | Gene | Compound | Drug interaction prediction |
| Gene | Compound | Gene | Off-target effect discovery |
| Disease | Gene | BiologicalProcess | Mechanistic insight |
| Disease | Anatomy | Gene | Tissue-specific targets |
| Compound | Gene | BiologicalProcess | Drug mechanism elucidation |

In auto-explore mode, given a starting entity, Nexus runs ABC across all viable (A-type, B-type, C-type) combinations and ranks the results by a composite score.

## Claude Reasoning Pipeline

Raw A-B-C paths are not enough. Researchers need to understand why a connection matters, how confident they should be, and what to do next. The reasoning pipeline adds two layers:

### Quick Summaries (all hypotheses)
A single Claude call batches all hypotheses and generates 2-3 sentence explanations of why each A-B-C connection is scientifically interesting.

### Full Research Briefs (top N hypotheses)
For the highest-scoring hypotheses, Claude produces a structured ~500-word brief:

- **Connection Explanation.** Why the intermediary B connects A to C, and what the biological mechanism might be.
- **Literature Evidence.** What papers say about the A-B and B-C links, with citations.
- **Existing Knowledge Comparison.** How this compares to known treatments or connections.
- **Confidence Assessment.** Structured ratings (strong/moderate/weak) across four dimensions: graph evidence, literature support, biological plausibility, and novelty.
- **Suggested Validation.** What experiments or computational analyses would test the hypothesis.

## Structured Confidence Assessment

Each hypothesis gets a multi-dimensional confidence breakdown rather than a single score:

| Dimension | What it measures |
|-----------|-----------------|
| Graph Evidence | Path count, relationship weights, whether intermediary nodes are well-studied |
| Literature Support | Number of relevant triples, recency of papers, extraction confidence |
| Biological Plausibility | Whether the proposed mechanism makes biological sense (Claude assessment) |
| Novelty | Whether this is genuinely unknown or a well-known connection |
| Path Redundancy | Multiple independent paths (different B nodes) connecting A to C increases confidence |

## Ground Truth Validation

To measure whether Nexus actually works, it is benchmarked against 50+ known biological discoveries:

1. Curate known discoveries where the A-C connection was non-obvious at the time
2. Remove the direct A-C edge from the graph
3. Run the Nexus pipeline and check if C appears in the results
4. Compute standard retrieval metrics: Recall@K, Mean Reciprocal Rank, Precision@K

This provides a concrete, repeatable quality signal for all pipeline improvements.

## Autonomous Validation Loop

Beyond the initial pipeline, Nexus includes a fully autonomous validation loop where a Claude agent selects and runs computational validation tools on its own:

- **7 MCP Tools.** Literature validation, compound lookup, pathway overlap analysis, protein interaction queries, expression correlation, molecular docking, and experimental protocol generation.
- **Agent Harness.** Manages validation sessions with event logging, budget enforcement (tool call caps, token limits), and timeout controls.
- **Monitoring UI.** Real-time SSE streaming of the agent's actions to a monitoring dashboard, so researchers can observe the validation process as it happens.

The agent autonomously decides which tools to call, in what order, based on the hypothesis it's validating. It can chain results (e.g., look up a compound, check its binding profile, then run a docking simulation) without human intervention.

## Knowledge Graph

The knowledge graph is seeded from **Hetionet v1.0**, an integrative network of biology:

- **47,031 nodes** across 11 types: Disease, Gene, Compound, Anatomy, BiologicalProcess, CellularComponent, MolecularFunction, Pathway, PharmacologicClass, SideEffect, Symptom
- **2,250,197 edges** across 24 relationship types encoding associations, bindings, treatments, regulations, and more

New edges are continuously added as the literature agent extracts triples from papers. Each edge carries evidence counts, confidence scores, source paper references, and a novelty flag.

## Data Model

**Neo4j** stores the knowledge graph (nodes, edges, graph traversal).

**Supabase (Postgres)** stores relational data:
- User profiles and authentication
- Credit balances and transactions
- Research job queue and status
- Ranked hypotheses with ABC paths and evidence chains
- Discovery Feed entries
- Disease-area subscriptions
- Enterprise API key management

Row-level security ensures users only see their own data, while the Discovery Feed is publicly readable.

## API Surface

```
POST /api/query           Submit a research question
GET  /api/jobs/{id}       Poll job status + results (SSE for real-time)
GET  /api/feed            Discovery feed (paginated, filterable by disease)
GET  /api/graph/explore   Interactive graph query
GET  /api/hypotheses/{id} Full hypothesis detail + evidence chain
POST /api/subscribe       Subscribe to disease area alerts
GET  /api/credits         Credit balance
POST /api/validate        Trigger computational validation on a hypothesis
```

## Frontend

### Pages
1. **Landing.** Live stats, sample discovery cards, sign up.
2. **Query Builder.** Disease autocomplete, free-form input, advanced filters.
3. **Discovery Feed.** Scrollable feed of autonomous discoveries, subscribe per disease.
4. **Graph Explorer.** Interactive Neo4j visualization with clickable nodes and highlighted ABC paths.
5. **Hypothesis Detail.** Evidence chain with citations, ABC path visualization, validation results, confidence breakdown, export and share.
6. **Dashboard.** Credits, query history, subscriptions, API keys.

### Design Language
Light, clean, medical aesthetic. White/off-white backgrounds, slate text, teal accents.

### Tech Stack
Next.js 14+ (App Router), Tailwind CSS, shadcn/ui, react-force-graph-2d for graph visualization, Supabase client for auth and real-time updates, TanStack Query for data fetching.

## External Services

| Service | Purpose |
|---------|---------|
| PaperQA2 | Literature RAG engine for paper search and evidence extraction |
| NCBI E-utilities | PubMed paper search and retrieval |
| Semantic Scholar | Paper search, citation graphs, embeddings |
| Neo4j Aura | Knowledge graph hosting |
| Supabase | Postgres database, auth, real-time subscriptions |
| Tamarind Bio | Computational validation (AlphaFold, DiffDock, docking) |
| BioRender | Scientific figure generation |
| Redis (Upstash) | Job queue |

## Build Roadmap

```
Phase 1: Project Scaffolding + Data Layer
         Monorepo setup, Neo4j + Supabase connections, Hetionet seed

Phase 2: FastAPI Gateway
         REST endpoints, auth middleware, job queue, SSE streaming

Phase 3: Swanson ABC Engine
         Core traversal algorithm on Neo4j

Phase 4: Literature Agent
         PubMed/Semantic Scholar search, entity extraction, triple generation

Phase 5: Pipeline Orchestrator
         Claude Agent SDK chaining: Literature -> Graph -> Validation -> Viz

Phase 6: Heartbeat Engine
         Autonomous paper ingestion, delta detection, scheduled ABC sweeps

Phase 7: Frontend
         All six pages with graph visualization and real-time updates

Phase 8: Integration + Deployment
         End-to-end testing, Vercel frontend, containerized backend
```

### Phase Dependencies

```
Phase 1 ──┬── Phase 2 (API)
           ├── Phase 3 (ABC Engine)
           └── Phase 7.1-7.2 (Layout + Auth)

Phase 3 ──── Phase 4 (Literature Agent)

Phase 4 ──── Phase 5 (Pipeline Orchestrator)

Phase 5 ──┬── Phase 6 (Heartbeat)
           └── Phase 7.3-7.7 (Frontend Pages)

Phase 6 + 7 ── Phase 8 (Integration + Deploy)
```

### v2 Additions (post-launch)

- Generalized multi-type ABC discovery across all 11 node types
- Claude reasoning pipeline (quick summaries + full research briefs)
- Ground truth validation suite (50+ curated known discoveries)
- Structured multi-dimensional confidence assessment
- Autonomous validation loop with 7 MCP tools and agent harness
- Real-time validation monitoring UI

## Cost Model

User-funded credits. Each query deducts credits based on the pipeline steps executed. The heartbeat engine is funded from a community pool or operational budget. Enterprise customers get custom billing and unlimited queries.
