# Nexus Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an autonomous biological discovery platform with adaptive checkpoints, computational validation, cloud lab integration, and a persistent learning system.

**Architecture:** Python monorepo. FastAPI backend with async Neo4j (Hetionet-seeded knowledge graph) + Supabase (relational). Multi-agent pipeline: Literature -> Graph (ABC) -> Reasoning -> Validation -> Viz -> Protocol, with checkpoint agents at each stage that can pivot or branch investigations. Learning system accumulates heuristics in .md files. Next.js frontend with real-time SSE monitoring.

**Tech Stack:** Python 3.12, FastAPI, Anthropic SDK, PaperQA2, Neo4j async driver, Supabase, httpx, Next.js 14+, Tailwind CSS, shadcn/ui, react-force-graph-2d

**Design Doc:** `docs/plans/2026-03-08-nexus-design.md`

**API Reference Docs:** Copy from `../biological_research_auto/docs/api-docs/` into `docs/api-docs/`

---

## Verification

After every task, run:
```bash
cd /Users/dannyliu/personal_projects/nexus && .venv/bin/pytest tests/ -v
cd /Users/dannyliu/personal_projects/nexus && .venv/bin/ruff check backend/ tests/
```

---

## Phase 1: Scaffolding + Data Layer

**Objective:** Monorepo structure, all dependencies, Neo4j + Supabase connections, Hetionet seed.

**Checkpoint:** `pytest tests/ -v` passes, Neo4j client connects, Supabase tables exist.

---

### Task 1.1: Initialize Monorepo

**Files:**
- Create: `pyproject.toml`
- Create: `backend/src/nexus/__init__.py`
- Create: `backend/src/nexus/config.py`
- Create: `.env.example`
- Create: `.env` (from user-provided keys, gitignored)

**Step 1: Create pyproject.toml**

```toml
[project]
name = "nexus"
version = "0.1.0"
description = "Autonomous Biological Discovery Platform"
requires-python = ">=3.12"
dependencies = [
	"fastapi>=0.115.0",
	"uvicorn[standard]>=0.30.0",
	"httpx>=0.27.0",
	"pydantic>=2.0",
	"pydantic-settings>=2.0",
	"neo4j>=5.0",
	"supabase>=2.0",
	"anthropic>=0.40",
	"paper-qa>=5",
]

[project.optional-dependencies]
dev = [
	"pytest>=8.0",
	"pytest-asyncio>=0.24",
	"pytest-httpx>=0.30",
	"ruff>=0.6",
	"mypy>=1.11",
]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.setuptools.packages.find]
where = ["backend/src"]

[tool.ruff]
line-length = 120

[tool.ruff.format]
quote-style = "double"
indent-style = "tab"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.12"
strict = true
```

**Step 2: Create config module**

```python
# backend/src/nexus/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
	app_name: str = "Nexus"
	debug: bool = False

	# Anthropic
	anthropic_api_key: str = ""

	# NCBI
	ncbi_api_key: str = ""

	# Semantic Scholar
	semantic_scholar_api_key: str = ""

	# Neo4j
	neo4j_uri: str = ""
	neo4j_username: str = ""
	neo4j_password: str = ""

	# Supabase
	supabase_url: str = ""
	supabase_anon_key: str = ""
	supabase_service_role_key: str = ""

	# Tamarind Bio
	tamarind_bio_api_key: str = ""

	# BioRender
	biorender_api_key: str = ""

	# Strateos (CloudLab)
	strateos_email: str = ""
	strateos_token: str = ""
	strateos_organization_id: str = ""

	# Vercel
	vercel_token: str = ""

	model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Step 3: Create .env.example** (no real keys)

```
ANTHROPIC_API_KEY=
NCBI_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
NEO4J_URI=
NEO4J_USERNAME=
NEO4J_PASSWORD=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
TAMARIND_BIO_API_KEY=
BIORENDER_API_KEY=
STRATEOS_EMAIL=
STRATEOS_TOKEN=
STRATEOS_ORGANIZATION_ID=
VERCEL_TOKEN=
```

**Step 4: Create .env** with the user's actual API keys (already provided in conversation). This file is gitignored.

**Step 5: Create empty __init__.py**

```python
# backend/src/nexus/__init__.py
```

**Step 6: Create virtual environment and install**

Run: `cd /Users/dannyliu/personal_projects/nexus && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`

**Step 7: Verify install**

Run: `.venv/bin/python -c "import nexus; print('OK')"`
Expected: `OK`

**Step 8: Commit**

```bash
git add pyproject.toml backend/ .env.example .gitignore
git commit -m "feat: initialize nexus monorepo with config and dependencies"
```

---

### Task 1.2: Neo4j Client

**Files:**
- Create: `backend/src/nexus/graph/__init__.py`
- Create: `backend/src/nexus/graph/client.py`
- Test: `tests/graph/test_client.py`

**Step 1: Write failing test**

```python
# tests/graph/test_client.py
import pytest

from nexus.graph.client import GraphClient


def test_graph_client_not_connected():
	c = GraphClient()
	with pytest.raises(RuntimeError, match="not connected"):
		_ = c.driver


def test_graph_client_init():
	c = GraphClient()
	assert c._driver is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/graph/test_client.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement Neo4j client**

```python
# backend/src/nexus/graph/client.py
from neo4j import AsyncGraphDatabase, AsyncDriver

from nexus.config import settings


class GraphClient:
	"""Async Neo4j client for the Nexus knowledge graph."""

	def __init__(self) -> None:
		self._driver: AsyncDriver | None = None

	async def connect(self) -> None:
		self._driver = AsyncGraphDatabase.driver(
			settings.neo4j_uri,
			auth=(settings.neo4j_username, settings.neo4j_password),
		)

	async def close(self) -> None:
		if self._driver:
			await self._driver.close()

	@property
	def driver(self) -> AsyncDriver:
		if not self._driver:
			raise RuntimeError("GraphClient not connected. Call connect() first.")
		return self._driver

	async def execute_read(self, query: str, **params) -> list[dict]:
		async with self.driver.session() as session:
			result = await session.run(query, params)
			return [dict(record) for record in await result.data()]

	async def execute_write(self, query: str, **params) -> list[dict]:
		async with self.driver.session() as session:
			result = await session.run(query, params)
			return [dict(record) for record in await result.data()]

	async def node_count(self) -> int:
		result = await self.execute_read("MATCH (n) RETURN count(n) AS count")
		return result[0]["count"]

	async def edge_count(self) -> int:
		result = await self.execute_read("MATCH ()-[r]->() RETURN count(r) AS count")
		return result[0]["count"]


graph_client = GraphClient()
```

**Step 4: Create `__init__.py`**

```python
# backend/src/nexus/graph/__init__.py
```

**Step 5: Create `tests/__init__.py` and `tests/graph/__init__.py`**

**Step 6: Run tests**

Run: `.venv/bin/pytest tests/graph/test_client.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add backend/src/nexus/graph/ tests/
git commit -m "feat: add async Neo4j client"
```

---

### Task 1.3: Hetionet Seed Script

**Files:**
- Create: `backend/src/nexus/graph/seed.py`
- Create: `scripts/seed_hetionet.py`
- Test: `tests/graph/test_seed.py`

**Step 1: Write test for metaedge parsing**

```python
# tests/graph/test_seed.py
from nexus.graph.seed import parse_metaedge


def test_parse_metaedge_compound_binds_gene():
	source, rel, target = parse_metaedge("Compound - binds - Gene > CbG")
	assert source == "Compound"
	assert "BINDS" in rel.upper()
	assert target == "Gene"


def test_parse_metaedge_disease_associates_gene():
	source, rel, target = parse_metaedge("Disease - associates - Gene > DaG")
	assert source == "Disease"
	assert "ASSOCIATES" in rel.upper()
	assert target == "Gene"
```

**Step 2: Implement seed module**

Reference: `docs/api-docs/hetionet.md` for data format.

```python
# backend/src/nexus/graph/seed.py
"""Seed Neo4j with Hetionet v1.0 knowledge graph.

Hetionet: 47,031 nodes (11 types), 2,250,197 edges (24 types).
Download: https://github.com/hetio/hetionet/tree/master/hetnet/json
"""
import json
from pathlib import Path

from nexus.graph.client import graph_client


HETIONET_DIR = Path(__file__).parent.parent.parent.parent / "data" / "hetionet"


def parse_metaedge(metaedge: str) -> tuple[str, str, str]:
	"""Parse hetionet metaedge like 'Compound - binds - Gene > CbG'."""
	parts = metaedge.split(" - ")
	source_label = parts[0].strip()
	target_and_abbrev = parts[-1].strip()

	if ">" in target_and_abbrev:
		target_part, abbrev = target_and_abbrev.rsplit(">", 1)
		target_label = target_part.strip()
		abbrev = abbrev.strip()
	else:
		target_label = target_and_abbrev
		abbrev = ""

	verb = parts[1].strip() if len(parts) > 2 else "RELATES_TO"
	rel_type = f"{verb.upper().replace(' ', '_')}_{abbrev}" if abbrev else verb.upper().replace(" ", "_")

	return source_label, rel_type, target_label


async def seed_nodes(nodes_path: Path) -> int:
	"""Load all nodes from hetionet JSON into Neo4j."""
	with open(nodes_path) as f:
		data = json.load(f)

	count = 0
	for node in data:
		label = node["kind"]
		props = {
			"identifier": node["identifier"],
			"name": node["data"].get("name", str(node["identifier"])),
			"source": node["data"].get("source", "hetionet"),
		}
		for key, value in node["data"].items():
			if key not in ("name", "source") and isinstance(value, (str, int, float, bool)):
				props[key] = value

		query = f"MERGE (n:{label} {{identifier: $identifier}}) SET n += $props"
		await graph_client.execute_write(query, identifier=props["identifier"], props=props)
		count += 1

	return count


async def seed_edges(edges_path: Path) -> int:
	"""Load all edges from hetionet JSON into Neo4j."""
	with open(edges_path) as f:
		data = json.load(f)

	count = 0
	for edge in data:
		source_label, rel_type, target_label = parse_metaedge(edge["kind"])
		source_id = edge["source_id"][1]
		target_id = edge["target_id"][1]

		query = (
			f"MATCH (a:{source_label} {{identifier: $source_id}}) "
			f"MATCH (b:{target_label} {{identifier: $target_id}}) "
			f"MERGE (a)-[r:{rel_type}]->(b) "
			f"SET r.source = 'hetionet', r.is_novel = false"
		)
		await graph_client.execute_write(query, source_id=source_id, target_id=target_id)
		count += 1

	return count


async def seed_all() -> dict:
	"""Run full Hetionet seed."""
	await graph_client.connect()

	nodes_path = HETIONET_DIR / "nodes.json"
	edges_path = HETIONET_DIR / "edges.json"

	if not nodes_path.exists():
		raise FileNotFoundError(
			f"Hetionet data not found at {HETIONET_DIR}. "
			"Download from https://github.com/hetio/hetionet/tree/master/hetnet/json"
		)

	node_count = await seed_nodes(nodes_path)
	edge_count = await seed_edges(edges_path)
	await graph_client.close()

	return {"nodes_loaded": node_count, "edges_loaded": edge_count}
```

**Step 3: Create runner script**

```python
# scripts/seed_hetionet.py
"""Run: .venv/bin/python scripts/seed_hetionet.py"""
import asyncio

from nexus.graph.seed import seed_all


async def main():
	result = await seed_all()
	print(f"Seeded: {result['nodes_loaded']} nodes, {result['edges_loaded']} edges")


if __name__ == "__main__":
	asyncio.run(main())
```

