import pytest

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
