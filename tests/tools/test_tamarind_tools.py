import pytest

from nexus.tools.tamarind_tools import (
	TOOL_CONFIGS,
	TamarindToolConfig,
	get_tools_for_hypothesis,
	InputType,
)


def test_tool_config_dataclass():
	"""TamarindToolConfig stores tool metadata correctly."""
	cfg = TamarindToolConfig(
		tool_type="diffdock",
		display_name="DiffDock",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["proteinFile", "ligandFile"],
		default_settings={"ligandFormat": "sdf/mol2 file"},
		perturbation_params={},
	)
	assert cfg.tool_type == "diffdock"
	assert cfg.input_type == InputType.PROTEIN_LIGAND
	assert "proteinFile" in cfg.required_params


def test_tool_configs_registry_populated():
	"""TOOL_CONFIGS contains expected tools."""
	assert "diffdock" in TOOL_CONFIGS
	assert "autodock_vina" in TOOL_CONFIGS
	assert "gnina" in TOOL_CONFIGS
	assert "admet" in TOOL_CONFIGS
	assert "alphafold" in TOOL_CONFIGS
	assert "esmfold" in TOOL_CONFIGS
	assert "deepfri" in TOOL_CONFIGS
	assert "temstapro" in TOOL_CONFIGS
	assert "netsolp" in TOOL_CONFIGS
	assert "aqueous-solubility" in TOOL_CONFIGS
	assert "af2bind" in TOOL_CONFIGS


def test_get_tools_for_drug_repurposing():
	"""drug_repurposing returns docking + ADMET tools."""
	tools = get_tools_for_hypothesis("drug_repurposing")
	tool_types = [t.tool_type for t in tools]
	assert "diffdock" in tool_types
	assert "gnina" in tool_types
	assert "admet" in tool_types


def test_get_tools_for_target_discovery():
	"""target_discovery returns structure prediction + function tools."""
	tools = get_tools_for_hypothesis("target_discovery")
	tool_types = [t.tool_type for t in tools]
	assert "esmfold" in tool_types
	assert "deepfri" in tool_types
	assert "temstapro" in tool_types


def test_get_tools_for_drug_interaction():
	"""drug_interaction returns ADMET + solubility tools."""
	tools = get_tools_for_hypothesis("drug_interaction")
	tool_types = [t.tool_type for t in tools]
	assert "admet" in tool_types
	assert "aqueous-solubility" in tool_types


def test_get_tools_for_mechanism():
	"""mechanism returns function prediction tools."""
	tools = get_tools_for_hypothesis("mechanism")
	tool_types = [t.tool_type for t in tools]
	assert "deepfri" in tool_types


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


def test_get_tools_for_unknown_type():
	"""Unknown hypothesis type returns empty list."""
	tools = get_tools_for_hypothesis("unknown_type_xyz")
	assert tools == []


def test_all_configs_have_required_fields():
	"""Every config has non-empty tool_type, display_name, category."""
	for key, cfg in TOOL_CONFIGS.items():
		assert cfg.tool_type == key
		assert cfg.display_name
		assert cfg.category
		assert isinstance(cfg.required_params, list)