**Step 4: Run tests and commit**

Run: `.venv/bin/pytest tests/graph/ -v`

```bash
git add backend/src/nexus/graph/seed.py scripts/ tests/graph/test_seed.py
git commit -m "feat: add Hetionet seed script with metaedge parser"
```

---

### Task 1.4: Supabase Schema + Client

**Files:**
- Create: `backend/src/nexus/db/__init__.py`
- Create: `backend/src/nexus/db/client.py`
- Create: `backend/src/nexus/db/models.py`
- Create: `backend/src/nexus/db/migrations/001_initial.sql`
- Test: `tests/db/test_models.py`

**Step 1: Write SQL migration**

```sql
-- backend/src/nexus/db/migrations/001_initial.sql

-- Profiles (extends Supabase auth.users)
create table if not exists public.profiles (
	id uuid references auth.users on delete cascade primary key,
	display_name text,
	tier text not null default 'free' check (tier in ('free', 'pro', 'enterprise')),
	credits_balance integer not null default 0,
	created_at timestamptz not null default now(),
	updated_at timestamptz not null default now()
);

-- Research sessions
create table if not exists public.sessions (
	id uuid primary key default gen_random_uuid(),
	user_id uuid references public.profiles on delete cascade,
	query text not null,
	status text not null default 'running' check (status in ('running', 'completed', 'failed')),
	pipeline_step text default 'literature',
	pivot_count integer not null default 0,
	branch_count integer not null default 0,
	config jsonb not null default '{}',
	result jsonb,
	created_at timestamptz not null default now(),
	completed_at timestamptz
);

-- Hypotheses
create table if not exists public.hypotheses (
	id uuid primary key default gen_random_uuid(),
	session_id uuid references public.sessions on delete cascade not null,
	title text not null,
	description text not null,
	disease_area text,
	hypothesis_type text not null default 'mechanism',
	novelty_score float not null default 0,
	evidence_score float not null default 0,
	validation_score float,
	overall_score float not null default 0,
	abc_path jsonb not null,
	evidence_chain jsonb not null default '[]',
	research_brief jsonb,
	validation_result jsonb,
	visualization_url text,
	is_public boolean not null default false,
	created_at timestamptz not null default now()
);

-- Discovery feed
create table if not exists public.feed_entries (
	id uuid primary key default gen_random_uuid(),
	hypothesis_id uuid references public.hypotheses on delete cascade not null,
	disease_area text not null,
	published_at timestamptz not null default now()
);

-- Disease subscriptions
create table if not exists public.subscriptions (
	id uuid primary key default gen_random_uuid(),
	user_id uuid references public.profiles on delete cascade not null,
	disease_area text not null,
	created_at timestamptz not null default now(),
	unique (user_id, disease_area)
);

-- CloudLab experiments
create table if not exists public.experiments (
	id uuid primary key default gen_random_uuid(),
	hypothesis_id uuid references public.hypotheses on delete cascade not null,
	provider text not null default 'strateos',
	protocol jsonb not null,
	status text not null default 'pending' check (status in ('pending', 'submitted', 'running', 'completed', 'failed')),
	result jsonb,
	submitted_at timestamptz,
	completed_at timestamptz,
	created_at timestamptz not null default now()
);

-- Session events (for SSE streaming)
create table if not exists public.session_events (
	id uuid primary key default gen_random_uuid(),
	session_id uuid references public.sessions on delete cascade not null,
	event_type text not null,
	hypothesis_id uuid,
	tool_name text,
	input_data jsonb,
	output_data jsonb,
	confidence_snapshot float,
	created_at timestamptz not null default now()
);

-- API keys (enterprise)
create table if not exists public.api_keys (
	id uuid primary key default gen_random_uuid(),
	user_id uuid references public.profiles on delete cascade not null,
	key_hash text not null unique,
	name text not null,
	is_active boolean not null default true,
	created_at timestamptz not null default now(),
	last_used_at timestamptz
);

-- Enable RLS
alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.hypotheses enable row level security;
alter table public.feed_entries enable row level security;
alter table public.subscriptions enable row level security;
alter table public.experiments enable row level security;
alter table public.session_events enable row level security;
alter table public.api_keys enable row level security;

-- RLS policies
create policy "Users can view own profile" on public.profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on public.profiles for update using (auth.uid() = id);
create policy "Users can view own sessions" on public.sessions for select using (auth.uid() = user_id);
create policy "Users can create sessions" on public.sessions for insert with check (auth.uid() = user_id);
create policy "Users can view own hypotheses" on public.hypotheses for select using (
	session_id in (select id from public.sessions where user_id = auth.uid()) or is_public = true
);
create policy "Anyone can view public feed" on public.feed_entries for select using (true);
create policy "Users can manage own subscriptions" on public.subscriptions for all using (auth.uid() = user_id);
create policy "Users can view own experiments" on public.experiments for select using (
	hypothesis_id in (
		select h.id from public.hypotheses h
		join public.sessions s on h.session_id = s.id
		where s.user_id = auth.uid()
	)
);
create policy "Users can view own events" on public.session_events for select using (
	session_id in (select id from public.sessions where user_id = auth.uid())
);
create policy "Users can manage own api keys" on public.api_keys for all using (auth.uid() = user_id);

-- Indexes
create index idx_sessions_user_id on public.sessions(user_id);
create index idx_sessions_status on public.sessions(status);
create index idx_hypotheses_session_id on public.hypotheses(session_id);
create index idx_hypotheses_disease_area on public.hypotheses(disease_area);
create index idx_hypotheses_overall_score on public.hypotheses(overall_score desc);
create index idx_feed_entries_disease on public.feed_entries(disease_area);
create index idx_feed_entries_published on public.feed_entries(published_at desc);
create index idx_experiments_hypothesis on public.experiments(hypothesis_id);
create index idx_session_events_session on public.session_events(session_id);
create index idx_session_events_created on public.session_events(created_at);
```

**Step 2: Write Supabase client**

```python
# backend/src/nexus/db/client.py
from supabase import create_client, Client

from nexus.config import settings


def get_supabase_client() -> Client:
	return create_client(settings.supabase_url, settings.supabase_service_role_key)


supabase: Client | None = get_supabase_client() if settings.supabase_url else None
```

**Step 3: Write Pydantic models**

```python
# backend/src/nexus/db/models.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ABCPath(BaseModel):
	a: dict  # {id, name, type}
	b: dict  # {id, name, type}
	c: dict  # {id, name, type}


class EvidenceItem(BaseModel):
	paper_id: str
	title: str
	snippet: str
	confidence: float


class ConfidenceAssessment(BaseModel):
	graph_evidence: str = "moderate"
	graph_reasoning: str = ""
	literature_support: str = "moderate"
	literature_reasoning: str = ""
	biological_plausibility: str = "moderate"
	plausibility_reasoning: str = ""
	novelty: str = "medium"
	novelty_reasoning: str = ""


class ResearchBrief(BaseModel):
	hypothesis_title: str = ""
	connection_explanation: str = ""
	literature_evidence: str = ""
	existing_knowledge_comparison: str = ""
	confidence: ConfidenceAssessment = ConfidenceAssessment()
	suggested_validation: str = ""


class Hypothesis(BaseModel):
	id: UUID
	session_id: UUID
	title: str
	description: str
	disease_area: str | None
	hypothesis_type: str
	novelty_score: float
	evidence_score: float
	validation_score: float | None
	overall_score: float
	abc_path: ABCPath
	evidence_chain: list[EvidenceItem]
	research_brief: ResearchBrief | None
	validation_result: dict | None
	visualization_url: str | None
	is_public: bool
	created_at: datetime


class SessionRequest(BaseModel):
	query: str
	disease_area: str | None = None
	start_entity: str | None = None
	start_type: str | None = None
	target_types: list[str] | None = None
	max_hypotheses: int = 10
	reasoning_depth: str = "quick"
	max_pivots: int = 3
	max_hops: int = 2


class SessionStatus(BaseModel):
	id: UUID
	status: str
	pipeline_step: str | None
	pivot_count: int
	branch_count: int


class FeedEntry(BaseModel):
	id: UUID
	hypothesis_id: UUID
	disease_area: str
	published_at: datetime


class ExperimentRequest(BaseModel):
	hypothesis_id: UUID
	provider: str = "strateos"


class ExperimentStatus(BaseModel):
	id: UUID
	hypothesis_id: UUID
	provider: str
	status: str
	result: dict | None
```

**Step 4: Write model tests**

```python
# tests/db/test_models.py
from nexus.db.models import SessionRequest, ABCPath, Hypothesis, ConfidenceAssessment
from uuid import uuid4
from datetime import datetime


def test_session_request_defaults():
	req = SessionRequest(query="What mechanisms drive Parkinson's disease?")
	assert req.max_pivots == 3
	assert req.max_hops == 2
	assert req.reasoning_depth == "quick"
	assert req.target_types is None


def test_abc_path():
	path = ABCPath(
		a={"id": "1", "name": "Parkinson's", "type": "Disease"},
		b={"id": "2", "name": "LRRK2", "type": "Gene"},
		c={"id": "3", "name": "Ibuprofen", "type": "Compound"},
	)
	assert path.a["name"] == "Parkinson's"
	assert path.c["type"] == "Compound"


def test_confidence_assessment_defaults():
	ca = ConfidenceAssessment()
	assert ca.graph_evidence == "moderate"
	assert ca.novelty == "medium"
```

**Step 5: Run tests and commit**

Run: `.venv/bin/pytest tests/ -v`

```bash
git add backend/src/nexus/db/ tests/db/
git commit -m "feat: add Supabase schema, client, and Pydantic models"
```

---

### Task 1.5: Copy API Reference Docs

**Step 1:** Copy API docs from the existing project for reference.

Run: `cp -r /Users/dannyliu/personal_projects/biological_research_auto/docs/api-docs /Users/dannyliu/personal_projects/nexus/docs/api-docs`

**Step 2: Commit**

```bash
git add docs/api-docs/
git commit -m "docs: add API reference docs for external services"
```

---

## Phase 2: Core ABC Engine

**Objective:** Implement generalized Swanson ABC traversal on Neo4j. Any source type, any target type.

**Checkpoint:** `pytest tests/graph/test_abc.py -v` passes with mock data.

---

### Task 2.1: ABC Dataclasses + Relationship Weights

**Files:**
- Modify: `backend/src/nexus/graph/abc.py`
- Test: `tests/graph/test_abc.py`

**Step 1: Write failing test**

```python
# tests/graph/test_abc.py
import pytest
from unittest.mock import patch, AsyncMock

from nexus.graph.abc import ABCHypothesis, compute_novelty, rel_weight


def test_abc_hypothesis_dataclass():
	h = ABCHypothesis(
		a_id="D1", a_name="Parkinson disease", a_type="Disease",
		b_id="G1", b_name="LRRK2", b_type="Gene",
		c_id="C1", c_name="Ibuprofen", c_type="Compound",
		ab_relationship="ASSOCIATES_DaG", bc_relationship="BINDS_CbG",
		path_count=5, novelty_score=0.95, path_strength=0.7,
		intermediaries=[],
	)
	assert h.a_name == "Parkinson disease"
	assert h.c_type == "Compound"


def test_compute_novelty():
	assert compute_novelty(1) == 0.9
	assert compute_novelty(4) == 0.95
	assert compute_novelty(25) == 0.4


def test_rel_weight_known():
	assert rel_weight("TREATS_CtD") == 1.0
	assert rel_weight("BINDS_CbG") == 0.9


def test_rel_weight_unknown():
	assert rel_weight("UNKNOWN_REL") == 0.5
```

