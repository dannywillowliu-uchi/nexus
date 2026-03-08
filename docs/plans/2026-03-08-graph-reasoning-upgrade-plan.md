# Graph Reasoning Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement tiered async fan-out for intermediary queries, bounded multi-entity exploration on BRANCH decisions, and unify molecular_dock.py with TamarindClient.

**Architecture:** Modify `abc.py` to fan out across intermediary types in priority tiers using `asyncio.gather()` with early termination. Extend checkpoint BRANCH handling in `orchestrator.py` to run up to 3 concurrent graph-only branches with semaphore + timeout. Refactor `molecular_dock.py` to use `TamarindClient` for uploads and job submission. Add `list_job_types()` to `TamarindClient`.

**Tech Stack:** Python 3.12, asyncio, Neo4j (local Docker), Tamarind Bio API, pytest + pytest-asyncio

---

## Task 1: Tiered Async Fan-Out in `abc.py`

Replace the Gene-hardcoded `MATCH (a)-[r1]-(b:Gene)` with parallel queries across intermediary types in priority tiers. If tier 1 returns >= `min_results`, skip lower tiers.

**Files:**
- Modify: `backend/src/nexus/graph/abc.py:131-234`
- Test: `tests/graph/test_abc.py`

**Step 1: Write the failing test**

Create `tests/graph/test_abc_fanout.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from nexus.graph.abc import find_abc_hypotheses, INTERMEDIARY_TIERS


def test_intermediary_tiers_defined():
	"""Tiers are defined with expected types."""
	assert len(INTERMEDIARY_TIERS) == 3
	assert INTERMEDIARY_TIERS[0] == ["Gene"]
	assert "Pathway" in INTERMEDIARY_TIERS[1]
	assert "BiologicalProcess" in INTERMEDIARY_TIERS[1]
	assert "Anatomy" in INTERMEDIARY_TIERS[2]


@patch("nexus.graph.abc.graph_client")
async def test_fanout_skips_lower_tiers_when_enough_results(mock_gc):
	"""When tier 1 returns >= min_results hypotheses, tiers 2-3 are skipped."""
	# Build 10 fake records so tier 1 is sufficient
	fake_records = [
		{
			"a_id": "1", "a_name": "Alzheimer", "a_type": "Disease",
			"c_id": str(i), "c_name": f"Drug{i}", "c_type": "Drug",
			"intermediaries": [{"b_id": str(i), "b_name": f"Gene{i}", "b_type": "Gene", "ab_rel": "ASSOCIATED_WITH", "bc_rel": "TARGET"}],
			"path_count": 3,
		}
		for i in range(10)
	]
	mock_gc.execute_read = AsyncMock(return_value=fake_records)

	results = await find_abc_hypotheses(
		source_name="Alzheimer",
		source_type="Disease",
		target_type="Drug",
		min_results=10,
	)

	assert len(results) == 10
	# Only 1 call because tier 1 returned enough
	assert mock_gc.execute_read.await_count == 1


@patch("nexus.graph.abc.graph_client")
async def test_fanout_expands_to_tier2_when_insufficient(mock_gc):
	"""When tier 1 returns < min_results, tier 2 queries run."""
	tier1_records = [
		{
			"a_id": "1", "a_name": "Alzheimer", "a_type": "Disease",
			"c_id": "10", "c_name": "DrugX", "c_type": "Drug",
			"intermediaries": [{"b_id": "10", "b_name": "GeneX", "b_type": "Gene", "ab_rel": "ASSOCIATED_WITH", "bc_rel": "TARGET"}],
			"path_count": 3,
		}
	]
	tier2_records = [
		{
			"a_id": "1", "a_name": "Alzheimer", "a_type": "Disease",
			"c_id": "20", "c_name": "DrugY", "c_type": "Drug",
			"intermediaries": [{"b_id": "20", "b_name": "PathwayZ", "b_type": "Pathway", "ab_rel": "PATHWAY_PROTEIN", "bc_rel": "TARGET"}],
			"path_count": 2,
		}
	]

	call_count = 0

	async def mock_read(query, **params):
		nonlocal call_count
		call_count += 1
		if call_count == 1:
			return tier1_records
		return tier2_records

	mock_gc.execute_read = AsyncMock(side_effect=mock_read)

	results = await find_abc_hypotheses(
		source_name="Alzheimer",
		source_type="Disease",
		target_type="Drug",
		min_results=10,
	)

	assert len(results) >= 2
	# Tier 1 (1 call) + Tier 2 (2 concurrent calls for Pathway, BiologicalProcess)
	assert mock_gc.execute_read.await_count >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/dannyliu/personal_projects/nexus && python -m pytest tests/graph/test_abc_fanout.py -v`
