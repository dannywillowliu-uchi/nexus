"""Registry of Tamarind Bio tool configurations for validation planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InputType(Enum):
	"""What kind of input a Tamarind tool needs."""
	PROTEIN_LIGAND = "protein_ligand"  # PDB file + SDF/SMILES
	SEQUENCE = "sequence"  # protein amino acid sequence
	SMILES = "smiles"  # small molecule SMILES string
	PDB = "pdb"  # PDB file only
	COMPLEX_PDB = "complex_pdb"  # protein-ligand complex PDB
	SEQUENCE_PAIR = "sequence_pair"  # two protein sequences


@dataclass
class TamarindToolConfig:
	"""Configuration for a single Tamarind Bio tool."""
	tool_type: str  # Tamarind API job type (e.g., "diffdock")
	display_name: str  # Human-readable name
	category: str  # "docking", "structure", "properties", "function", "affinity"
	input_type: InputType
	required_params: list[str]  # Required settings keys
	default_settings: dict = field(default_factory=dict)
	perturbation_params: dict[str, list] = field(default_factory=dict)


TOOL_CONFIGS: dict[str, TamarindToolConfig] = {
	# --- Docking tools (consensus) ---
	"diffdock": TamarindToolConfig(
		tool_type="diffdock",
		display_name="DiffDock",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["proteinFile", "ligandFile"],
		default_settings={"ligandFormat": "sdf/mol2 file"},
	),
	"autodock_vina": TamarindToolConfig(
		tool_type="autodock_vina",
		display_name="AutoDock Vina",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["receptorFile", "ligandFile"],
		default_settings={
			"boxX": 0, "boxY": 0, "boxZ": 0,
			"width": 25, "height": 25, "depth": 25,
			"exhaustiveness": 8,
		},
		perturbation_params={
			"exhaustiveness": [8, 16, 32],
		},
	),
	"gnina": TamarindToolConfig(
		tool_type="gnina",
		display_name="GNINA",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["proteinFile", "ligandFile"],
		default_settings={
			"boxX": 0, "boxY": 0, "boxZ": 0,
			"width": 25, "height": 25, "depth": 25,
			"wholeProtein": True,
			"exhaustiveness": 8,
		},
		perturbation_params={
			"exhaustiveness": [8, 16],
		},
	),
	"flowdock": TamarindToolConfig(
		tool_type="flowdock",
		display_name="FlowDock",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["pdbFile", "sequence", "smiles"],
		default_settings={},
	),
	"surfdock": TamarindToolConfig(
		tool_type="surfdock",
		display_name="SurfDock",
		category="docking",
		input_type=InputType.PROTEIN_LIGAND,
		required_params=["proteinFile", "ligandFile"],
		default_settings={"ligandFormat": "sdf file", "numSamples": 40},
	),

	# --- ADMET / drug properties ---
	"admet": TamarindToolConfig(
		tool_type="admet",
		display_name="ADMET",
		category="properties",
		input_type=InputType.SMILES,
		required_params=["smilesStrings"],
		default_settings={},
	),
	"aqueous-solubility": TamarindToolConfig(
		tool_type="aqueous-solubility",
		display_name="Aqueous Solubility",
		category="properties",
		input_type=InputType.SMILES,
		required_params=["smiles"],
		default_settings={},
	),

	# --- Binding affinity (post-dock) ---
	"aev-plig": TamarindToolConfig(
		tool_type="aev-plig",
		display_name="AEV-PLIG",
		category="affinity",
		input_type=InputType.COMPLEX_PDB,
		required_params=["pdbFile", "sdfFile"],
		default_settings={},
	),

	# --- Binding site prediction ---
	"af2bind": TamarindToolConfig(
		tool_type="af2bind",
		display_name="AF2BIND",
		category="binding_site",
		input_type=InputType.PDB,
		required_params=["pdbFile", "chain"],
		default_settings={"chain": "A"},
	),

	# --- Structure prediction ---
	"alphafold": TamarindToolConfig(
		tool_type="alphafold",
		display_name="AlphaFold",
		category="structure",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={"numRecycles": 3, "numModels": "1", "modelType": "auto"},
	),
	"esmfold": TamarindToolConfig(
		tool_type="esmfold",
		display_name="ESMFold",
		category="structure",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={},
	),
	"boltz": TamarindToolConfig(
		tool_type="boltz",
		display_name="Boltz-2",
		category="structure",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={"inputFormat": "sequence", "numSamples": 5},
	),

	# --- Protein function prediction ---
	"deepfri": TamarindToolConfig(
		tool_type="deepfri",
		display_name="DeepFRI",
		category="function",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={"task": "sequence", "ontology": ["mf", "bp"]},
		perturbation_params={
			"ontology": [["mf", "bp"], ["mf", "bp", "cc", "ec"]],
		},
	),

	# --- Protein properties ---
	"temstapro": TamarindToolConfig(
		tool_type="temstapro",
		display_name="TemStaPro",
		category="properties",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={},
	),
	"netsolp": TamarindToolConfig(
		tool_type="netsolp",
		display_name="NetSolP",
		category="properties",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={},
	),
	"deepstabp": TamarindToolConfig(
		tool_type="deepstabp",
		display_name="deepSTABp",
		category="properties",
		input_type=InputType.SEQUENCE,
		required_params=["sequence"],
		default_settings={},
	),

	# --- Protein-protein interaction ---
	"spatial-ppi": TamarindToolConfig(
		tool_type="spatial-ppi",
		display_name="Spatial PPI v2",
		category="interaction",
		input_type=InputType.SEQUENCE_PAIR,
		required_params=["sequenceA", "sequenceB"],
		default_settings={"inputFormat": "sequence"},
	),
}

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
	"comorbidity": [],
	"connection": [],
}


def get_tools_for_hypothesis(hypothesis_type: str) -> list[TamarindToolConfig]:
	"""Return ordered list of tool configs appropriate for a hypothesis type."""
	tool_keys = HYPOTHESIS_TOOL_MAP.get(hypothesis_type, [])
	return [TOOL_CONFIGS[k] for k in tool_keys if k in TOOL_CONFIGS]