**Step 2: Implement**

```python
# backend/src/nexus/graph/abc.py
"""Swanson ABC Literature-Based Discovery on Neo4j.

The ABC model: If A relates to B in one context, and B relates to C in another,
then A-C may be a novel, undiscovered connection worth investigating.

Generalized: any source type -> any intermediary -> any target type.
"""
import math
from dataclasses import dataclass, field

from nexus.graph.client import graph_client


RELATIONSHIP_WEIGHTS: dict[str, float] = {
	"TREATS_CtD": 1.0,
	"BINDS_CbG": 0.9,
	"ASSOCIATES_DaG": 0.85,
	"UPREGULATES_DuG": 0.7,
	"DOWNREGULATES_DdG": 0.7,
	"UPREGULATES_AuG": 0.7,
	"DOWNREGULATES_AdG": 0.7,
	"PALLIATES_CpD": 0.8,
	"CAUSES_CcSE": 0.75,
	"PRESENTS_DpS": 0.6,
	"LOCALIZES_DlA": 0.65,
	"RESEMBLES_DrD": 0.5,
	"INTERACTS_GiG": 0.8,
	"REGULATES_GrG": 0.75,
	"COVARIES_GcG": 0.6,
	"PARTICIPATES_GpBP": 0.7,
	"PARTICIPATES_GpCC": 0.6,
	"PARTICIPATES_GpMF": 0.65,
	"PARTICIPATES_GpPW": 0.7,
	"EXPRESSES_AeG": 0.65,
	"INCLUDES_PCiC": 0.5,
}


def rel_weight(rel_type: str) -> float:
	"""Get weight for a relationship type."""
	return RELATIONSHIP_WEIGHTS.get(rel_type, 0.5)


def compute_novelty(path_count: int) -> float:
	"""Score novelty based on intermediary path count.

	Sweet spot: 3-5 paths = enough evidence, still novel.
	"""
	if path_count <= 2:
		return 0.9
	elif path_count <= 5:
		return 0.95
	elif path_count <= 10:
		return 0.8
	elif path_count <= 20:
		return 0.6
	else:
		return 0.4


@dataclass
class ABCHypothesis:
	a_id: str
	a_name: str
	a_type: str
	b_id: str
	b_name: str
	b_type: str
	c_id: str
	c_name: str
	c_type: str
	ab_relationship: str
	bc_relationship: str
	path_count: int
	novelty_score: float
	path_strength: float = 0.0
	intermediaries: list[dict] = field(default_factory=list)
```

**Step 3: Run tests**

Run: `.venv/bin/pytest tests/graph/test_abc.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/src/nexus/graph/abc.py tests/graph/test_abc.py
git commit -m "feat: add ABC hypothesis dataclass and relationship weights"
```

---

### Task 2.2: Generalized ABC Traversal

**Files:**
- Modify: `backend/src/nexus/graph/abc.py`
- Test: `tests/graph/test_abc.py`

**Step 1: Write failing tests for ABC traversal**

Add to `tests/graph/test_abc.py`:

```python
@pytest.mark.asyncio
async def test_find_abc_hypotheses_disease_to_compound():
	mock_results = [
		{
			"a_name": "Parkinson disease", "a_id": "DOID:14330", "a_type": "Disease",
			"c_name": "Ibuprofen", "c_id": "DB01050", "c_type": "Compound",
			"intermediaries": [{"identifier": "G1", "name": "LRRK2", "type": "Gene"}],
			"ab_rels": ["ASSOCIATES_DaG"], "bc_rels": ["BINDS_CbG"],
			"path_count": 5,
		},
	]

	with patch("nexus.graph.abc.graph_client") as mock_graph:
		mock_graph.execute_read = AsyncMock(return_value=mock_results)
		results = await find_abc_hypotheses(
			source_name="Parkinson disease",
			source_type="Disease",
			target_type="Compound",
		)
		assert len(results) == 1
		assert results[0].a_type == "Disease"
		assert results[0].c_type == "Compound"
		assert results[0].path_strength > 0


@pytest.mark.asyncio
async def test_find_abc_hypotheses_gene_source():
	mock_results = [
		{
			"a_name": "BRCA1", "a_id": "1100", "a_type": "Gene",
			"c_name": "ovarian cancer", "c_id": "DOID:2394", "c_type": "Disease",
			"intermediaries": [{"identifier": "BP1", "name": "DNA repair", "type": "BiologicalProcess"}],
			"ab_rels": ["PARTICIPATES_GpBP"], "bc_rels": ["ASSOCIATES_DaG"],
			"path_count": 4,
		},
	]

	with patch("nexus.graph.abc.graph_client") as mock_graph:
		mock_graph.execute_read = AsyncMock(return_value=mock_results)
		results = await find_abc_hypotheses(
			source_name="BRCA1",
			source_type="Gene",
			target_type="Disease",
		)
		assert len(results) == 1
		assert results[0].a_type == "Gene"
```

**Step 2: Implement find_abc_hypotheses**

Add to `backend/src/nexus/graph/abc.py`:

```python
async def find_abc_hypotheses(
	source_name: str,
	source_type: str = "Disease",
	target_type: str = "Compound",
	max_results: int = 20,
	exclude_known: bool = True,
) -> list[ABCHypothesis]:
	"""Find novel A-B-C connections starting from any entity type."""
	exclusion_clause = "AND NOT (a)--(c)" if exclude_known else ""

	query = f"""
	MATCH (a:{source_type} {{name: $source_name}})-[r1]-(b)-[r2]-(c:{target_type})
	WHERE a <> c AND b <> c AND b <> a
	{exclusion_clause}
	WITH a, c, collect(DISTINCT b) AS intermediaries,
		collect(DISTINCT type(r1)) AS ab_rels,
		collect(DISTINCT type(r2)) AS bc_rels,
		count(DISTINCT b) AS path_count
	RETURN
		a.name AS a_name, a.identifier AS a_id,
		labels(a)[0] AS a_type,
		c.name AS c_name, c.identifier AS c_id,
		labels(c)[0] AS c_type,
		intermediaries, ab_rels, bc_rels, path_count
	ORDER BY path_count DESC
	LIMIT $max_results
	"""

	results = await graph_client.execute_read(
		query, source_name=source_name, max_results=max_results,
	)

	hypotheses = []
	for row in results:
		if not row["intermediaries"]:
			continue

		ab_rels = row["ab_rels"]
		bc_rels = row["bc_rels"]

		all_intermediaries: list[dict] = []
		best_b = None
		best_strength = -1.0

		for intermediary in row["intermediaries"]:
			b_type = intermediary.get("type", "Unknown") if isinstance(intermediary, dict) else "Unknown"
			b_id = str(intermediary.get("identifier", "")) if isinstance(intermediary, dict) else ""
			b_name = intermediary.get("name", "") if isinstance(intermediary, dict) else str(intermediary)

			ab_rel = ab_rels[0] if ab_rels else ""
			bc_rel = bc_rels[0] if bc_rels else ""
			strength = math.sqrt(rel_weight(ab_rel) * rel_weight(bc_rel))

			b_info = {
				"b_id": b_id, "b_name": b_name, "b_type": b_type,
				"ab_relationship": ab_rel, "bc_relationship": bc_rel,
				"path_strength": round(strength, 4),
			}
			all_intermediaries.append(b_info)

			if strength > best_strength:
				best_strength = strength
				best_b = b_info

		if not best_b:
			continue

		hypotheses.append(ABCHypothesis(
			a_id=str(row["a_id"]),
			a_name=row["a_name"],
			a_type=row.get("a_type", source_type),
			b_id=best_b["b_id"],
			b_name=best_b["b_name"],
			b_type=best_b["b_type"],
			c_id=str(row["c_id"]),
			c_name=row["c_name"],
			c_type=row["c_type"],
			ab_relationship=best_b["ab_relationship"],
			bc_relationship=best_b["bc_relationship"],
			path_count=row["path_count"],
			novelty_score=compute_novelty(row["path_count"]),
			path_strength=best_b["path_strength"],
			intermediaries=all_intermediaries,
		))

	return hypotheses


async def find_drug_repurposing_candidates(disease_name: str, max_results: int = 20) -> list[ABCHypothesis]:
	return await find_abc_hypotheses(source_name=disease_name, source_type="Disease", target_type="Compound", max_results=max_results)


async def find_mechanism_hypotheses(disease_name: str, max_results: int = 20) -> list[ABCHypothesis]:
	return await find_abc_hypotheses(source_name=disease_name, source_type="Disease", target_type="BiologicalProcess", max_results=max_results)
```

**Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/graph/test_abc.py -v`

```bash
git add backend/src/nexus/graph/abc.py tests/graph/test_abc.py
git commit -m "feat: implement generalized Swanson ABC traversal"
```

---

## Phase 3: Literature Agent

**Objective:** Search PubMed + Semantic Scholar, extract entity-relationship triples via Claude.

**Checkpoint:** `pytest tests/agents/ -v` passes.

---

### Task 3.1: Paper Search Client

**Files:**
- Create: `backend/src/nexus/agents/__init__.py`
- Create: `backend/src/nexus/agents/literature/__init__.py`
- Create: `backend/src/nexus/agents/literature/search.py`
- Test: `tests/agents/test_search.py`

**Step 1: Write failing tests**

```python
# tests/agents/test_search.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from nexus.agents.literature.search import search_pubmed, search_semantic_scholar, Paper