Expected: FAIL (INTERMEDIARY_TIERS not defined, min_results not a parameter)

**Step 3: Implement tiered fan-out**

Modify `backend/src/nexus/graph/abc.py`:

1. Add `INTERMEDIARY_TIERS` constant:
```python
INTERMEDIARY_TIERS: list[list[str]] = [
	["Gene"],
	["Pathway", "BiologicalProcess"],
	["Anatomy", "Phenotype", "MolecularFunction", "CellularComponent"],
]

QUERY_TIMEOUT = 10.0  # seconds per intermediary query
```

2. Add `_query_intermediary_type()` helper that runs one Cypher query for a specific intermediary type label:
```python
async def _query_intermediary_type(
	source_name: str,
	source_type: str,
	intermediary_type: str,
	target_type: str,
	max_results: int,
	exclude_known: bool,
	fuzzy: bool,
	preferred_ab_rels: list[str] | None,
) -> list[dict]:
	"""Run ABC query for a single intermediary type. Returns raw records."""
	# Same Cypher as find_abc_hypotheses but with b:{intermediary_type} label
	# Uses asyncio.wait_for with QUERY_TIMEOUT
```

3. Refactor `find_abc_hypotheses()` to add `min_results: int = 10` parameter:
   - Loop over INTERMEDIARY_TIERS
   - For each tier, run `asyncio.gather(*[_query_intermediary_type(..., itype) for itype in tier])` with `asyncio.wait_for` wrapping each call for timeout
   - Merge records, deduplicate by (a_id, c_id) pair
   - If accumulated results >= min_results, break early
   - Convert merged records to ABCHypothesis list as before

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/graph/test_abc_fanout.py tests/graph/test_abc.py -v`
Expected: PASS

**Step 5: Run existing orchestrator tests**

Run: `python -m pytest tests/pipeline/test_orchestrator.py -v`
Expected: PASS (no breaking changes to find_abc_hypotheses signature)

**Step 6: Commit**

```bash
git add backend/src/nexus/graph/abc.py tests/graph/test_abc_fanout.py
git commit -m "feat: tiered async fan-out for intermediary queries in ABC traversal"
```

---

## Task 2: Bounded Multi-Entity Exploration

When checkpoint returns BRANCH, run up to 3 concurrent lightweight pipeline branches (graph search + scoring only, no literature/reasoning) with 30s timeout per branch.

Currently the orchestrator spawns a full recursive `run_pipeline()` call for BRANCH. Replace with a bounded `_run_branch()` that only does entity resolution + graph search + scoring.

**Files:**
- Modify: `backend/src/nexus/pipeline/orchestrator.py:211-556`
- Modify: `backend/src/nexus/checkpoint/models.py` (add `branch_entities` field)
- Test: `tests/pipeline/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/pipeline/test_orchestrator.py`:

```python
@patch("nexus.pipeline.orchestrator.graph_client")
@patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock)
@patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock)
async def test_run_pipeline_branch_bounded(mock_lit, mock_abc, mock_cp, mock_merge, mock_gc):
	"""BRANCH decision runs lightweight graph-only branches, max 3 concurrent."""
	branch_result = CheckpointResult(
		decision=CheckpointDecision.BRANCH,
		reason="Explore BACE1 and TREM2 in parallel",
		pivot_entity="BACE1",
		pivot_entity_type="Gene",
		branch_entities=[
			{"name": "BACE1", "type": "Gene"},
			{"name": "TREM2", "type": "Gene"},
		],
		confidence=0.85,
	)

	mock_cp.side_effect = [branch_result, CONTINUE_RESULT]
	mock_lit.return_value = MOCK_LIT_RESULT
	mock_abc.return_value = [MOCK_HYPOTHESIS]
	mock_merge.return_value = 2
	mock_gc.resolve_entity_multi = _mock_resolve_multi()

	result = await run_pipeline(
		query="Alzheimer",
		start_entity="Alzheimer",
		target_types=["Compound"],
	)

	assert result.step == PipelineStep.COMPLETED
	assert len(result.branches) >= 1
	# Branch hypotheses merged into main scored_hypotheses
	assert len(result.scored_hypotheses) >= 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/pipeline/test_orchestrator.py::test_run_pipeline_branch_bounded -v`
Expected: FAIL (branch_entities not a field on CheckpointResult)

**Step 3: Add `branch_entities` to CheckpointResult**

Modify `backend/src/nexus/checkpoint/models.py`:

```python
@dataclass
class CheckpointResult:
	decision: CheckpointDecision
	reason: str
	pivot_entity: str | None = None
	pivot_entity_type: str | None = None
	confidence: float = 0.0
	branch_entities: list[dict] | None = None  # [{"name": "X", "type": "Y"}, ...]
