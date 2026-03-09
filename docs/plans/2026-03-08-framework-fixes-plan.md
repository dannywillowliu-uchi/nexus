# Framework Performance Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 issues degrading hypothesis quality: relationship weight mismatches, fragile section parsing, empty validation maps, disconnected validation scores, and silent input failures.

**Architecture:** Targeted fixes across the scoring pipeline (`graph/abc.py`), reasoning agent (`agents/reasoning_agent.py`), validation planner (`tools/validation_planner.py`, `tools/tamarind_tools.py`), and orchestrator (`pipeline/orchestrator.py`). Each fix is independent and can be tested in isolation.

**Tech Stack:** Python, pytest, pytest-asyncio

---

### Task 1: Relationship Weight Alias Map

**Files:**
- Modify: `backend/src/nexus/graph/abc.py:39-96`
- Modify: `tests/graph/test_abc.py:88-183`

**Step 1: Update the test for rel_weight to use PrimeKG labels and test aliases**

In `tests/graph/test_abc.py`, replace `test_rel_weight_known` with:

```python
def test_rel_weight_known():
	"""Known PrimeKG relationship types should return their assigned weights."""
	assert rel_weight("INDICATION") == 1.0
	assert rel_weight("TARGET") == 1.0
	assert rel_weight("ASSOCIATED_WITH") == 0.85
	assert rel_weight("PROTEIN_PROTEIN") == 0.8
	assert rel_weight("BIOPROCESS_PROTEIN") == 0.7


def test_rel_weight_aliases():
	"""Old Hetionet labels should resolve via alias map."""
	assert rel_weight("TREATS_CtD") == 1.0  # -> INDICATION
	assert rel_weight("BINDS_CbG") == 1.0  # -> TARGET
	assert rel_weight("ASSOCIATES_DaG") == 0.85  # -> ASSOCIATED_WITH
	assert rel_weight("INTERACTS_GiG") == 0.8  # -> PROTEIN_PROTEIN
	assert rel_weight("DOWNREGULATES_CdG") == 1.0  # -> TARGET
	assert rel_weight("PARTICIPATES_GpBP") == 0.7  # -> BIOPROCESS_PROTEIN
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/graph/test_abc.py::test_rel_weight_known tests/graph/test_abc.py::test_rel_weight_aliases -v`
Expected: FAIL (test_rel_weight_aliases doesn't exist yet, test_rel_weight_known assertions changed)

**Step 3: Add the alias map and update rel_weight in abc.py**

In `backend/src/nexus/graph/abc.py`, after the `RELATIONSHIP_WEIGHTS` dict (after line 68), add:

```python
RELATIONSHIP_ALIASES: dict[str, str] = {
	"TREATS_CtD": "INDICATION",
	"PALLIATES_CpD": "INDICATION",
	"BINDS_CbG": "TARGET",
	"ASSOCIATES_DaG": "ASSOCIATED_WITH",
	"DOWNREGULATES_CdG": "TARGET",
	"UPREGULATES_CuG": "TARGET",
	"RESEMBLES_DrD": "ASSOCIATED_WITH",
	"INCLUDES_PCiC": "CELLCOMP_PROTEIN",
	"PARTICIPATES_GpPW": "PATHWAY_PROTEIN",
	"PARTICIPATES_GpBP": "BIOPROCESS_PROTEIN",
	"PARTICIPATES_GpMF": "MOLFUNC_PROTEIN",
	"LOCALIZES_DlA": "ANATOMY_PROTEIN_PRESENT",
	"PRESENTS_DpS": "PHENOTYPE_PRESENT",
	"INTERACTS_GiG": "PROTEIN_PROTEIN",
	"COVARIES_GcG": "PROTEIN_PROTEIN",
	"ASSOCIATES_GaD": "ASSOCIATED_WITH",
}
```

Then update `rel_weight`:

```python
def rel_weight(rel_type: str) -> float:
	"""Return the weight for a relationship type, checking aliases for old Hetionet labels."""
	canonical = RELATIONSHIP_ALIASES.get(rel_type, rel_type)
	return RELATIONSHIP_WEIGHTS.get(canonical, 0.5)
```

**Step 4: Update mock records in test_abc.py to use PrimeKG labels**

In `tests/graph/test_abc.py`, update `_make_mock_records`:

```python
def _make_mock_records(source_type="Disease", target_type="Compound"):
	"""Build realistic mock records for ABC traversal results."""
	return [
		{
			"a_id": "DOID:1234",
			"a_name": "multiple sclerosis",
			"a_type": source_type,
			"c_id": "DB00123",
			"c_name": "Methotrexate",
			"c_type": target_type,
			"intermediaries": [
				{
					"b_id": "GENE:5678",
					"b_name": "TNF",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATED_WITH",
					"bc_rel": "TARGET",
				},
				{
					"b_id": "GENE:9999",
					"b_name": "IL6",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATED_WITH",
					"bc_rel": "TARGET",
				},
			],
			"path_count": 2,
		},
		{
			"a_id": "DOID:1234",
			"a_name": "multiple sclerosis",
			"a_type": source_type,
			"c_id": "DB00456",
			"c_name": "Rituximab",
			"c_type": target_type,
			"intermediaries": [
				{
					"b_id": "GENE:1111",
					"b_name": "CD20",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATED_WITH",
					"bc_rel": "INDICATION",
				},
			],
			"path_count": 1,
		},
	]
```

Update `test_find_abc_hypotheses_disease_to_compound` assertions:

```python
	# ASSOCIATED_WITH(0.85) * TARGET(1.0) -> sqrt(0.85) * Gene(1.5) ~ 1.383
	assert h0.b_name == "TNF"
	assert h0.path_strength > 1.3
```

Update `test_find_abc_hypotheses_gene_source` mock to use PrimeKG labels:

```python
	mock_records = [
		{
			"a_id": "GENE:5678",
			"a_name": "TNF",
			"a_type": "Gene",
			"c_id": "DB00789",
			"c_name": "Infliximab",
			"c_type": "Compound",
			"intermediaries": [
				{
					"b_id": "DOID:4567",
					"b_name": "rheumatoid arthritis",
					"b_type": "Disease",
					"ab_rel": "ASSOCIATED_WITH",
					"bc_rel": "INDICATION",
				},
			],
			"path_count": 1,
		},
	]
```

**Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/graph/test_abc.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/src/nexus/graph/abc.py tests/graph/test_abc.py
git commit -m "fix: add relationship alias map for Hetionet->PrimeKG label compat"
```

---

### Task 2: Fuzzy Section Header Matching

**Files:**
- Modify: `backend/src/nexus/agents/reasoning_agent.py:313-345`
- Modify: `tests/agents/test_reasoning_agent.py:62-171`

**Step 1: Update the test mock to return a realistic narrative**

In `tests/agents/test_reasoning_agent.py`, replace `MOCK_BRIEF_JSON` with a narrative-format mock and update the test:

```python
MOCK_NARRATIVE = """## 1. BIOLOGICAL PLAUSIBILITY

Diabetes is linked to PPARG through genetic association, and Metformin targets PPARG directly. PPARG is a nuclear receptor that regulates fatty acid storage and glucose metabolism. When activated by thiazolidinediones or similar ligands, it enhances insulin sensitivity.

## 2. STRENGTH OF EVIDENCE

Multiple papers support the PPARG-diabetes association. The strongest evidence comes from GWAS studies linking PPARG variants to T2D risk. The drug-gene link through direct binding is well-established pharmacologically.

## 3. WHAT A RESEARCHER WOULD DO FIRST

In vitro binding assay of Metformin to PPARG followed by glucose uptake measurement. Use HepG2 cells for hepatic context, treat with 1-10mM Metformin, measure PPARG transactivation via luciferase reporter.

## 4. WHY THIS MIGHT FAIL

Metformin's primary mechanism is through AMPK, not PPARG. The binding affinity may be too low to be clinically relevant. Off-target effects could confound results.

## 5. CLINICAL SIGNIFICANCE

Type 2 diabetes affects 462 million people worldwide. Current treatments have limitations including weight gain and cardiovascular risk. If Metformin acts through PPARG, it could explain differential responses in patients with PPARG polymorphisms."""
```

Then update `test_generate_research_brief`:

```python
@pytest.mark.asyncio
@patch("nexus.agents.reasoning_agent.settings")
@patch("nexus.agents.reasoning_agent.anthropic.AsyncAnthropic")
async def test_generate_research_brief(mock_anthropic_cls, mock_settings):
	mock_settings.anthropic_api_key = "test-key"

	# First call returns narrative, second call returns scores
	mock_narrative_block = AsyncMock()
	mock_narrative_block.text = MOCK_NARRATIVE

	mock_score_block = AsyncMock()
	mock_score_block.text = json.dumps({
		"graph_evidence": 0.87,
		"graph_reasoning": "Multiple paths through PPARG.",
		"literature_support": 0.78,
		"literature_reasoning": "Several papers support the association.",
		"biological_plausibility": 0.9,
		"plausibility_reasoning": "PPARG is a well-known metabolic regulator.",
		"novelty": 0.6,
		"novelty_reasoning": "The association is known but mechanism is less explored.",
	})

	mock_narrative_msg = AsyncMock()
	mock_narrative_msg.content = [mock_narrative_block]

	mock_score_msg = AsyncMock()
	mock_score_msg.content = [mock_score_block]

	mock_client = AsyncMock()
	mock_client.messages.create = AsyncMock(side_effect=[mock_narrative_msg, mock_score_msg])
	mock_anthropic_cls.return_value = mock_client

	hypothesis = _make_hypothesis()
	papers = [
		{
			"paper_id": "paper1",
			"title": "PPARG in Diabetes",
			"abstract": "PPARG variants are strongly associated with type 2 diabetes.",
		},
	]

	brief = await generate_research_brief(hypothesis, MOCK_TRIPLES, papers)

	assert brief.hypothesis_title == "Diabetes -> PPARG -> Metformin"
	assert "PPARG" in brief.connection_explanation
	assert brief.confidence.graph_evidence == 0.87
	assert brief.confidence.literature_support == 0.78
	assert brief.confidence.biological_plausibility == 0.9
	assert brief.confidence.novelty == 0.6
	assert "binding assay" in brief.suggested_validation.lower()
	assert brief.researcher_narrative == MOCK_NARRATIVE

	assert mock_client.messages.create.call_count == 2
	# First call is researcher reasoning (Sonnet, 4096 tokens)
	first_call = mock_client.messages.create.call_args_list[0].kwargs
	assert first_call["model"] == "claude-sonnet-4-20250514"
	assert first_call["max_tokens"] == 4096
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/agents/test_reasoning_agent.py::test_generate_research_brief -v`
Expected: FAIL (section extraction won't match `## 1. BIOLOGICAL PLAUSIBILITY`)

**Step 3: Update _extract_sections for fuzzy matching**

In `backend/src/nexus/agents/reasoning_agent.py`, replace `_extract_sections`:

```python
import re

def _extract_sections(narrative: str) -> dict[str, str]:
	"""Extract named sections from the researcher narrative.

	Handles variations like '## 1. BIOLOGICAL PLAUSIBILITY', '**Biological Plausibility**',
	'1) biological plausibility', etc.
	"""
	section_headers = [
		"BIOLOGICAL PLAUSIBILITY",
		"STRENGTH OF EVIDENCE",
		"WHAT A RESEARCHER WOULD DO FIRST",
		"WHY THIS MIGHT FAIL",
		"CLINICAL SIGNIFICANCE",
	]
	sections: dict[str, str] = {}
	lines = narrative.split("\n")
	current_key = ""
	current_lines: list[str] = []

	for line in lines:
		# Normalize: strip markdown markers, numbers, punctuation
		normalized = re.sub(r"^[\s#*\d.\-–—)]+", "", line).strip().upper()
		matched = False
		for header in section_headers:
			if header in normalized:
				if current_key:
					sections[current_key] = "\n".join(current_lines).strip()
				current_key = header.lower().replace(" ", "_")
				current_lines = []
				matched = True
				break
		if not matched and current_key:
			current_lines.append(line)

	if current_key:
		sections[current_key] = "\n".join(current_lines).strip()

	return sections
```

Note: add `import re` at the top of the file if not already present.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/agents/test_reasoning_agent.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/src/nexus/agents/reasoning_agent.py tests/agents/test_reasoning_agent.py
git commit -m "fix: make section extraction resilient to markdown formatting variations"
```

---

### Task 3: Comorbidity/Connection Tool Maps

**Files:**
- Modify: `backend/src/nexus/tools/tamarind_tools.py:203-224`
- Modify: `tests/tools/test_tamarind_tools.py:75-84`
- Modify: `tests/tools/test_validation_planner.py:279-293`

**Step 1: Update the test expectations**

In `tests/tools/test_tamarind_tools.py`, update:

```python
def test_get_tools_for_comorbidity():
	"""comorbidity returns gene-focused analysis tools."""
	tools = get_tools_for_hypothesis("comorbidity")
	tool_types = [t.tool_type for t in tools]
	assert "esmfold" in tool_types
	assert "deepfri" in tool_types
	assert "temstapro" in tool_types


def test_get_tools_for_connection():
	"""connection returns best-effort tools based on available inputs."""
	tools = get_tools_for_hypothesis("connection")
	tool_types = [t.tool_type for t in tools]
	assert "admet" in tool_types
	assert "esmfold" in tool_types
```

In `tests/tools/test_validation_planner.py`, update `test_run_validation_plan_comorbidity_empty`:

```python
@pytest.mark.asyncio
async def test_run_validation_plan_comorbidity():
	"""comorbidity with gene intermediary runs gene-focused tools."""
	hypothesis = {
		"hypothesis_type": "comorbidity",
		"abc_path": {
			"a": {"name": "diabetes", "type": "Disease"},
			"b": {"name": "IL6", "type": "Gene"},
			"c": {"name": "CVD", "type": "Disease"},
		},
	}

	mock_run_job = AsyncMock(return_value={
		"status": "Complete",
		"result": {"plddt_score": 88.0},
	})

	with patch("nexus.tools.validation_planner._fetch_pdb_for_gene", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_sdf_for_drug", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_smiles_for_drug", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_sequence_for_gene", new_callable=AsyncMock, return_value="MKKLTFFF"), \
		 patch("nexus.tools.validation_planner.TamarindClient") as MockClient:
		instance = MockClient.return_value
		instance.run_job = mock_run_job

		from nexus.tools.validation_planner import run_validation_plan
		results = await run_validation_plan(hypothesis)

	assert len(results) > 0
	for r in results:
		assert isinstance(r, ToolResponse)
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/tools/test_tamarind_tools.py::test_get_tools_for_comorbidity tests/tools/test_tamarind_tools.py::test_get_tools_for_connection tests/tools/test_validation_planner.py::test_run_validation_plan_comorbidity -v`
Expected: FAIL

**Step 3: Update the tool maps**

In `backend/src/nexus/tools/tamarind_tools.py`, update `HYPOTHESIS_TOOL_MAP`:

```python
HYPOTHESIS_TOOL_MAP: dict[str, list[str]] = {
	"drug_repurposing": [
		"diffdock", "gnina", "autodock_vina",
		"admet",
		"af2bind",
	],
	"target_discovery": [
		"esmfold",
		"deepfri",
		"temstapro",
		"netsolp",
	],
	"mechanism": [
		"deepfri",
	],
	"drug_interaction": [
		"admet",
		"aqueous-solubility",
	],
	"comorbidity": [
		"esmfold",
		"deepfri",
		"temstapro",
	],
	"connection": [
		"admet",
		"esmfold",
	],
}
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/tools/test_tamarind_tools.py tests/tools/test_validation_planner.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/src/nexus/tools/tamarind_tools.py tests/tools/test_tamarind_tools.py tests/tools/test_validation_planner.py
git commit -m "feat: add validation tools for comorbidity and connection hypothesis types"
```

---

### Task 4: Post-Validation Re-ranking

**Files:**
- Modify: `backend/src/nexus/pipeline/orchestrator.py:659-691`
- Modify: `tests/pipeline/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/pipeline/test_orchestrator.py`:

```python
@pytest.mark.asyncio
async def test_run_pipeline_validation_reranks():
	"""Validation results feed back into overall_score and re-rank hypotheses."""
	hyp_strong = ABCHypothesis(
		a_id="D1", a_name="RA", a_type="Disease",
		b_id="G1", b_name="TNF", b_type="Gene",
		c_id="C1", c_name="Drug1", c_type="Drug",
		ab_relationship="ASSOCIATED_WITH", bc_relationship="TARGET",
		path_count=3, novelty_score=0.7, path_strength=0.5,
	)
	hyp_weak = ABCHypothesis(
		a_id="D1", a_name="RA", a_type="Disease",
		b_id="G2", b_name="IL6", b_type="Gene",
		c_id="C2", c_name="Drug2", c_type="Drug",
		ab_relationship="ASSOCIATED_WITH", bc_relationship="TARGET",
		path_count=5, novelty_score=0.9, path_strength=0.8,
	)

	with patch("nexus.pipeline.orchestrator.run_literature_agent", new_callable=AsyncMock) as mock_lit, \
		 patch("nexus.pipeline.orchestrator.graph_client") as mock_graph, \
		 patch("nexus.pipeline.orchestrator.run_checkpoint", new_callable=AsyncMock) as mock_cp, \
		 patch("nexus.pipeline.orchestrator.find_abc_hypotheses", new_callable=AsyncMock) as mock_abc, \
		 patch("nexus.pipeline.orchestrator.generate_quick_summaries", new_callable=AsyncMock) as mock_sum, \
		 patch("nexus.pipeline.orchestrator.generate_research_brief", new_callable=AsyncMock) as mock_brief, \
		 patch("nexus.pipeline.orchestrator.run_validation_plan", new_callable=AsyncMock) as mock_validate, \
		 patch("nexus.pipeline.orchestrator.merge_triples_to_graph", new_callable=AsyncMock) as mock_merge:

		mock_lit.return_value = LiteratureResult(papers=[], triples=[], errors=[])
		mock_cp.return_value = CheckpointResult(
			decision=CheckpointDecision.CONTINUE, reason="ok", confidence=0.8,
		)
		mock_graph.resolve_entity_multi = AsyncMock(return_value=[])
		mock_merge.return_value = 0

		# hyp_weak has higher base score, hyp_strong has lower base score
		mock_abc.return_value = [hyp_weak, hyp_strong]
		mock_sum.return_value = ["s1", "s2"]
		mock_brief.side_effect = Exception("skip")

		# hyp_strong (Drug1) gets great validation, hyp_weak (Drug2) gets bad validation
		async def validation_side_effect(hypothesis):
			if hypothesis.get("title", "").endswith("Drug1"):
				return [ToolResponse(
					status="success", confidence_delta=0.5,
					evidence_type="supporting", summary="strong docking",
					raw_data={"tool_type": "diffdock"},
				)]
			else:
				return [ToolResponse(
					status="success", confidence_delta=-0.1,
					evidence_type="contradicting", summary="weak docking",
					raw_data={"tool_type": "diffdock"},
				)]

		mock_validate.side_effect = validation_side_effect

		result = await run_pipeline("test", start_entity="RA", start_type="Disease")

	# After re-ranking, both should have pre_validation_score and updated overall_score
	for sh in result.scored_hypotheses:
		assert "pre_validation_score" in sh

	# hyp_strong (Drug1) should now rank higher despite lower base score
	# because validation gave it +0.5 delta
	drug1 = next(sh for sh in result.scored_hypotheses if "Drug1" in sh["title"])
	drug2 = next(sh for sh in result.scored_hypotheses if "Drug2" in sh["title"])
	assert drug1["overall_score"] > drug2["overall_score"]
	assert drug1["pre_validation_score"] < drug2["pre_validation_score"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/pipeline/test_orchestrator.py::test_run_pipeline_validation_reranks -v`
Expected: FAIL (`pre_validation_score` not in hypothesis dicts)

**Step 3: Add post-validation re-ranking in the orchestrator**

In `backend/src/nexus/pipeline/orchestrator.py`, after the validation gather loop (after the existing line `result.scored_hypotheses[i]["validations"].append(entry)`), before `await _emit(on_event, "stage_complete", {"stage": "validation",...})`, add:

```python
		# --- Post-validation re-ranking ---
		for sh in result.scored_hypotheses:
			validations = sh.get("validations", [])
			if validations:
				avg_delta = sum(v["confidence_delta"] for v in validations) / len(validations)
			else:
				avg_delta = 0.0
			sh["pre_validation_score"] = sh["overall_score"]
			sh["validation_boost"] = round(avg_delta, 4)
			sh["overall_score"] = round(sh["overall_score"] * 0.8 + avg_delta * 0.2, 4)

		result.scored_hypotheses.sort(key=lambda h: h.get("overall_score", 0), reverse=True)
```

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/pipeline/test_orchestrator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/src/nexus/pipeline/orchestrator.py tests/pipeline/test_orchestrator.py
git commit -m "feat: re-rank hypotheses after validation using confidence deltas"
```

---

### Task 5: Input Resolution Reporting

**Files:**
- Modify: `backend/src/nexus/tools/validation_planner.py:323-491`
- Modify: `tests/tools/test_validation_planner.py`

**Step 1: Write the failing test**

Add to `tests/tools/test_validation_planner.py`:

```python
@pytest.mark.asyncio
async def test_run_validation_plan_reports_skipped_tools():
	"""When input resolution fails, skipped tools include specific reasons."""
	hypothesis = {
		"hypothesis_type": "drug_repurposing",
		"abc_path": {
			"a": {"name": "UnknownDrug", "type": "Drug"},
			"b": {"name": "UnknownGene", "type": "Gene"},
			"c": {"name": "SomeDisease", "type": "Disease"},
		},
	}

	# All input fetches fail
	with patch("nexus.tools.validation_planner._fetch_pdb_for_gene", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_sdf_for_drug", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_smiles_for_drug", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_sequence_for_gene", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner.TamarindClient") as MockClient:
		instance = MockClient.return_value
		instance.run_job = AsyncMock()

		from nexus.tools.validation_planner import run_validation_plan
		results = await run_validation_plan(hypothesis)

	# Should have a partial result explaining what failed
	assert len(results) >= 1
	summaries = " ".join(r.summary for r in results)
	# Should mention specific inputs that failed, not just generic "missing inputs"
	assert "pdb" in summaries.lower() or "sdf" in summaries.lower() or "smiles" in summaries.lower()


@pytest.mark.asyncio
async def test_resolve_inputs_returns_report():
	"""_resolve_inputs returns an input resolution report as second value."""
	with patch("nexus.tools.validation_planner._fetch_pdb_for_gene", new_callable=AsyncMock, return_value="ATOM ..."), \
		 patch("nexus.tools.validation_planner._fetch_sdf_for_drug", new_callable=AsyncMock, return_value=None), \
		 patch("nexus.tools.validation_planner._fetch_smiles_for_drug", new_callable=AsyncMock, return_value="CCO"), \
		 patch("nexus.tools.validation_planner._fetch_sequence_for_gene", new_callable=AsyncMock, return_value="MKKLT"):

		from nexus.tools.validation_planner import _resolve_inputs
		inputs, report = await _resolve_inputs({
			"hypothesis_type": "drug_repurposing",
			"abc_path": {
				"a": {"name": "Aspirin", "type": "Drug"},
				"b": {"name": "COX2", "type": "Gene"},
				"c": {"name": "Pain", "type": "Disease"},
			},
		})

	assert report["pdb"] == "fetched"
	assert report["sdf"] == "failed"
	assert report["smiles"] == "fetched"
	assert report["sequence"] == "fetched"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tests/tools/test_validation_planner.py::test_run_validation_plan_reports_skipped_tools tests/tools/test_validation_planner.py::test_resolve_inputs_returns_report -v`
Expected: FAIL

**Step 3: Update _resolve_inputs to return a report**

In `backend/src/nexus/tools/validation_planner.py`, update `_resolve_inputs`:

```python
async def _resolve_inputs(hypothesis: dict) -> tuple[HypothesisInputs, dict[str, str]]:
	"""Extract and fetch all needed inputs from a scored hypothesis dict.

	Returns (inputs, report) where report maps input names to status.
	"""
	abc_path = hypothesis.get("abc_path", {})
	a = abc_path.get("a", {})
	b = abc_path.get("b", {})
	c = abc_path.get("c", {})
	h_type = hypothesis.get("hypothesis_type", "connection")

	inputs = HypothesisInputs(hypothesis_type=h_type)
	report: dict[str, str] = {}

	drug_entity = None
	protein_entity = None

	for entity in [a, b, c]:
		etype = entity.get("type", "").lower()
		if etype in ("drug", "compound"):
			if drug_entity is None:
				drug_entity = entity
			else:
				inputs.drug_name_2 = entity.get("name")
		elif etype in ("gene", "protein"):
			if protein_entity is None:
				protein_entity = entity

	tasks = {}
	if drug_entity:
		inputs.drug_name = drug_entity.get("name")
		tasks["sdf"] = _fetch_sdf_for_drug(inputs.drug_name)
		tasks["smiles"] = _fetch_smiles_for_drug(inputs.drug_name)
	if protein_entity:
		inputs.protein_name = protein_entity.get("name")
		tasks["pdb"] = _fetch_pdb_for_gene(inputs.protein_name)
		tasks["sequence"] = _fetch_sequence_for_gene(inputs.protein_name)

	if inputs.drug_name_2:
		tasks["smiles_2"] = _fetch_smiles_for_drug(inputs.drug_name_2)

	if tasks:
		keys = list(tasks.keys())
		results = await asyncio.gather(*tasks.values(), return_exceptions=True)
		for key, result in zip(keys, results):
			if isinstance(result, Exception):
				report[key] = "failed"
				continue
			if result:
				report[key] = "fetched"
				if key == "sdf":
					inputs._sdf_content = result
				elif key == "smiles":
					inputs.drug_smiles = result
				elif key == "pdb":
					inputs._pdb_content = result
				elif key == "sequence":
					inputs.protein_sequence = result
				elif key == "smiles_2":
					inputs.drug_smiles_2 = result
			else:
				report[key] = "failed"

	return inputs, report
```

**Step 4: Update run_validation_plan to use the report**

In `run_validation_plan`, update the `_resolve_inputs` call and the "no tools" fallback:

```python
	inputs, input_report = await _resolve_inputs(hypothesis)

	client = TamarindClient()
	await _upload_files(inputs, client)

	jobs_to_run: list[tuple[str, dict]] = []
	skipped_tools: list[str] = []
	for cfg in tool_configs:
		job_settings = build_job_settings(cfg.tool_type, inputs)
		if job_settings is not None:
			jobs_to_run.append((cfg.tool_type, job_settings))
		else:
			# Determine which input was missing
			failed_inputs = [k for k, v in input_report.items() if v == "failed"]
			skipped_tools.append(
				f"{cfg.tool_type} skipped: missing {', '.join(failed_inputs) if failed_inputs else cfg.input_type.value} input"
			)

	results: list[ToolResponse] = []

	if skipped_tools:
		results.append(ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Skipped tools: {'; '.join(skipped_tools)}",
			raw_data={"skipped": skipped_tools, "input_report": input_report},
		))

	if not jobs_to_run:
		if not results:
			results.append(ToolResponse(
				status="partial",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"No tools could run for {h_type}: all inputs failed ({input_report})",
				raw_data={"hypothesis_type": h_type, "input_report": input_report},
			))
		return results
```

Then update the end of the function to append job results to the existing `results` list:

```python
	job_tasks = [_run_single(tool_type, tool_settings) for tool_type, tool_settings in jobs_to_run]
	job_results = await asyncio.gather(*job_tasks)
	results.extend(job_results)
	return results
```

**Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tests/tools/test_validation_planner.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/src/nexus/tools/validation_planner.py tests/tools/test_validation_planner.py
git commit -m "feat: report specific input resolution failures in validation output"
```

---

### Task 6: Run full test suite and verify

**Step 1: Run all tests**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass (209+ tests, 0 failures)

**Step 2: Run linter**

Run: `source .venv/bin/activate && ruff check backend/ tests/`
Expected: No errors

**Step 3: Push**

```bash
git push origin dev
git checkout main && git merge dev --no-edit && git push origin main
```