@pytest.mark.asyncio
async def test_search_pubmed():
	mock_search_response = MagicMock()
	mock_search_response.status_code = 200
	mock_search_response.json.return_value = {
		"esearchresult": {"idlist": ["12345"]}
	}

	mock_fetch_response = MagicMock()
	mock_fetch_response.status_code = 200
	mock_fetch_response.text = """<?xml version="1.0"?>
	<PubmedArticleSet>
		<PubmedArticle>
			<MedlineCitation>
				<PMID>12345</PMID>
				<Article>
					<ArticleTitle>LRRK2 in Parkinson's</ArticleTitle>
					<Abstract><AbstractText>LRRK2 mutations cause PD.</AbstractText></Abstract>
				</Article>
			</MedlineCitation>
		</PubmedArticle>
	</PubmedArticleSet>"""

	with patch("nexus.agents.literature.search.httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client.get = AsyncMock(side_effect=[mock_search_response, mock_fetch_response])
		mock_client_cls.return_value = mock_client

		papers = await search_pubmed("LRRK2 Parkinson", max_results=5)
		assert len(papers) == 1
		assert papers[0].paper_id == "PMID:12345"


@pytest.mark.asyncio
async def test_search_semantic_scholar():
	mock_response = MagicMock()
	mock_response.status_code = 200
	mock_response.json.return_value = {
		"data": [{
			"paperId": "abc123",
			"title": "LRRK2 in Parkinson's",
			"abstract": "LRRK2 mutations cause PD.",
			"year": 2024,
			"citationCount": 50,
		}]
	}

	with patch("nexus.agents.literature.search.httpx.AsyncClient") as mock_client_cls:
		mock_client = AsyncMock()
		mock_client.__aenter__ = AsyncMock(return_value=mock_client)
		mock_client.__aexit__ = AsyncMock(return_value=False)
		mock_client.get = AsyncMock(return_value=mock_response)
		mock_client_cls.return_value = mock_client

		papers = await search_semantic_scholar("LRRK2 Parkinson", max_results=5)
		assert len(papers) == 1
		assert papers[0].paper_id == "S2:abc123"
```

**Step 2: Implement search module**

Reference: `docs/api-docs/ncbi-eutils.md` and `docs/api-docs/semantic-scholar.md`

```python
# backend/src/nexus/agents/literature/search.py
"""Paper search via PubMed (NCBI E-utilities) and Semantic Scholar."""
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from nexus.config import settings


@dataclass
class Paper:
	paper_id: str
	title: str
	abstract: str
	year: int | None = None
	citation_count: int | None = None
	source: str = "pubmed"


async def search_pubmed(query: str, max_results: int = 10) -> list[Paper]:
	"""Search PubMed via NCBI E-utilities."""
	async with httpx.AsyncClient(timeout=30.0) as client:
		# Step 1: ESearch to get PMIDs
		search_params = {
			"db": "pubmed",
			"term": query,
			"retmax": max_results,
			"retmode": "json",
			"sort": "relevance",
		}
		if settings.ncbi_api_key:
			search_params["api_key"] = settings.ncbi_api_key

		search_resp = await client.get(
			"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
			params=search_params,
		)
		search_resp.raise_for_status()
		pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])

		if not pmids:
			return []

		# Step 2: EFetch to get abstracts
		fetch_params = {
			"db": "pubmed",
			"id": ",".join(pmids),
			"rettype": "xml",
			"retmode": "xml",
		}
		if settings.ncbi_api_key:
			fetch_params["api_key"] = settings.ncbi_api_key

		fetch_resp = await client.get(
			"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
			params=fetch_params,
		)
		fetch_resp.raise_for_status()

		return _parse_pubmed_xml(fetch_resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[Paper]:
	"""Parse PubMed XML response into Paper objects."""
	papers = []
	try:
		root = ET.fromstring(xml_text)
		for article in root.findall(".//PubmedArticle"):
			pmid_el = article.find(".//PMID")
			title_el = article.find(".//ArticleTitle")
			abstract_el = article.find(".//AbstractText")

			if pmid_el is None or title_el is None:
				continue

			papers.append(Paper(
				paper_id=f"PMID:{pmid_el.text}",
				title=title_el.text or "",
				abstract=abstract_el.text or "" if abstract_el is not None else "",
				source="pubmed",
			))
	except ET.ParseError:
		pass

	return papers


async def search_semantic_scholar(query: str, max_results: int = 10) -> list[Paper]:
	"""Search Semantic Scholar API."""
	async with httpx.AsyncClient(timeout=30.0) as client:
		headers = {}
		if settings.semantic_scholar_api_key:
			headers["x-api-key"] = settings.semantic_scholar_api_key

		resp = await client.get(
			"https://api.semanticscholar.org/graph/v1/paper/search",
			params={
				"query": query,
				"limit": max_results,
				"fields": "title,abstract,year,citationCount",
			},
			headers=headers,
		)
		resp.raise_for_status()

		papers = []
		for item in resp.json().get("data", []):
			if not item.get("abstract"):
				continue
			papers.append(Paper(
				paper_id=f"S2:{item['paperId']}",
				title=item.get("title", ""),
				abstract=item.get("abstract", ""),
				year=item.get("year"),
				citation_count=item.get("citationCount"),
				source="semantic_scholar",
			))

		return papers


async def search_papers(query: str, max_results: int = 10) -> list[Paper]:
	"""Search both PubMed and Semantic Scholar, deduplicate by title."""
	pubmed_papers = await search_pubmed(query, max_results=max_results)
	s2_papers = await search_semantic_scholar(query, max_results=max_results)

	seen_titles = set()
	combined = []
	for paper in pubmed_papers + s2_papers:
		title_lower = paper.title.lower().strip()
		if title_lower not in seen_titles:
			seen_titles.add(title_lower)
			combined.append(paper)

	return combined[:max_results]
```

**Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/agents/test_search.py -v`

```bash
git add backend/src/nexus/agents/ tests/agents/
git commit -m "feat: add PubMed and Semantic Scholar search clients"
```

---

### Task 3.2: Triple Extraction via Claude

**Files:**
- Create: `backend/src/nexus/agents/literature/extract.py`
- Test: `tests/agents/test_extract.py`

**Step 1: Write failing test**

```python
# tests/agents/test_extract.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from nexus.agents.literature.extract import extract_triples, Triple
from nexus.agents.literature.search import Paper


@pytest.mark.asyncio
async def test_extract_triples():
	paper = Paper(
		paper_id="PMID:12345",
		title="LRRK2 in Parkinson's disease",
		abstract="LRRK2 mutations are associated with Parkinson's disease. LRRK2 binds GTP.",
	)

	mock_response = MagicMock()
	mock_response.content = [MagicMock(text='[{"subject": "LRRK2", "subject_type": "Gene", "predicate": "associated_with", "object": "Parkinson disease", "object_type": "Disease", "confidence": 0.95}]')]

	with patch("nexus.agents.literature.extract.anthropic") as mock_anthropic:
		mock_client = AsyncMock()
		mock_anthropic.AsyncAnthropic.return_value = mock_client
		mock_client.messages.create = AsyncMock(return_value=mock_response)

		triples = await extract_triples([paper])
		assert len(triples) == 1
		assert triples[0].subject == "LRRK2"
		assert triples[0].object == "Parkinson disease"
		assert triples[0].confidence == 0.95
```

**Step 2: Implement triple extraction**

```python
# backend/src/nexus/agents/literature/extract.py
"""Extract entity-relationship triples from papers using Claude."""
import json
from dataclasses import dataclass

import anthropic

from nexus.config import settings
from nexus.agents.literature.search import Paper


@dataclass
class Triple:
	subject: str
	subject_type: str
	predicate: str
	object: str
	object_type: str
	confidence: float
	source_paper_id: str = ""


EXTRACTION_PROMPT = """You are a biomedical NLP system. Extract entity-relationship triples from the following paper abstracts.

Entity types: Disease, Gene, Compound, Anatomy, BiologicalProcess, CellularComponent, MolecularFunction, Pathway, PharmacologicClass, SideEffect, Symptom

For each triple, provide:
- subject: entity name (use standard biomedical nomenclature)
- subject_type: one of the entity types above
- predicate: relationship verb (e.g., "associated_with", "binds", "upregulates", "treats", "causes")
- object: entity name
- object_type: one of the entity types above
- confidence: 0.0-1.0 based on how explicitly the paper states this relationship

Papers:
{papers_block}

Return ONLY a JSON array of triples. No markdown fences."""


async def extract_triples(papers: list[Paper]) -> list[Triple]:
	"""Extract entity-relationship triples from papers via Claude."""
	if not papers:
		return []

	if not settings.anthropic_api_key:
		return []

	papers_block = ""
	for p in papers:
		papers_block += f"\n[{p.paper_id}] {p.title}\n{p.abstract}\n"

	client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

	try:
		message = await client.messages.create(
			model="claude-sonnet-4-20250514",
			max_tokens=4000,
			messages=[{
				"role": "user",
				"content": EXTRACTION_PROMPT.format(papers_block=papers_block),
			}],
		)

		text = message.content[0].text.strip()
		if text.startswith("```"):
			text = text.split("\n", 1)[1] if "\n" in text else text[3:]
		if text.endswith("```"):
			text = text[:-3]
		text = text.strip()
		if text.startswith("json"):
			text = text[4:].strip()

		parsed = json.loads(text)
		triples = []
		for item in parsed:
			if not isinstance(item, dict):
				continue
			triples.append(Triple(
				subject=item.get("subject", ""),
				subject_type=item.get("subject_type", ""),
				predicate=item.get("predicate", ""),
				object=item.get("object", ""),
				object_type=item.get("object_type", ""),
				confidence=float(item.get("confidence", 0.5)),
				source_paper_id=item.get("source_paper_id", ""),
			))
		return triples

	except Exception:
		return []
```

**Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/agents/test_extract.py -v`

```bash
git add backend/src/nexus/agents/literature/extract.py tests/agents/test_extract.py
git commit -m "feat: add Claude-driven triple extraction from papers"
```

---

### Task 3.3: Literature Agent Orchestrator

**Files:**
- Create: `backend/src/nexus/agents/literature/agent.py`
- Test: `tests/agents/test_literature_agent.py`

**Step 1: Write test**

```python
# tests/agents/test_literature_agent.py
import pytest
from unittest.mock import AsyncMock, patch

from nexus.agents.literature.agent import run_literature_agent, LiteratureResult


@pytest.mark.asyncio
async def test_run_literature_agent():
	from nexus.agents.literature.search import Paper
	from nexus.agents.literature.extract import Triple

	mock_papers = [Paper(paper_id="PMID:1", title="Test", abstract="LRRK2 in PD")]
	mock_triples = [Triple("LRRK2", "Gene", "assoc", "PD", "Disease", 0.9, "PMID:1")]

	with (
		patch("nexus.agents.literature.agent.search_papers", new_callable=AsyncMock, return_value=mock_papers),
		patch("nexus.agents.literature.agent.extract_triples", new_callable=AsyncMock, return_value=mock_triples),
	):
		result = await run_literature_agent("LRRK2 Parkinson's disease")
		assert isinstance(result, LiteratureResult)
		assert len(result.papers) == 1
		assert len(result.triples) == 1
```

**Step 2: Implement**

```python
# backend/src/nexus/agents/literature/agent.py
"""Literature Agent: search papers, extract triples."""
from dataclasses import dataclass, field

from nexus.agents.literature.search import search_papers, Paper
from nexus.agents.literature.extract import extract_triples, Triple


@dataclass
class LiteratureResult:
	papers: list[Paper] = field(default_factory=list)
	triples: list[Triple] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)


async def run_literature_agent(
	query: str,
	max_papers: int = 10,
) -> LiteratureResult:
	"""Run the full literature agent: search + extract."""
	result = LiteratureResult()

	try:
		result.papers = await search_papers(query, max_results=max_papers)
	except Exception as e:
		result.errors.append(f"Paper search failed: {e}")
		return result

	try:
		result.triples = await extract_triples(result.papers)
	except Exception as e:
		result.errors.append(f"Triple extraction failed: {e}")

	return result
```

**Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/agents/ -v`

```bash
git add backend/src/nexus/agents/literature/agent.py tests/agents/test_literature_agent.py
git commit -m "feat: add literature agent orchestrator"
```

---

## Phase 4: Checkpoint System + Learning

**Objective:** Build the checkpoint agent that reads learned rules and decides continue/pivot/branch. Build the learning .md file system with auto-compaction.

**Checkpoint:** `pytest tests/checkpoint/ -v` and `pytest tests/learning/ -v` pass.

---

### Task 4.1: Checkpoint Agent

**Files:**
- Create: `backend/src/nexus/checkpoint/__init__.py`
- Create: `backend/src/nexus/checkpoint/agent.py`
- Create: `backend/src/nexus/checkpoint/models.py`
- Test: `tests/checkpoint/test_agent.py`

**Step 1: Write models**

```python
# backend/src/nexus/checkpoint/models.py
from dataclasses import dataclass, field
from enum import Enum


class CheckpointDecision(Enum):
	CONTINUE = "continue"
	PIVOT = "pivot"
	BRANCH = "branch"


@dataclass
class CheckpointResult:
	decision: CheckpointDecision
	reason: str
	pivot_entity: str | None = None
	pivot_entity_type: str | None = None
	confidence: float = 0.0


@dataclass
class CheckpointContext:
	"""Context passed to the checkpoint agent for evaluation."""
	stage: str  # "literature", "graph", "validation", "experiment"
	original_query: str
	current_entity: str
	current_entity_type: str
	pivot_count: int
	max_pivots: int
	# Stage-specific data
	triples: list[dict] = field(default_factory=list)
	hypotheses: list[dict] = field(default_factory=list)
	validation_results: list[dict] = field(default_factory=list)
	experiment_results: list[dict] = field(default_factory=list)
```

**Step 2: Write failing test**

```python
# tests/checkpoint/test_agent.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from nexus.checkpoint.models import CheckpointDecision, CheckpointContext
from nexus.checkpoint.agent import evaluate_checkpoint


@pytest.mark.asyncio
async def test_checkpoint_continue():
	ctx = CheckpointContext(
		stage="literature",
		original_query="Parkinson's disease",
		current_entity="Parkinson disease",
		current_entity_type="Disease",
		pivot_count=0,
		max_pivots=3,
		triples=[{"subject": "LRRK2", "object": "Parkinson disease"}],
	)

	mock_response = MagicMock()
	mock_response.content = [MagicMock(text='{"decision": "continue", "reason": "Results are on track", "pivot_entity": null, "confidence": 0.8}')]

	with patch("nexus.checkpoint.agent.anthropic") as mock_anthropic:
		mock_client = AsyncMock()
		mock_anthropic.AsyncAnthropic.return_value = mock_client
		mock_client.messages.create = AsyncMock(return_value=mock_response)

		result = await evaluate_checkpoint(ctx)
		assert result.decision == CheckpointDecision.CONTINUE


@pytest.mark.asyncio
async def test_checkpoint_pivot_budget_exhausted():
	ctx = CheckpointContext(
		stage="literature",
		original_query="Parkinson's disease",
		current_entity="Parkinson disease",
		current_entity_type="Disease",
		pivot_count=3,
		max_pivots=3,
	)

	result = await evaluate_checkpoint(ctx)
	assert result.decision == CheckpointDecision.CONTINUE
	assert "budget" in result.reason.lower()
```

**Step 3: Implement checkpoint agent**

```python
# backend/src/nexus/checkpoint/agent.py
"""Checkpoint Agent: evaluates pipeline results and decides continue/pivot/branch."""
import json
from pathlib import Path

import anthropic

from nexus.config import settings
from nexus.checkpoint.models import CheckpointDecision, CheckpointResult, CheckpointContext


LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"


def _load_pivot_rules() -> str:
	"""Load pivot rules from learning system."""
	rules_path = LEARNING_DIR / "pivot-rules.md"
	if rules_path.exists():
		return rules_path.read_text()
	return "No pivot rules learned yet."


def _load_playbook(entity: str) -> str:
	"""Load domain playbook if one exists for the entity's domain."""
	playbooks_dir = LEARNING_DIR / "playbooks"
	if not playbooks_dir.exists():
		return ""

	for playbook in playbooks_dir.glob("*.md"):
		if entity.lower() in playbook.stem.lower():
			return playbook.read_text()

	return ""


CHECKPOINT_PROMPT = """You are a research checkpoint agent. Evaluate the current pipeline results and decide whether to continue, pivot, or branch.

STAGE: {stage}
ORIGINAL QUERY: {original_query}
CURRENT ENTITY: {current_entity} ({current_entity_type})
PIVOTS USED: {pivot_count}/{max_pivots}

CURRENT RESULTS:
{results_block}

LEARNED PIVOT RULES:
{pivot_rules}

DOMAIN PLAYBOOK:
{playbook}

Decide:
- "continue": results are on track, proceed to next stage
- "pivot": a more interesting entity emerged, restart from Literature Agent with new target
- "branch": investigate new entity in parallel while continuing current investigation

If pivoting or branching, specify the entity to investigate.

Return JSON:
{{"decision": "continue|pivot|branch", "reason": "why", "pivot_entity": "entity name or null", "pivot_entity_type": "Disease|Gene|Compound|... or null", "confidence": 0.0-1.0}}

Return ONLY JSON."""


async def evaluate_checkpoint(ctx: CheckpointContext) -> CheckpointResult:
	"""Evaluate a checkpoint and decide next action."""
	# Hard limit: if pivot budget is exhausted, always continue
	if ctx.pivot_count >= ctx.max_pivots:
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="Pivot budget exhausted, continuing with current investigation.",
			confidence=1.0,
		)

	if not settings.anthropic_api_key:
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="No API key, defaulting to continue.",
			confidence=0.5,
		)

	# Build results block based on stage
	results_block = ""
	if ctx.triples:
		results_block += f"Triples extracted: {len(ctx.triples)}\n"
		for t in ctx.triples[:10]:
			results_block += f"  - {t.get('subject', '')} {t.get('predicate', '')} {t.get('object', '')}\n"
	if ctx.hypotheses:
		results_block += f"\nHypotheses found: {len(ctx.hypotheses)}\n"
		for h in ctx.hypotheses[:5]:
			results_block += f"  - {h.get('a_name', '')} -> {h.get('b_name', '')} -> {h.get('c_name', '')} (score: {h.get('novelty_score', 0):.2f})\n"
	if ctx.validation_results:
		results_block += f"\nValidation results: {len(ctx.validation_results)}\n"
		for v in ctx.validation_results[:5]:
			results_block += f"  - {v.get('hypothesis', '')}: {v.get('verdict', '')}\n"

	if not results_block:
		results_block = "No results yet."

	pivot_rules = _load_pivot_rules()
	playbook = _load_playbook(ctx.current_entity)

	client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

	try:
		message = await client.messages.create(
			model="claude-sonnet-4-20250514",
			max_tokens=500,
			messages=[{
				"role": "user",
				"content": CHECKPOINT_PROMPT.format(
					stage=ctx.stage,
					original_query=ctx.original_query,
					current_entity=ctx.current_entity,
					current_entity_type=ctx.current_entity_type,
					pivot_count=ctx.pivot_count,
					max_pivots=ctx.max_pivots,
					results_block=results_block,
					pivot_rules=pivot_rules,
					playbook=playbook or "(no playbook for this domain)",
				),
			}],
		)

		text = message.content[0].text.strip()
		if text.startswith("```"):
			text = text.split("\n", 1)[1] if "\n" in text else text[3:]
		if text.endswith("```"):
			text = text[:-3]
		text = text.strip()

		parsed = json.loads(text)
		decision = CheckpointDecision(parsed.get("decision", "continue"))

		return CheckpointResult(
			decision=decision,
			reason=parsed.get("reason", ""),
			pivot_entity=parsed.get("pivot_entity"),
			pivot_entity_type=parsed.get("pivot_entity_type"),
			confidence=float(parsed.get("confidence", 0.5)),
		)

	except Exception:
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="Checkpoint evaluation failed, defaulting to continue.",
			confidence=0.3,
		)