```

Update `backend/src/nexus/checkpoint/agent.py` to parse `branch_entities` from the LLM JSON response (lines ~146-155):

```python
return CheckpointResult(
	decision=decision,
	reason=data.get("reason", ""),
	pivot_entity=data.get("pivot_entity"),
	pivot_entity_type=data.get("pivot_entity_type"),
	confidence=float(data.get("confidence", 0.0)),
	branch_entities=data.get("branch_entities"),
)
```

**Step 4: Implement `_run_branch()` and bounded BRANCH handling**

Add to `backend/src/nexus/pipeline/orchestrator.py`:

```python
MAX_CONCURRENT_BRANCHES = 3
BRANCH_TIMEOUT = 30.0  # seconds per branch

async def _run_branch(
	entity_name: str,
	entity_type: str,
	target_types: list[str],
	triples: list[Triple],
	max_hypotheses: int = 10,
) -> list[dict]:
	"""Lightweight branch: entity resolution + graph search + scoring only."""
	candidates = await graph_client.resolve_entity_multi(entity_name, entity_type=entity_type)
	if candidates:
		entity_name = candidates[0].name
		entity_type = candidates[0].type

	all_hypotheses: list[ABCHypothesis] = []
	for target in target_types:
		hyps = await find_abc_hypotheses(
			source_name=entity_name,
			source_type=entity_type,
			target_type=target,
		)
		all_hypotheses.extend(hyps)

	scored = [score_hypothesis(h, triples) for h in all_hypotheses]
	scored.sort(key=lambda h: h.get("overall_score", 0), reverse=True)
	return scored[:max_hypotheses]
```

Then replace the current BRANCH handling (lines ~303-315) in `run_pipeline()`:

```python
elif lit_cp.decision == CheckpointDecision.BRANCH:
	branch_entities_raw = lit_cp.branch_entities or []
	if not branch_entities_raw and lit_cp.pivot_entity:
		branch_entities_raw = [{"name": lit_cp.pivot_entity, "type": lit_cp.pivot_entity_type or start_type}]
	branch_entities_raw = branch_entities_raw[:MAX_CONCURRENT_BRANCHES]

	sem = asyncio.Semaphore(MAX_CONCURRENT_BRANCHES)
	triples_for_branches = lit_result.triples if lit_result else []

	async def bounded_branch(ent: dict) -> list[dict]:
		async with sem:
			return await asyncio.wait_for(
				_run_branch(
					ent["name"], ent.get("type", start_type),
					targets, triples_for_branches,
				),
				timeout=BRANCH_TIMEOUT,
			)

	branch_tasks = [asyncio.create_task(bounded_branch(e)) for e in branch_entities_raw]
	for task in asyncio.as_completed(branch_tasks):
		try:
			branch_scored = await task
			result.branches.append(branch_scored)
			result.scored_hypotheses.extend(branch_scored)
		except (TimeoutError, Exception) as exc:
			result.errors.append(f"Branch failed: {exc}")

	await _emit(on_event, "branch", {
		"entities": [e["name"] for e in branch_entities_raw],
		"reason": lit_cp.reason,
	})
