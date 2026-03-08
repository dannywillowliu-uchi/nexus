from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_tools import InputType
from nexus.tools.validation_planner import (
	build_job_settings,
	HypothesisInputs,
)


def test_hypothesis_inputs_dataclass():
	"""HypothesisInputs stores all possible input data."""
	inputs = HypothesisInputs(
		drug_name="Fostamatinib",
		drug_smiles="C1=CC(=CC(=C1)OC)NC2=NC=C(C(=N2)NC3=CC=C(C=C3)N4CCNCC4)F",
		protein_name="IRAK1",
		protein_sequence="MKKLT...",
		protein_pdb_file="nexus-IRAK1.pdb",
		ligand_file="nexus-Fostamatinib.sdf",
		hypothesis_type="drug_repurposing",
	)
	assert inputs.drug_name == "Fostamatinib"
	assert inputs.protein_name == "IRAK1"


def test_build_job_settings_diffdock():
	"""DiffDock needs proteinFile + ligandFile + ligandFormat."""
	inputs = HypothesisInputs(
		protein_pdb_file="protein.pdb",
		ligand_file="ligand.sdf",
		hypothesis_type="drug_repurposing",
	)
	settings = build_job_settings("diffdock", inputs)
	assert settings["proteinFile"] == "protein.pdb"
	assert settings["ligandFile"] == "ligand.sdf"
	assert settings["ligandFormat"] == "sdf/mol2 file"


def test_build_job_settings_admet():
	"""ADMET needs smilesStrings list."""
	inputs = HypothesisInputs(
		drug_smiles="CCO",
		hypothesis_type="drug_repurposing",
	)
	settings = build_job_settings("admet", inputs)
	assert settings["smilesStrings"] == ["CCO"]


def test_build_job_settings_esmfold():
	"""ESMFold needs sequence."""
	inputs = HypothesisInputs(
		protein_sequence="MKKLT",
		hypothesis_type="target_discovery",
	)
	settings = build_job_settings("esmfold", inputs)
	assert settings["sequence"] == "MKKLT"


def test_build_job_settings_deepfri():
	"""DeepFRI needs task + sequence + ontology."""
	inputs = HypothesisInputs(
		protein_sequence="MKKLT",
		hypothesis_type="mechanism",
	)
	settings = build_job_settings("deepfri", inputs)
	assert settings["task"] == "sequence"
	assert settings["sequence"] == "MKKLT"
	assert "mf" in settings["ontology"]


def test_build_job_settings_gnina():
	"""GNINA needs proteinFile + ligandFile + box params."""
	inputs = HypothesisInputs(
		protein_pdb_file="protein.pdb",
		ligand_file="ligand.sdf",
		hypothesis_type="drug_repurposing",
	)
	settings = build_job_settings("gnina", inputs)
	assert settings["proteinFile"] == "protein.pdb"
	assert settings["ligandFile"] == "ligand.sdf"
	assert "wholeProtein" in settings


def test_build_job_settings_missing_inputs():
	"""Returns None when required inputs are missing."""
	inputs = HypothesisInputs(hypothesis_type="drug_repurposing")
	settings = build_job_settings("diffdock", inputs)
	assert settings is None


def test_build_job_settings_af2bind():
	"""AF2BIND needs pdbFile + chain."""
	inputs = HypothesisInputs(
		protein_pdb_file="protein.pdb",
		hypothesis_type="drug_repurposing",
	)
	settings = build_job_settings("af2bind", inputs)
	assert settings["pdbFile"] == "protein.pdb"
	assert settings["chain"] == "A"


def test_build_job_settings_aqueous_solubility():
	"""Aqueous solubility needs smiles."""
	inputs = HypothesisInputs(
		drug_smiles="CCO",
		hypothesis_type="drug_interaction",
	)
	settings = build_job_settings("aqueous-solubility", inputs)
	assert settings["smiles"] == "CCO"


from nexus.tools.validation_planner import score_tool_result


def test_score_docking_strong_binding():
	"""Docking score < -7.0 is strong supporting evidence."""
	delta, etype = score_tool_result("diffdock", {"docking_score": -8.5})
	assert delta >= 0.4
	assert etype == "supporting"


def test_score_docking_moderate_binding():
	"""Docking score between -7.0 and -5.0 is moderate."""
	delta, etype = score_tool_result("gnina", {"docking_score": -6.0})
	assert 0.2 <= delta <= 0.4
	assert etype == "supporting"


def test_score_docking_weak_binding():
	"""Docking score between -5.0 and -3.0 is neutral."""
	delta, etype = score_tool_result("autodock_vina", {"docking_score": -4.0})
	assert delta <= 0.15
	assert etype == "neutral"


def test_score_docking_no_binding():
	"""Docking score > -3.0 is contradicting."""
	delta, etype = score_tool_result("diffdock", {"docking_score": -1.0})
	assert delta < 0
	assert etype == "contradicting"