```

**Step 4: Run tests and commit**

Run: `.venv/bin/pytest tests/checkpoint/ -v`

```bash
git add backend/src/nexus/checkpoint/ tests/checkpoint/
git commit -m "feat: add checkpoint agent with pivot rules and domain playbook support"
```

---

### Task 4.2: Learning System

**Files:**
- Create: `backend/src/nexus/learning/__init__.py`
- Create: `backend/src/nexus/learning/writer.py`
- Create: `backend/src/nexus/learning/compactor.py`
- Create: `learning/pivot-rules.md` (seed file)
- Create: `learning/playbooks/.gitkeep`
- Create: `learning/sessions/.gitkeep`
- Test: `tests/learning/test_writer.py`
- Test: `tests/learning/test_compactor.py`

**Step 1: Create seed pivot rules**

```markdown
# Pivot Rules

## Literature Stage
- If >3 triples mention a Gene not in the original query, consider branching to that Gene
- If paper abstracts mention a novel compound-gene interaction with confidence >0.9, branch

## Graph Stage
- If top ABC hypothesis has a novelty_score >0.9 and the intermediary B is a Gene, consider pivoting to investigate that Gene
- If <3 hypotheses found with novelty >0.8, widen target_types to include more node types
- If a Disease-Disease comorbidity path is found with high evidence, branch to the comorbid disease

## Validation Stage
- If computational validation reveals an unexpected protein-protein interaction, branch to investigate
- If validation contradicts the top hypothesis, check if intermediary B connects to alternative C nodes

## Experiment Stage
- If experiment confirms hypothesis, mark as validated and continue
- If experiment refutes, pivot to next-highest-scoring hypothesis
- If inconclusive, redesign experiment with different parameters
```

**Step 2: Write session log writer**

```python
# backend/src/nexus/learning/writer.py
"""Write learning artifacts after sessions."""
from datetime import datetime
from pathlib import Path


LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"


def write_session_log(
	session_id: str,
	query: str,
	entities_explored: list[str],
	pivots: list[dict],
	hypotheses: list[dict],
	learnings: str,
) -> Path:
	"""Write a session log to learning/sessions/."""
	sessions_dir = LEARNING_DIR / "sessions"
	sessions_dir.mkdir(parents=True, exist_ok=True)

	date_str = datetime.now().strftime("%Y-%m-%d")
	log_path = sessions_dir / f"{session_id}.md"

	content = f"""# Session {session_id} - {date_str}

## Query: {query}

## Entities Explored
{chr(10).join(f"- {e}" for e in entities_explored)}

## Pivots Taken: {len(pivots)}
"""
	for p in pivots:
		content += f"- {p.get('from', '?')} -> {p.get('to', '?')}, reason: {p.get('reason', '?')}, outcome: {p.get('outcome', '?')}\n"

	content += f"""
## Top Hypotheses
"""
	for h in hypotheses[:5]:
		content += f"- {h.get('title', '?')} (score: {h.get('overall_score', 0):.2f})\n"

	content += f"""
## Learnings
{learnings}
"""

	log_path.write_text(content)
	return log_path


def update_domain_playbook(disease_area: str, new_patterns: list[str]) -> Path:
	"""Append new patterns to a domain playbook."""
	playbooks_dir = LEARNING_DIR / "playbooks"
	playbooks_dir.mkdir(parents=True, exist_ok=True)

	safe_name = disease_area.lower().replace("'", "").replace(" ", "-")
	playbook_path = playbooks_dir / f"{safe_name}.md"

	if playbook_path.exists():
		existing = playbook_path.read_text()
	else:
		existing = f"# {disease_area} Playbook\n\n"

	for pattern in new_patterns:
		if pattern not in existing:
			existing += f"- {pattern}\n"

	playbook_path.write_text(existing)
	return playbook_path
```

**Step 3: Write compactor**

```python
# backend/src/nexus/learning/compactor.py
"""Auto-compact learning files to prevent infinite growth."""
from datetime import datetime
from pathlib import Path

import anthropic

from nexus.config import settings


LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"