```

Also update the graph-stage BRANCH handling similarly (after line ~420).

**Step 5: Run tests**

Run: `python -m pytest tests/pipeline/test_orchestrator.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/src/nexus/checkpoint/models.py backend/src/nexus/checkpoint/agent.py backend/src/nexus/pipeline/orchestrator.py tests/pipeline/test_orchestrator.py
git commit -m "feat: bounded multi-entity exploration with semaphore + timeout on BRANCH"
```

---

## Task 3: Unify `molecular_dock.py` with TamarindClient

Replace raw httpx upload/submit calls in `molecular_dock.py` with `TamarindClient.upload_file()` and `TamarindClient.submit_job()`. Keep PDB/SDF fetching as-is (those are external APIs, not Tamarind).

**Files:**
- Modify: `backend/src/nexus/tools/molecular_dock.py`
- Test: `tests/tools/test_molecular_dock.py`

**Step 1: Write the failing test**

Create `tests/tools/test_molecular_dock.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from nexus.tools.molecular_dock import molecular_dock


@patch("nexus.tools.molecular_dock._fetch_sdf_for_drug", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock._fetch_pdb_for_gene", new_callable=AsyncMock)
@patch("nexus.tools.molecular_dock.TamarindClient")
async def test_molecular_dock_uses_tamarind_client(mock_client_cls, mock_pdb, mock_sdf):
	"""molecular_dock should use TamarindClient for upload and submit."""
	mock_pdb.return_value = "ATOM 1 CA ALA A 1"
	mock_sdf.return_value = b"fake sdf content"

	mock_instance = AsyncMock()
	mock_instance.upload_file.return_value = "https://tamarind.bio/files/test.pdb"
	mock_instance.submit_job.return_value = "nexus-dock-test"
	mock_client_cls.return_value = mock_instance

	with patch("nexus.tools.molecular_dock.settings") as mock_settings:
		mock_settings.tamarind_bio_api_key = "test-key"
		result = await molecular_dock("Aspirin", "COX2")

	assert result.status == "partial"
	assert mock_instance.upload_file.await_count == 2
	mock_instance.submit_job.assert_awaited_once()


@patch("nexus.tools.molecular_dock.settings")
async def test_molecular_dock_no_api_key(mock_settings):
	"""No API key returns partial with skip message."""
	mock_settings.tamarind_bio_api_key = ""
	result = await molecular_dock("Aspirin", "COX2")
	assert result.status == "partial"
	assert "skipped" in result.summary.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_molecular_dock.py -v`
Expected: FAIL (TamarindClient not imported in molecular_dock.py)

**Step 3: Refactor molecular_dock.py**

Replace raw httpx calls with TamarindClient. Keep `_fetch_pdb_for_gene` and `_fetch_sdf_for_drug` unchanged (they call external APIs):

```python
from __future__ import annotations

import logging
import time

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient

logger = logging.getLogger(__name__)

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"


# _fetch_pdb_for_gene and _fetch_sdf_for_drug stay exactly the same


async def molecular_dock(compound_name: str, protein_name: str) -> ToolResponse:
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Molecular docking skipped for {compound_name} + {protein_name}: no Tamarind Bio API key configured.",
			raw_data={"compound": compound_name, "protein": protein_name, "reason": "missing_api_key"},
		)

	try:
		async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
			pdb_content = await _fetch_pdb_for_gene(protein_name, http_client)
			if not pdb_content:
				return ToolResponse(
					status="partial", confidence_delta=0.0, evidence_type="neutral",
					summary=f"No PDB structure found for {protein_name}. Cannot run docking.",
					raw_data={"protein": protein_name, "reason": "no_pdb_structure"},
				)

			sdf_content = await _fetch_sdf_for_drug(compound_name, http_client)
			if not sdf_content:
				return ToolResponse(
					status="partial", confidence_delta=0.0, evidence_type="neutral",
					summary=f"No SDF found for {compound_name} on PubChem. Cannot run docking.",
					raw_data={"compound": compound_name, "reason": "no_sdf"},
				)

		client = TamarindClient()

		pdb_filename = f"nexus-{protein_name}.pdb".replace(" ", "_")
		await client.upload_file(pdb_filename, pdb_content.encode())

		sdf_filename = f"nexus-{compound_name}.sdf".replace(" ", "_")
		await client.upload_file(sdf_filename, sdf_content)

		ts = int(time.time())
		job_name = f"nexus-dock-{compound_name}-{protein_name}-{ts}".replace(" ", "_")[:64]
		await client.submit_job(job_name, "diffdock", {
			"proteinFile": pdb_filename,
			"ligandFile": sdf_filename,
			"ligandFormat": "sdf/mol2 file",
		})

		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"DiffDock job submitted for {compound_name} + {protein_name}: {job_name}",
			raw_data={"job_name": job_name},
		)

	except Exception as exc:
		logger.warning("Molecular docking error for %s + %s: %s", compound_name, protein_name, exc)
		return ToolResponse(
			status="error", confidence_delta=0.0, evidence_type="neutral",
			summary=f"Molecular docking error: {exc}",
			raw_data={"error": str(exc)},
		)
