"""Validation planner: selects and runs Tamarind tools based on hypothesis type."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse
from nexus.tools.tamarind_client import TamarindClient
from nexus.tools.tamarind_tools import TOOL_CONFIGS, InputType, get_tools_for_hypothesis


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


logger = logging.getLogger(__name__)

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT_API = "https://rest.uniprot.org/uniprotkb/search"


async def _fetch_pdb_for_gene(gene_name: str) -> str | None:
	"""Fetch PDB content from RCSB PDB for a gene/protein."""
	query = {
		"query": {
			"type": "terminal",
			"service": "full_text",
			"parameters": {"value": f"{gene_name} human"},
		},
		"return_type": "entry",
		"request_options": {"paginate": {"start": 0, "rows": 1}},
	}
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.post(RCSB_SEARCH_URL, json=query)
			if resp.status_code != 200:
				return None
			data = resp.json()
			results = data.get("result_set", [])
			if not results:
				return None
			pdb_id = results[0].get("identifier", "")
			if not pdb_id:
				return None
			pdb_resp = await client.get(
				f"https://files.rcsb.org/download/{pdb_id}.pdb", timeout=30.0
			)
			pdb_resp.raise_for_status()
			return pdb_resp.text
	except Exception:
		logger.debug("Could not fetch PDB for %s", gene_name)
		return None


async def _fetch_sdf_for_drug(drug_name: str) -> bytes | None:
	"""Download SDF from PubChem for a drug name."""
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.get(
				f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/SDF"
			)
			if resp.status_code != 200:
				return None
			return resp.content
	except Exception:
		logger.debug("Could not fetch SDF for %s", drug_name)
		return None


async def _fetch_smiles_for_drug(drug_name: str) -> str | None:
	"""Fetch canonical SMILES from PubChem for a drug name."""
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.get(
				f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/CanonicalSMILES/JSON"
			)
			if resp.status_code != 200:
				return None
			data = resp.json()
			props = data.get("PropertyTable", {}).get("Properties", [])
			if props:
				return props[0].get("CanonicalSMILES")
			return None
	except Exception:
		logger.debug("Could not fetch SMILES for %s", drug_name)
		return None


async def _fetch_sequence_for_gene(gene_name: str) -> str | None:
	"""Fetch protein sequence from UniProt for a gene name."""
	try:
		async with httpx.AsyncClient(timeout=15.0) as client:
			resp = await client.get(
				UNIPROT_API,
				params={
					"query": f"gene_exact:{gene_name} AND organism_id:9606",
					"format": "json",
					"size": "1",
				},
			)
			if resp.status_code != 200:
				return None
			data = resp.json()
			results = data.get("results", [])
			if not results:
				return None
			seq = results[0].get("sequence", {}).get("value")
			return seq
	except Exception:
		logger.debug("Could not fetch sequence for %s", gene_name)
		return None


async def _resolve_inputs(hypothesis: dict) -> tuple[HypothesisInputs, dict[str, str]]:
	"""Extract and fetch all needed inputs from a scored hypothesis dict.

	Returns a tuple of (inputs, report) where report maps input names to "fetched" or "failed".
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


async def _upload_files(inputs: HypothesisInputs, client: TamarindClient) -> None:
	"""Upload PDB and SDF files to Tamarind if they exist."""
	upload_tasks = []

	if inputs._pdb_content:
		pdb_filename = f"nexus-{inputs.protein_name}.pdb".replace(" ", "_")
		inputs.protein_pdb_file = pdb_filename
		upload_tasks.append(client.upload_file(pdb_filename, inputs._pdb_content.encode()))

	if inputs._sdf_content:
		sdf_filename = f"nexus-{inputs.drug_name}.sdf".replace(" ", "_")
		inputs.ligand_file = sdf_filename
		upload_tasks.append(client.upload_file(sdf_filename, inputs._sdf_content))

	if upload_tasks:
		await asyncio.gather(*upload_tasks, return_exceptions=True)


async def run_validation_plan(hypothesis: dict) -> list[ToolResponse]:
	"""Run all appropriate validation tools for a hypothesis.

	1. Determine hypothesis type
	2. Resolve inputs (fetch PDB/SDF/SMILES/sequence)
	3. Upload files to Tamarind
	4. Select tools and build job settings
	5. Run all jobs in parallel
	6. Score results and return ToolResponses
	"""
	h_type = hypothesis.get("hypothesis_type", "connection")
	tool_configs = get_tools_for_hypothesis(h_type)

	if not tool_configs:
		return []

	if not settings.tamarind_bio_api_key:
		return [ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary="Validation skipped: no Tamarind Bio API key configured.",
			raw_data={"reason": "missing_api_key"},
		)]

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

	ts = int(time.time())

	async def _run_single(tool_type: str, tool_settings: dict) -> ToolResponse:
		job_name = f"nexus-val-{tool_type}-{ts}-{hash(str(tool_settings)) % 10000:04d}"
		try:
			result = await client.run_job(
				job_name=job_name,
				job_type=tool_type,
				settings=tool_settings,
				timeout=300.0,
			)
			job_status = result.get("status", "")
			if job_status != "Complete":
				return ToolResponse(
					status="partial",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"{tool_type} job ended with status: {job_status}",
					raw_data={"tool_type": tool_type, "job_name": job_name, "status": job_status},
				)
			result_data = result.get("result", {}) or {}
			confidence_delta, evidence_type = score_tool_result(tool_type, result_data)
			return ToolResponse(
				status="success",
				confidence_delta=confidence_delta,
				evidence_type=evidence_type,
				summary=f"{tool_type}: completed successfully",
				raw_data={"tool_type": tool_type, "job_name": job_name, **result_data},
			)
		except TimeoutError:
			return ToolResponse(
				status="partial",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"{tool_type} job timed out",
				raw_data={"tool_type": tool_type, "job_name": job_name, "status": "timeout"},
			)
		except Exception as exc:
			return ToolResponse(
				status="error",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"{tool_type} failed: {exc}",
				raw_data={"tool_type": tool_type, "error": str(exc)},
			)

	job_tasks = [_run_single(tool_type, tool_settings) for tool_type, tool_settings in jobs_to_run]
	job_results = await asyncio.gather(*job_tasks)
	results.extend(job_results)
	return results