async def compact_session_logs(max_sessions: int = 50) -> bool:
	"""If >max_sessions logs exist, summarize oldest into archive."""
	sessions_dir = LEARNING_DIR / "sessions"
	if not sessions_dir.exists():
		return False

	logs = sorted(sessions_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
	# Exclude archives
	logs = [l for l in logs if not l.stem.startswith("archive-")]

	if len(logs) <= max_sessions:
		return False

	# Take oldest 80% for archiving
	to_archive = logs[:int(len(logs) * 0.8)]
	combined = "\n\n---\n\n".join(f.read_text() for f in to_archive)

	summary = await _summarize_text(
		combined,
		"Summarize these research session logs into a concise digest of key patterns, "
		"productive pivots, dead ends, and domain-specific learnings. Keep only actionable insights.",
	)

	date_str = datetime.now().strftime("%Y-%m-%d")
	archive_path = sessions_dir / f"archive-{date_str}.md"
	archive_path.write_text(f"# Session Archive - {date_str}\n\n{summary}\n")

	for f in to_archive:
		f.unlink()

	_log_compaction("session_logs", len(to_archive), archive_path)
	return True


async def compact_playbook(playbook_path: Path, max_lines: int = 200) -> bool:
	"""If playbook exceeds max_lines, distill to confirmed patterns."""
	if not playbook_path.exists():
		return False

	content = playbook_path.read_text()
	if content.count("\n") <= max_lines:
		return False

	summary = await _summarize_text(
		content,
		"Distill this domain playbook to its most useful patterns. "
		"Keep only patterns that appear to be confirmed across multiple sessions. "
		"Remove speculative or one-off observations. Target under 100 lines.",
	)

	playbook_path.write_text(summary)
	_log_compaction("playbook", playbook_path.stem, playbook_path)
	return True


async def compact_pivot_rules(max_rules: int = 50) -> bool:
	"""If pivot rules exceed max_rules, prune least useful."""
	rules_path = LEARNING_DIR / "pivot-rules.md"
	if not rules_path.exists():
		return False

	content = rules_path.read_text()
	rule_lines = [l for l in content.split("\n") if l.strip().startswith("- ")]

	if len(rule_lines) <= max_rules:
		return False

	summary = await _summarize_text(
		content,
		"Rank these pivot rules by likely usefulness. Keep the top 80% that seem "
		"most actionable and well-supported. Remove vague or redundant rules. "
		"Preserve the markdown structure with headers.",
	)

	rules_path.write_text(summary)
	_log_compaction("pivot_rules", len(rule_lines), rules_path)
	return True


async def _summarize_text(text: str, instruction: str) -> str:
	"""Use Claude to summarize text."""
	if not settings.anthropic_api_key:
		# Fallback: keep first 50% of lines
		lines = text.split("\n")
		return "\n".join(lines[:len(lines) // 2])

	client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
	message = await client.messages.create(
		model="claude-sonnet-4-20250514",
		max_tokens=2000,
		messages=[{"role": "user", "content": f"{instruction}\n\n{text}"}],
	)
	return message.content[0].text


def _log_compaction(what: str, detail, path: Path) -> None:
	"""Log compaction events."""
	log_path = LEARNING_DIR / "compaction-log.md"
	date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
	entry = f"- [{date_str}] Compacted {what}: {detail} -> {path.name}\n"

	if log_path.exists():
		content = log_path.read_text() + entry
	else:
		content = f"# Compaction Log\n\n{entry}"

	log_path.write_text(content)
```

**Step 4: Write tests**

```python
# tests/learning/test_writer.py
import tempfile
from pathlib import Path
from unittest.mock import patch

from nexus.learning.writer import write_session_log, update_domain_playbook


def test_write_session_log(tmp_path):
	with patch("nexus.learning.writer.LEARNING_DIR", tmp_path):
		path = write_session_log(
			session_id="test-123",
			query="Parkinson's disease",
			entities_explored=["Parkinson disease", "LRRK2"],
			pivots=[{"from": "PD", "to": "LRRK2", "reason": "high triple count", "outcome": "productive"}],
			hypotheses=[{"title": "PD-LRRK2-Ibuprofen", "overall_score": 0.85}],
			learnings="Gene intermediaries were most productive.",
		)
		assert path.exists()
		content = path.read_text()
		assert "Parkinson" in content
		assert "LRRK2" in content
		assert "productive" in content
```

**Step 5: Run tests and commit**

Run: `.venv/bin/pytest tests/learning/ tests/checkpoint/ -v`

```bash
git add backend/src/nexus/learning/ backend/src/nexus/checkpoint/ learning/ tests/learning/ tests/checkpoint/
git commit -m "feat: add learning system with session logs, playbooks, pivot rules, and auto-compaction"
```

---

## Phase 5: Pipeline Orchestrator

**Objective:** Chain Literature -> Checkpoint -> Graph -> Checkpoint -> Reasoning -> Validation -> Checkpoint, with pivot/branch support.

**Checkpoint:** `pytest tests/pipeline/ -v` passes.

---

### Task 5.1: Pipeline Orchestrator with Checkpoints

**Files:**
- Create: `backend/src/nexus/pipeline/__init__.py`
- Create: `backend/src/nexus/pipeline/orchestrator.py`
- Test: `tests/pipeline/test_orchestrator.py`

**Step 1: Write the orchestrator**

```python
# backend/src/nexus/pipeline/orchestrator.py
"""Adaptive pipeline orchestrator with checkpoint-driven pivots."""
import asyncio
from dataclasses import dataclass, field
from enum import Enum

from nexus.agents.literature.agent import run_literature_agent, LiteratureResult
from nexus.agents.literature.extract import Triple
from nexus.graph.abc import find_abc_hypotheses, ABCHypothesis
from nexus.graph.client import graph_client
from nexus.checkpoint.agent import evaluate_checkpoint
from nexus.checkpoint.models import CheckpointDecision, CheckpointContext, CheckpointResult


class PipelineStep(Enum):
	LITERATURE = "literature"
	GRAPH = "graph"
	REASONING = "reasoning"
	VALIDATION = "validation"
	VISUALIZATION = "visualization"
	PROTOCOL = "protocol"
	COMPLETED = "completed"
	FAILED = "failed"


@dataclass
class PipelineResult:
	query: str
	start_entity: str
	start_type: str
	step: PipelineStep = PipelineStep.LITERATURE
	literature_result: LiteratureResult | None = None
	hypotheses: list[ABCHypothesis] = field(default_factory=list)
	scored_hypotheses: list[dict] = field(default_factory=list)
	pivots: list[dict] = field(default_factory=list)
	branches: list["PipelineResult"] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)
	checkpoint_log: list[dict] = field(default_factory=list)


async def merge_triples_to_graph(triples: list[Triple]) -> int:
	"""Merge extracted triples into Neo4j as new edges."""
	count = 0
	for t in triples:
		try:
			query = (
				f"MERGE (a:{t.subject_type} {{name: $subject}}) "
				f"MERGE (b:{t.object_type} {{name: $object}}) "
				f"MERGE (a)-[r:EXTRACTED {{predicate: $predicate}}]->(b) "
				f"SET r.source = 'literature', r.is_novel = true, "
				f"r.confidence = $confidence, r.source_paper = $paper_id"
			)
			await graph_client.execute_write(
				query,
				subject=t.subject, object=t.object,
				predicate=t.predicate, confidence=t.confidence,
				paper_id=t.source_paper_id,
			)
			count += 1
		except Exception:
			pass
	return count


def score_hypothesis(abc: ABCHypothesis, triples: list[Triple]) -> dict:
	"""Score a hypothesis based on graph and literature evidence."""
	# Evidence score: how many triples mention entities in this hypothesis
	relevant_triples = [
		t for t in triples
		if abc.a_name.lower() in (t.subject.lower(), t.object.lower())
		or abc.b_name.lower() in (t.subject.lower(), t.object.lower())
		or abc.c_name.lower() in (t.subject.lower(), t.object.lower())
	]
	evidence_score = min(len(relevant_triples) / 5.0, 1.0)

	# Determine hypothesis type
	if abc.c_type == "Compound" and abc.a_type == "Disease":
		h_type = "drug_repurposing"
	elif abc.c_type == "Disease" and abc.a_type == "Disease":
		h_type = "comorbidity"
	elif abc.c_type == "BiologicalProcess":
		h_type = "mechanism"
	elif abc.c_type == "Compound" and abc.a_type == "Compound":
		h_type = "drug_interaction"
	elif abc.c_type == "Gene":
		h_type = "target_discovery"
	else:
		h_type = "connection"

	overall = (
		abc.novelty_score * 0.3
		+ evidence_score * 0.4
		+ abc.path_strength * 0.3
	)

	disease_area = abc.a_name if abc.a_type == "Disease" else (abc.c_name if abc.c_type == "Disease" else None)

	return {
		"title": f"{abc.a_name} -> {abc.b_name} -> {abc.c_name}",
		"description": f"Novel {h_type} connection via {abc.b_name} ({abc.b_type})",
		"disease_area": disease_area,
		"hypothesis_type": h_type,
		"novelty_score": abc.novelty_score,
		"evidence_score": evidence_score,
		"path_strength": abc.path_strength,
		"overall_score": round(overall, 4),
		"abc_path": {
			"a": {"id": abc.a_id, "name": abc.a_name, "type": abc.a_type},
			"b": {"id": abc.b_id, "name": abc.b_name, "type": abc.b_type},
			"c": {"id": abc.c_id, "name": abc.c_name, "type": abc.c_type},
		},
		"ab_relationship": abc.ab_relationship,
		"bc_relationship": abc.bc_relationship,
		"path_count": abc.path_count,
		"intermediaries": abc.intermediaries,
	}


async def run_pipeline(
	query: str,
	start_entity: str | None = None,
	start_type: str = "Disease",
	target_types: list[str] | None = None,
	max_hypotheses: int = 10,
	max_papers: int = 10,
	max_pivots: int = 3,
	on_event: callable = None,
) -> PipelineResult:
	"""Run the adaptive discovery pipeline with checkpoints."""
	source_name = start_entity or query
	if target_types is None:
		target_types = ["Compound", "Gene", "BiologicalProcess"]

	result = PipelineResult(
		query=query,
		start_entity=source_name,
		start_type=start_type,
	)
	pivot_count = 0

	async def _emit(event_type: str, data: dict = None):
		if on_event:
			await on_event(event_type, data or {})

	# === STAGE 1: LITERATURE ===
	result.step = PipelineStep.LITERATURE
	await _emit("stage_start", {"stage": "literature", "entity": source_name})

	try:
		result.literature_result = await run_literature_agent(query, max_papers=max_papers)
		await _emit("stage_complete", {
			"stage": "literature",
			"papers": len(result.literature_result.papers),
			"triples": len(result.literature_result.triples),
		})
	except Exception as e:
		result.errors.append(f"Literature failed: {e}")
		result.step = PipelineStep.FAILED
		return result

	# Merge triples into graph
	if result.literature_result.triples:
		try:
			merged = await merge_triples_to_graph(result.literature_result.triples)
			await _emit("triples_merged", {"count": merged})
		except Exception as e:
			result.errors.append(f"Triple merge failed: {e}")

	# CHECKPOINT after literature
	checkpoint_ctx = CheckpointContext(
		stage="literature",
		original_query=query,
		current_entity=source_name,
		current_entity_type=start_type,
		pivot_count=pivot_count,
		max_pivots=max_pivots,
		triples=[
			{"subject": t.subject, "predicate": t.predicate, "object": t.object}
			for t in result.literature_result.triples
		],
	)
	cp_result = await evaluate_checkpoint(checkpoint_ctx)
	result.checkpoint_log.append({
		"stage": "literature", "decision": cp_result.decision.value,
		"reason": cp_result.reason, "pivot_entity": cp_result.pivot_entity,
	})

	if cp_result.decision == CheckpointDecision.PIVOT and cp_result.pivot_entity:
		pivot_count += 1
		source_name = cp_result.pivot_entity
		start_type = cp_result.pivot_entity_type or start_type
		result.pivots.append({"from": result.start_entity, "to": source_name, "reason": cp_result.reason, "stage": "literature"})
		await _emit("pivot", {"from": result.start_entity, "to": source_name, "reason": cp_result.reason})
	elif cp_result.decision == CheckpointDecision.BRANCH and cp_result.pivot_entity:
		pivot_count += 1
		branch_task = run_pipeline(
			query=f"Investigate {cp_result.pivot_entity}",
			start_entity=cp_result.pivot_entity,
			start_type=cp_result.pivot_entity_type or "Gene",
			target_types=target_types,
			max_hypotheses=max_hypotheses,
			max_papers=max_papers // 2,
			max_pivots=0,  # branches don't get their own pivots
		)
		result.branches.append(asyncio.ensure_future(branch_task))
		await _emit("branch", {"entity": cp_result.pivot_entity, "reason": cp_result.reason})

	# === STAGE 2: GRAPH (ABC TRAVERSAL) ===
	result.step = PipelineStep.GRAPH
	await _emit("stage_start", {"stage": "graph", "entity": source_name})

	for target in target_types:
		try:
			hypotheses = await find_abc_hypotheses(
				source_name=source_name,
				source_type=start_type,
				target_type=target,
				max_results=max_hypotheses,
			)
			result.hypotheses.extend(hypotheses)
		except Exception as e:
			result.errors.append(f"ABC for {target} failed: {e}")

	# Score all hypotheses
	triples = result.literature_result.triples if result.literature_result else []
	result.scored_hypotheses = [score_hypothesis(h, triples) for h in result.hypotheses]
	result.scored_hypotheses.sort(key=lambda x: x["overall_score"], reverse=True)

	await _emit("stage_complete", {
		"stage": "graph",
		"hypotheses": len(result.scored_hypotheses),
	})

	# CHECKPOINT after graph
	checkpoint_ctx = CheckpointContext(
		stage="graph",
		original_query=query,
		current_entity=source_name,
		current_entity_type=start_type,
		pivot_count=pivot_count,
		max_pivots=max_pivots,
		hypotheses=[
			{"a_name": h["abc_path"]["a"]["name"], "b_name": h["abc_path"]["b"]["name"],
			 "c_name": h["abc_path"]["c"]["name"], "novelty_score": h["novelty_score"]}
			for h in result.scored_hypotheses[:5]
		],
	)
	cp_result = await evaluate_checkpoint(checkpoint_ctx)
	result.checkpoint_log.append({
		"stage": "graph", "decision": cp_result.decision.value,
		"reason": cp_result.reason, "pivot_entity": cp_result.pivot_entity,
	})

	# Handle pivot/branch after graph (same pattern as above)
	if cp_result.decision == CheckpointDecision.PIVOT and cp_result.pivot_entity and pivot_count < max_pivots:
		pivot_count += 1
		result.pivots.append({"from": source_name, "to": cp_result.pivot_entity, "reason": cp_result.reason, "stage": "graph"})
		# Re-run literature + graph for the new entity
		pivot_lit = await run_literature_agent(cp_result.pivot_entity, max_papers=max_papers // 2)
		if pivot_lit.triples:
			await merge_triples_to_graph(pivot_lit.triples)
		pivot_hyps = await find_abc_hypotheses(
			source_name=cp_result.pivot_entity,
			source_type=cp_result.pivot_entity_type or "Gene",
			target_type="Compound",
		)
		pivot_scored = [score_hypothesis(h, pivot_lit.triples) for h in pivot_hyps]
		result.scored_hypotheses.extend(pivot_scored)
		result.scored_hypotheses.sort(key=lambda x: x["overall_score"], reverse=True)

	# Await any branches
	for branch_future in result.branches:
		if asyncio.isfuture(branch_future):
			try:
				branch_result = await branch_future
				result.scored_hypotheses.extend(branch_result.scored_hypotheses)
				result.scored_hypotheses.sort(key=lambda x: x["overall_score"], reverse=True)
			except Exception as e:
				result.errors.append(f"Branch failed: {e}")

	# Trim to max_hypotheses
	result.scored_hypotheses = result.scored_hypotheses[:max_hypotheses]

	result.step = PipelineStep.COMPLETED
	await _emit("pipeline_complete", {"total_hypotheses": len(result.scored_hypotheses), "pivots": len(result.pivots)})

	return result
```

**Step 2: Write test**

```python
# tests/pipeline/test_orchestrator.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from nexus.pipeline.orchestrator import run_pipeline, score_hypothesis, PipelineStep
from nexus.graph.abc import ABCHypothesis
from nexus.checkpoint.models import CheckpointDecision, CheckpointResult


def _mock_hypothesis():
	return ABCHypothesis(
		a_id="D1", a_name="Parkinson disease", a_type="Disease",
		b_id="G1", b_name="LRRK2", b_type="Gene",
		c_id="C1", c_name="Ibuprofen", c_type="Compound",
		ab_relationship="ASSOCIATES_DaG", bc_relationship="BINDS_CbG",
		path_count=5, novelty_score=0.95, path_strength=0.7,
	)


def test_score_hypothesis():
	h = _mock_hypothesis()
	scored = score_hypothesis(h, [])
	assert scored["hypothesis_type"] == "drug_repurposing"
	assert scored["overall_score"] > 0
	assert scored["disease_area"] == "Parkinson disease"


@pytest.mark.asyncio
async def test_run_pipeline_basic():
	from nexus.agents.literature.agent import LiteratureResult
	from nexus.agents.literature.search import Paper

	mock_lit = LiteratureResult(
		papers=[Paper("PMID:1", "Test", "abstract")],
		triples=[],
	)
	mock_hyps = [_mock_hypothesis()]
	continue_result = CheckpointResult(
		decision=CheckpointDecision.CONTINUE,
		reason="On track",
		confidence=0.8,
	)

	with (
		patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock, return_value=mock_lit),
		patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock, return_value=mock_hyps),
		patch("nexus.pipeline.orchestrator.evaluate_checkpoint", new_callable=AsyncMock, return_value=continue_result),
		patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock, return_value=0),
	):
		result = await run_pipeline("Parkinson's disease", start_entity="Parkinson disease")
		assert result.step == PipelineStep.COMPLETED
		assert len(result.scored_hypotheses) >= 1
		assert result.scored_hypotheses[0]["hypothesis_type"] == "drug_repurposing"
