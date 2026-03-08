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