```

**Step 4: Run tests**

Run: `python -m pytest tests/tools/test_molecular_dock.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/src/nexus/tools/molecular_dock.py tests/tools/test_molecular_dock.py
git commit -m "refactor: unify molecular_dock.py with TamarindClient"
```

---

## Task 4: Add `list_job_types()` to TamarindClient

Add dynamic tool discovery so the pipeline can query available Tamarind Bio job types at runtime.

**Files:**
- Modify: `backend/src/nexus/tools/tamarind_client.py`
- Test: `tests/tools/test_tamarind_client.py`

**Step 1: Write the failing test**

Add to `tests/tools/test_tamarind_client.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from nexus.tools.tamarind_client import TamarindClient


@patch("nexus.tools.tamarind_client.settings")
async def test_list_job_types(mock_settings):
	"""list_job_types returns available job types from the API."""
	mock_settings.tamarind_bio_api_key = "test-key"
	client = TamarindClient(api_key="test-key")

	mock_response = MagicMock()
	mock_response.status_code = 200
	mock_response.json.return_value = {
		"jobTypes": ["diffdock", "esmfold", "autodock_vina", "gnina"]
	}
	mock_response.raise_for_status = MagicMock()

	with patch("httpx.AsyncClient") as mock_http:
		mock_http_instance = AsyncMock()
		mock_http_instance.get = AsyncMock(return_value=mock_response)
		mock_http_instance.__aenter__ = AsyncMock(return_value=mock_http_instance)
		mock_http_instance.__aexit__ = AsyncMock(return_value=False)
		mock_http.return_value = mock_http_instance

		result = await client.list_job_types()

	assert "diffdock" in result
	assert "esmfold" in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tools/test_tamarind_client.py::test_list_job_types -v`
Expected: FAIL (list_job_types not defined)

**Step 3: Implement list_job_types**

Add to `TamarindClient` in `backend/src/nexus/tools/tamarind_client.py`:

```python
async def list_job_types(self) -> list[str]:
	"""Fetch available job types from the Tamarind Bio API."""
	async with httpx.AsyncClient(timeout=30.0) as client:
		resp = await client.get(
			f"{self._base_url}/job-types",
			headers=self._headers,
		)
		resp.raise_for_status()
		data = resp.json()
		return data.get("jobTypes", [])
```

**Step 4: Run test**

Run: `python -m pytest tests/tools/test_tamarind_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/nexus/tools/tamarind_client.py tests/tools/test_tamarind_client.py
git commit -m "feat: add list_job_types() to TamarindClient for dynamic tool discovery"
```

---

## Task 5: Full Verification

Run the complete test suite, linter, and type checker to verify nothing is broken.

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

**Step 2: Run linter**

Run: `ruff check backend/ tests/`
Expected: Clean

**Step 3: Run type checker**

Run: `mypy backend/src/nexus/`
Expected: Clean (or only pre-existing issues)

**Step 4: Commit and push**

```bash
git push origin dev
```