```

**Step 3: Run tests and commit**

Run: `.venv/bin/pytest tests/pipeline/ -v`

```bash
git add backend/src/nexus/pipeline/ tests/pipeline/
git commit -m "feat: add adaptive pipeline orchestrator with checkpoint-driven pivots"
```

---

## Phase 6: Validation Agent + MCP Tools

**Objective:** Build 7 validation tools, the agent harness with budget enforcement, and the Claude-driven validation loop.

**Checkpoint:** `pytest tests/tools/ tests/harness/ -v` passes.

This phase has many files. Implement the tool schema, then each tool, then the harness, then the validation agent.

---

### Task 6.1: Tool Response Schema

**Files:**
- Create: `backend/src/nexus/tools/__init__.py`
- Create: `backend/src/nexus/tools/schema.py`
- Test: `tests/tools/test_schema.py`

```python
# backend/src/nexus/tools/schema.py
from dataclasses import dataclass, field


@dataclass
class ToolResponse:
	status: str  # "success", "partial", "error"
	confidence_delta: float  # how much to adjust hypothesis confidence (-1.0 to 1.0)
	evidence_type: str  # "supporting", "contradicting", "neutral"
	summary: str
	raw_data: dict = field(default_factory=dict)
```

Test: verify dataclass creation and defaults.

---

### Task 6.2-6.8: Implement 7 Validation Tools

Each tool follows the same pattern:
- Takes a hypothesis dict + relevant parameters
- Calls an external API (or Claude for generate_protocol)
- Returns a `ToolResponse`

**Tools to implement:**

1. `backend/src/nexus/tools/literature_validate.py` - Search PubMed for papers supporting/contradicting the hypothesis
2. `backend/src/nexus/tools/compound_lookup.py` - Look up compound data from PubChem + clinical trials
3. `backend/src/nexus/tools/pathway_overlap.py` - Check KEGG pathway co-membership of A and C via B
4. `backend/src/nexus/tools/protein_interaction.py` - Query STRING database for protein-protein interactions
5. `backend/src/nexus/tools/expression_correlate.py` - Check GEO expression profiles for co-expression
6. `backend/src/nexus/tools/molecular_dock.py` - Tamarind Bio API for binding affinity prediction (ref: `docs/api-docs/tamarind-bio.md`)
7. `backend/src/nexus/tools/generate_protocol.py` - Claude-generated wet lab protocol for hypothesis validation

Each tool gets its own test file in `tests/tools/`.

Reference: `docs/api-docs/tamarind-bio.md` for molecular_dock tool (submit job -> poll -> get results).

**Commit after each tool or batch:**

```bash
git commit -m "feat: add validation tools (literature, compound, pathway, protein, expression, dock, protocol)"
```

---

### Task 6.9: Agent Harness

**Files:**
- Create: `backend/src/nexus/harness/__init__.py`
- Create: `backend/src/nexus/harness/models.py`
- Create: `backend/src/nexus/harness/event_store.py`
- Create: `backend/src/nexus/harness/harness.py`
- Test: `tests/harness/test_harness.py`

**Harness models:**

```python
# backend/src/nexus/harness/models.py
from dataclasses import dataclass, field


@dataclass
class HarnessConfig:
	max_iterations_per_hypothesis: int = 10
	max_total_tool_calls: int = 50
	timeout_minutes: int = 30


@dataclass
class Event:
	event_id: str
	session_id: str
	event_type: str  # "tool_call", "verdict", "session_created", "checkpoint", "pivot"
	hypothesis_id: str | None = None
	tool_name: str | None = None
	input_data: dict | None = None
	output_data: dict | None = None
	confidence_snapshot: float | None = None
	timestamp: str = ""