def test_score_admet_favorable():
	"""ADMET with good drug-likeness properties is supporting."""
	delta, etype = score_tool_result("admet", {"predictions": [{"druglikeness": 0.8}]})
	assert delta > 0
	assert etype == "supporting"


def test_score_structure_high_plddt():
	"""Structure with pLDDT >= 90 is strong supporting."""
	delta, etype = score_tool_result("esmfold", {"plddt_score": 92.0})
	assert delta >= 0.3
	assert etype == "supporting"


def test_score_structure_low_plddt():
	"""Structure with pLDDT < 50 is contradicting."""
	delta, etype = score_tool_result("alphafold", {"plddt_score": 35.0})
	assert delta < 0
	assert etype == "contradicting"


def test_score_unknown_tool():
	"""Unknown tool returns neutral defaults."""
	delta, etype = score_tool_result("unknown_tool", {"foo": "bar"})
	assert delta == 0.1
	assert etype == "neutral"


def test_score_deepfri_function():
	"""DeepFRI with high-confidence predictions is supporting."""
	delta, etype = score_tool_result("deepfri", {
		"predictions": [{"term": "GO:0005515", "score": 0.9, "name": "protein binding"}]
	})
	assert delta > 0
	assert etype == "supporting"


def test_score_temstapro():
	"""TemStaPro thermostability prediction."""
	delta, etype = score_tool_result("temstapro", {"thermostable": True})
	assert delta > 0
	assert etype == "supporting"


@pytest.mark.asyncio
async def test_run_validation_plan_drug_repurposing():
	"""drug_repurposing hypothesis runs docking + ADMET in parallel."""
	hypothesis = {
		"hypothesis_type": "drug_repurposing",
		"abc_path": {
			"a": {"name": "Fostamatinib", "type": "Drug"},
			"b": {"name": "IRAK1", "type": "Gene"},
			"c": {"name": "rheumatoid arthritis", "type": "Disease"},
		},
	}

	mock_run_job = AsyncMock(return_value={
		"status": "Complete",
		"result": {"docking_score": -7.5},
	})

	with patch("nexus.tools.validation_planner._fetch_pdb_for_gene", new_callable=AsyncMock, return_value="ATOM ...") as mock_pdb, \
		 patch("nexus.tools.validation_planner._fetch_sdf_for_drug", new_callable=AsyncMock, return_value=b"SDF...") as mock_sdf, \
		 patch("nexus.tools.validation_planner._fetch_smiles_for_drug", new_callable=AsyncMock, return_value="CCO") as mock_smiles, \
		 patch("nexus.tools.validation_planner._fetch_sequence_for_gene", new_callable=AsyncMock, return_value="MKKLT") as mock_seq, \
		 patch("nexus.tools.validation_planner.TamarindClient") as MockClient:
		instance = MockClient.return_value
		instance.upload_file = AsyncMock(return_value="uploaded.pdb")
		instance.run_job = mock_run_job

		from nexus.tools.validation_planner import run_validation_plan
		results = await run_validation_plan(hypothesis)

	assert len(results) > 0
	for r in results:
		assert isinstance(r, ToolResponse)


@pytest.mark.asyncio
async def test_run_validation_plan_target_discovery():
	"""target_discovery hypothesis runs structure + function prediction."""
	hypothesis = {
		"hypothesis_type": "target_discovery",
		"abc_path": {
			"a": {"name": "rheumatoid arthritis", "type": "Disease"},
			"b": {"name": "TNF", "type": "Gene"},
			"c": {"name": "IRAK1", "type": "Gene"},
		},
	}

	mock_run_job = AsyncMock(return_value={
		"status": "Complete",
		"result": {"plddt_score": 85.0},
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


@pytest.mark.asyncio
async def test_run_validation_plan_no_api_key():
	"""Skips validation when no API key is configured."""
	hypothesis = {
		"hypothesis_type": "drug_repurposing",
		"abc_path": {
			"a": {"name": "Fostamatinib", "type": "Drug"},
			"b": {"name": "IRAK1", "type": "Gene"},
			"c": {"name": "RA", "type": "Disease"},
		},
	}

	with patch("nexus.tools.validation_planner.settings") as mock_settings:
		mock_settings.tamarind_bio_api_key = None

		from nexus.tools.validation_planner import run_validation_plan
		results = await run_validation_plan(hypothesis)

	assert len(results) == 1
	assert results[0].status == "partial"
	assert "api key" in results[0].summary.lower() or "tamarind" in results[0].summary.lower()


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

	# Should have results explaining what failed
	assert len(results) >= 1
	summaries = " ".join(r.summary for r in results)
	# Should mention specific inputs that failed, not just generic "missing inputs"
	assert "skipped" in summaries.lower() or "failed" in summaries.lower()


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
