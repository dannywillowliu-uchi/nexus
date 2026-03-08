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