```

**Event store:** In-memory list with SSE callback support. Stores events, supports filtering by session/hypothesis, and dispatches to registered callbacks for real-time streaming.

**Harness:** Tracks tool call counts per session and per hypothesis, enforces budget limits, logs events, tracks consecutive failures per tool (auto-disable after N failures).

---

### Task 6.10: Validation Agent Loop

**Files:**
- Create: `backend/src/nexus/harness/validation_agent.py`
- Test: `tests/harness/test_validation_agent.py`

The validation agent:
1. Takes a hypothesis + available tools + harness
2. Claude decides which tool to call next based on hypothesis type and prior results
3. Runs the tool, captures ToolResponse
4. Updates confidence based on confidence_delta
5. Repeats until: 2+ supporting tools OR budget exhausted
6. Renders verdict: "validated", "refuted", "inconclusive"

Tool strategy by hypothesis type:
- drug_repurposing: compound_lookup -> molecular_dock -> literature_validate
- mechanism: pathway_overlap -> expression_correlate -> literature_validate
- target_discovery: protein_interaction -> expression_correlate -> literature_validate

**Commit:**

```bash
git commit -m "feat: add agent harness with budget enforcement and validation agent loop"
```

---

## Phase 7: Reasoning Agent

**Objective:** Quick summaries for all hypotheses, full research briefs for top N.

**Checkpoint:** `pytest tests/agents/test_reasoning_agent.py -v` passes.

---

### Task 7.1: Reasoning Agent

**Files:**
- Create: `backend/src/nexus/agents/reasoning_agent.py`
- Test: `tests/agents/test_reasoning_agent.py`

Two functions:
- `generate_quick_summaries(hypotheses, triples) -> list[str]` - single Claude call, 2-3 sentences per hypothesis
- `generate_research_brief(hypothesis, triples, papers) -> ResearchBrief` - detailed ~500 word brief with confidence assessment

Uses claude-sonnet-4-20250514 for cost efficiency. Falls back to template-based summaries if no API key.

**Commit:**

```bash
git commit -m "feat: add reasoning agent with quick summaries and research briefs"
```

---

## Phase 8: CloudLab Integration

**Objective:** Abstract provider interface, Strateos adapter, protocol agent.

**Checkpoint:** `pytest tests/cloudlab/ -v` passes.

---

### Task 8.1: CloudLab Provider Interface + Strateos Adapter

**Files:**
- Create: `backend/src/nexus/cloudlab/__init__.py`
- Create: `backend/src/nexus/cloudlab/provider.py`
- Create: `backend/src/nexus/cloudlab/strateos.py`
- Create: `backend/src/nexus/cloudlab/protocol_agent.py`
- Test: `tests/cloudlab/test_strateos.py`
- Test: `tests/cloudlab/test_protocol_agent.py`

**Provider interface:**

```python
# backend/src/nexus/cloudlab/provider.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExperimentProtocol:
	hypothesis_id: str
	title: str
	description: str
	protocol_json: dict  # Provider-specific format
	estimated_cost: float | None = None


@dataclass
class ExperimentSubmission:
	submission_id: str
	provider: str
	status: str  # "submitted", "running", "completed", "failed"


@dataclass
class ExperimentResults:
	submission_id: str
	status: str
	data: dict
	summary: str


class CloudLabProvider(Protocol):
	async def validate_protocol(self, protocol: ExperimentProtocol) -> dict: ...
	async def submit_experiment(self, protocol: ExperimentProtocol) -> ExperimentSubmission: ...
	async def poll_status(self, submission_id: str) -> str: ...
	async def get_results(self, submission_id: str) -> ExperimentResults: ...
```

**Strateos adapter:** Implements CloudLabProvider using the Strateos REST API + Autoprotocol JSON format. Uses `transcriptic analyze` for dry-run validation. Reference: Strateos developer docs.

**Protocol agent:** Takes a validated hypothesis, uses Claude to generate an Autoprotocol JSON experiment design, then submits to the configured CloudLab provider.

**Commit:**

```bash
git commit -m "feat: add CloudLab integration with provider interface and Strateos adapter"
```

---

## Phase 9: Visualization (BioRender)

**Objective:** BioRender MCP integration for traceable discovery path diagrams.

**Checkpoint:** `pytest tests/agents/test_viz_agent.py -v` passes.

---

### Task 9.1: Visualization Agent

**Files:**
- Create: `backend/src/nexus/agents/viz_agent.py`
- Test: `tests/agents/test_viz_agent.py`

Reference: `docs/api-docs/biorender-mcp.md`

The viz agent:
- Takes a hypothesis with its ABC path and any pivot trail
- Searches BioRender for relevant icons (disease, gene, compound)
- Returns figure URLs and icon metadata for the frontend to compose into discovery path diagrams
- Gracefully degrades if BIORENDER_API_KEY is not set

**Commit:**

```bash
git commit -m "feat: add BioRender visualization agent"
```

---

## Phase 10: Heartbeat Engine

**Objective:** Autonomous paper ingestion, delta detection, scheduled ABC sweeps.

**Checkpoint:** `pytest tests/heartbeat/ -v` passes.

---

### Task 10.1: Heartbeat Engine

**Files:**
- Create: `backend/src/nexus/heartbeat/__init__.py`
- Create: `backend/src/nexus/heartbeat/ingest.py`
- Create: `backend/src/nexus/heartbeat/delta.py`
- Create: `backend/src/nexus/heartbeat/engine.py`
- Test: `tests/heartbeat/test_ingest.py`
- Test: `tests/heartbeat/test_delta.py`
- Test: `tests/heartbeat/test_engine.py`

**Ingestion:** Polls PubMed for recent papers (last 24h/7d), extracts triples, merges into Neo4j.

**Delta detection:** Compares new edges against existing graph. Flags "high-delta" edges where a new A-B link creates novel ABC paths that didn't exist before.

**Engine:** Async loop: ingest -> detect deltas -> ABC sweep on highest-delta edges -> score -> publish to Discovery Feed.

**Commit:**

```bash
git commit -m "feat: add heartbeat engine for autonomous discovery"
```

---

## Phase 11: FastAPI Gateway + Frontend

**Objective:** All API routes, Next.js frontend with 7 pages.

**Checkpoint:** Backend: `pytest tests/api/ -v` passes, `uvicorn nexus.api.app:app` starts. Frontend: `npm run build` succeeds.

---

### Task 11.1: FastAPI App + Routes

**Files:**
- Create: `backend/src/nexus/api/__init__.py`
- Create: `backend/src/nexus/api/app.py`
- Create: `backend/src/nexus/api/deps.py`
- Create: `backend/src/nexus/api/routes/health.py`
- Create: `backend/src/nexus/api/routes/sessions.py`
- Create: `backend/src/nexus/api/routes/query.py`
- Create: `backend/src/nexus/api/routes/feed.py`
- Create: `backend/src/nexus/api/routes/graph.py`
- Create: `backend/src/nexus/api/routes/hypotheses.py`
- Create: `backend/src/nexus/api/routes/experiments.py`
- Test: `tests/api/test_health.py`
- Test: `tests/api/test_sessions.py`

**FastAPI app with lifespan:**

```python
# backend/src/nexus/api/app.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.graph.client import graph_client
from nexus.api.routes import health, sessions, query, feed, graph, hypotheses, experiments


@asynccontextmanager
async def lifespan(app: FastAPI):
	await graph_client.connect()
	yield
	await graph_client.close()


app = FastAPI(
	title="Nexus API",
	description="Autonomous Biological Discovery Platform",
	version="0.1.0",
	lifespan=lifespan,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(feed.router, prefix="/api", tags=["feed"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(hypotheses.router, prefix="/api", tags=["hypotheses"])
app.include_router(experiments.router, prefix="/api", tags=["experiments"])
```

**Key routes:**
- `POST /api/sessions` - creates session, starts pipeline in background, returns session_id
- `GET /api/sessions/{id}/stream` - SSE stream of real-time events (tool calls, checkpoints, pivots, verdicts)
- `GET /api/sessions/{id}/report` - final scored hypotheses with briefs
- All other routes per the design doc API surface

**Commit:**

```bash
git commit -m "feat: add FastAPI gateway with all API routes"
```

---

### Task 11.2: Next.js Frontend Setup

**Step 1:** Initialize Next.js in `frontend/`

Run: `cd /Users/dannyliu/personal_projects/nexus && npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack`

**Step 2:** Install shadcn/ui

Run: `cd frontend && npx shadcn@latest init -d`

**Step 3:** Install additional deps

Run: `cd frontend && npm install react-force-graph-2d @supabase/supabase-js @tanstack/react-query recharts framer-motion`

**Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Next.js frontend with shadcn/ui and dependencies"
```

---

### Task 11.3-11.9: Frontend Pages

Build 7 pages per the design doc:

1. **Landing** (`app/page.tsx`) - hero, live stats, sample discoveries, sign up
2. **Query Builder** (`app/query/page.tsx`) - entity autocomplete, target type checkboxes, reasoning depth, pivot budget slider
3. **Session Monitor** (`app/session/[id]/page.tsx`) - real-time SSE timeline (left), hypothesis panel (right), metrics bar (bottom). Show pivot decisions as branching nodes
4. **Discovery Feed** (`app/feed/page.tsx`) - scrollable feed cards, disease filter, subscribe buttons
5. **Graph Explorer** (`app/graph/page.tsx`) - react-force-graph-2d visualization, click nodes, highlight ABC paths
6. **Hypothesis Detail** (`app/hypothesis/[id]/page.tsx`) - evidence chain, ABC path mini-graph, BioRender figures, confidence breakdown, research brief, experiment status
7. **Dashboard** (`app/dashboard/page.tsx`) - credits, session history, subscriptions, API keys

**API client** (`lib/api.ts`):
- `createSession(request)` - POST /api/sessions
- `streamSessionEvents(sessionId, onEvent)` - SSE stream
- `getSessionReport(sessionId)` - GET /api/sessions/{id}/report
- `getFeed(filters)` - GET /api/feed
- `getHypothesis(id)` - GET /api/hypotheses/{id}

**Design tokens:** White (#ffffff/#fafafa) backgrounds, slate-800 (#1e293b) text, teal-600 (#0891b2) accent, success (#059669), warning (#d97706).

**Commit after each page or batch.**

---

## Phase 12: Integration + Deployment

**Objective:** End-to-end test, CLAUDE.md, deploy.

---

### Task 12.1: Research Session Runner

**Files:**
- Create: `backend/src/nexus/harness/runner.py`
- Test: `tests/integration/test_full_session.py`

The runner ties everything together:
1. Create session in Supabase
2. Run adaptive pipeline (literature -> checkpoint -> graph -> checkpoint -> reasoning -> validation -> checkpoint -> viz -> protocol)
3. Stream events via SSE
4. Write session learning log
5. Update graph with new relationships
6. Check auto-compaction triggers
7. Return final results

**Commit:**

```bash
git commit -m "feat: add research session runner with full pipeline integration"
```

---

### Task 12.2: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

Project-specific instructions for the repo:
- How to run tests, lint, type check
- Directory structure explanation
- Coding conventions (tabs, double quotes)
- How to run the backend and frontend
- How to seed Hetionet
- API key setup

**Commit:**

```bash
git commit -m "docs: add project CLAUDE.md"
```

---

### Task 12.3: Deploy

**Frontend:** `cd frontend && vercel deploy` (Vercel token is available)

**Backend:** Dockerize FastAPI app

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY backend/ backend/
RUN pip install .
CMD ["uvicorn", "nexus.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Commit:**

```bash
git commit -m "feat: add Dockerfile and deployment configuration"
```

---

## Phase Dependency Graph

```
Phase 1 (Scaffolding) ──┬── Phase 2 (ABC Engine)
                         ├── Phase 3 (Literature Agent)
                         └── Phase 11.2 (Frontend Setup)

Phase 2 + 3 ──── Phase 4 (Checkpoint + Learning)

Phase 4 ──── Phase 5 (Pipeline Orchestrator)

Phase 5 ──┬── Phase 6 (Validation Agent + Tools)
           ├── Phase 7 (Reasoning Agent)
           └── Phase 8 (CloudLab Integration)

Phase 6 + 7 + 8 ──── Phase 9 (Visualization)

Phase 9 ──── Phase 10 (Heartbeat)

Phase 5 ──── Phase 11.1 (FastAPI Routes)

Phase 11.1 + 11.2 ──── Phase 11.3-11.9 (Frontend Pages)

All Phases ──── Phase 12 (Integration + Deploy)
```

## Execution Notes

- Total estimated tasks: ~35 implementation tasks
- Each phase should end with a commit
- Tests should pass at every commit point
- The pipeline is usable (CLI) after Phase 5
- The full web app is usable after Phase 11
- CloudLab and Heartbeat can be deferred if needed
