"""Validation planner: selects and runs Tamarind tools based on hypothesis type."""

from __future__ import annotations

from dataclasses import dataclass, field

from nexus.tools.tamarind_tools import TOOL_CONFIGS, InputType


@dataclass
class HypothesisInputs:
	"""All possible inputs for validation tools, populated from hypothesis data."""
	drug_name: str | None = None
	drug_smiles: str | None = None
	protein_name: str | None = None
	protein_sequence: str | None = None
	protein_pdb_file: str | None = None
	ligand_file: str | None = None
	hypothesis_type: str = "connection"
	drug_name_2: str | None = None
	drug_smiles_2: str | None = None
	protein_sequence_2: str | None = None
	# Internal: raw file content before upload
	_pdb_content: str | None = field(default=None, repr=False)
	_sdf_content: bytes | None = field(default=None, repr=False)


def build_job_settings(tool_type: str, inputs: HypothesisInputs) -> dict | None:
	"""Build Tamarind job settings for a specific tool, given hypothesis inputs.

	Returns None if required inputs are missing.
	"""
	cfg = TOOL_CONFIGS.get(tool_type)
	if cfg is None:
		return None

	settings = dict(cfg.default_settings)

	if cfg.input_type == InputType.PROTEIN_LIGAND:
		if not inputs.protein_pdb_file or not inputs.ligand_file:
			return None
		if tool_type == "diffdock":
			settings["proteinFile"] = inputs.protein_pdb_file
			settings["ligandFile"] = inputs.ligand_file
		elif tool_type == "surfdock":
			settings["proteinFile"] = inputs.protein_pdb_file
			settings["ligandFile"] = inputs.ligand_file
		elif tool_type in ("autodock_vina", "autodock-vina"):
			settings["receptorFile"] = inputs.protein_pdb_file
			settings["ligandFile"] = inputs.ligand_file
		elif tool_type == "gnina":
			settings["proteinFile"] = inputs.protein_pdb_file
			settings["ligandFile"] = inputs.ligand_file
		elif tool_type == "flowdock":
			settings["pdbFile"] = inputs.protein_pdb_file
			if inputs.drug_smiles:
				settings["smiles"] = inputs.drug_smiles
			if inputs.protein_sequence:
				settings["sequence"] = inputs.protein_sequence
		else:
			settings["proteinFile"] = inputs.protein_pdb_file
			settings["ligandFile"] = inputs.ligand_file

	elif cfg.input_type == InputType.SEQUENCE:
		if not inputs.protein_sequence:
			return None
		settings["sequence"] = inputs.protein_sequence

	elif cfg.input_type == InputType.SMILES:
		if not inputs.drug_smiles:
			return None
		if tool_type == "admet":
			settings["smilesStrings"] = [inputs.drug_smiles]
		else:
			settings["smiles"] = inputs.drug_smiles

	elif cfg.input_type == InputType.PDB:
		if not inputs.protein_pdb_file:
			return None
		settings["pdbFile"] = inputs.protein_pdb_file

	elif cfg.input_type == InputType.COMPLEX_PDB:
		if not inputs.protein_pdb_file or not inputs.ligand_file:
			return None
		settings["pdbFile"] = inputs.protein_pdb_file
		settings["sdfFile"] = inputs.ligand_file

	elif cfg.input_type == InputType.SEQUENCE_PAIR:
		if not inputs.protein_sequence or not inputs.protein_sequence_2:
			return None
		settings["sequenceA"] = inputs.protein_sequence
		settings["sequenceB"] = inputs.protein_sequence_2

	return settings


# --- Evidence scoring per tool category ---

DOCKING_TOOLS = {"diffdock", "autodock_vina", "gnina", "surfdock", "flowdock", "placer", "smina", "unimol2"}
STRUCTURE_TOOLS = {"alphafold", "esmfold", "boltz", "chai", "openfold"}


def _score_docking(result: dict) -> tuple[float, str]:
	"""Score docking results by binding energy."""
	score = result.get("docking_score") or result.get("affinity") or result.get("score", 0.0)
	if isinstance(score, str):
		try:
			score = float(score)
		except ValueError:
			return 0.1, "neutral"
	if score < -7.0:
		return 0.5, "supporting"
	elif score < -5.0:
		return 0.3, "supporting"
	elif score < -3.0:
		return 0.1, "neutral"
	else:
		return -0.1, "contradicting"


def _score_structure(result: dict) -> tuple[float, str]:
	"""Score structure prediction by pLDDT."""
	plddt = result.get("plddt_score") or result.get("confidence_score") or result.get("plddt")
	if plddt is None:
		return 0.1, "neutral"
	if isinstance(plddt, str):
		try:
			plddt = float(plddt)
		except ValueError:
			return 0.1, "neutral"
	if plddt >= 90:
		return 0.4, "supporting"
	elif plddt >= 70:
		return 0.2, "supporting"
	elif plddt >= 50:
		return 0.1, "neutral"
	else:
		return -0.1, "contradicting"


def _score_admet(result: dict) -> tuple[float, str]:
	"""Score ADMET results. Look for druglikeness or overall assessment."""
	predictions = result.get("predictions", [])
	if not predictions:
		return 0.1, "neutral"
	first = predictions[0] if isinstance(predictions, list) else predictions
	druglikeness = first.get("druglikeness", 0.5)
	if isinstance(druglikeness, str):
		try:
			druglikeness = float(druglikeness)
		except ValueError:
			return 0.1, "neutral"
	if druglikeness >= 0.7:
		return 0.3, "supporting"
	elif druglikeness >= 0.4:
		return 0.15, "neutral"
	else:
		return -0.1, "contradicting"


def _score_deepfri(result: dict) -> tuple[float, str]:
	"""Score DeepFRI function predictions."""
	predictions = result.get("predictions", [])
	if not predictions:
		return 0.1, "neutral"
	max_score = max((p.get("score", 0.0) for p in predictions), default=0.0)
	if max_score >= 0.7:
		return 0.3, "supporting"
	elif max_score >= 0.4:
		return 0.15, "supporting"
	else:
		return 0.1, "neutral"


def _score_thermostability(result: dict) -> tuple[float, str]:
	"""Score thermostability predictions (temstapro, deepstabp)."""
	if result.get("thermostable") is True:
		return 0.2, "supporting"
	if result.get("thermostable") is False:
		return -0.05, "neutral"
	tm = result.get("melting_temperature") or result.get("Tm")
	if tm is not None:
		if isinstance(tm, str):
			try:
				tm = float(tm)
			except ValueError:
				return 0.1, "neutral"
		if tm >= 60:
			return 0.2, "supporting"
		elif tm >= 40:
			return 0.1, "neutral"
		else:
			return -0.05, "neutral"
	return 0.1, "neutral"


def _score_default(result: dict) -> tuple[float, str]:
	"""Default scoring: any completed result is mildly supporting."""
	return 0.1, "neutral"


def score_tool_result(tool_type: str, result: dict) -> tuple[float, str]:
	"""Route to the appropriate scoring function based on tool type."""
	if tool_type in DOCKING_TOOLS:
		return _score_docking(result)
	if tool_type in STRUCTURE_TOOLS:
		return _score_structure(result)
	if tool_type == "admet":
		return _score_admet(result)
	if tool_type == "deepfri":
		return _score_deepfri(result)
	if tool_type in ("temstapro", "deepstabp"):
		return _score_thermostability(result)
	return _score_default(result)
