from __future__ import annotations

import logging
import time

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse

logger = logging.getLogger(__name__)

TAMARIND_BASE_URL = "https://app.tamarind.bio/api"
SUBMIT_URL = f"{TAMARIND_BASE_URL}/submit-job"
UPLOAD_URL = f"{TAMARIND_BASE_URL}/upload"
JOBS_URL = f"{TAMARIND_BASE_URL}/jobs"

RCSB_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"


async def _fetch_pdb_for_gene(gene_name: str, client: httpx.AsyncClient) -> str | None:
	"""Try to fetch a PDB file for a gene/protein from RCSB PDB.

	Returns PDB content as string, or None if not found.
	"""
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
		resp = await client.post(RCSB_SEARCH_URL, json=query, timeout=15.0)
		if resp.status_code != 200:
			return None
		data = resp.json()
		results = data.get("result_set", [])
		if not results:
			return None
		pdb_id = results[0].get("identifier", "")
		if not pdb_id:
			return None

		pdb_resp = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb", timeout=30.0)
		pdb_resp.raise_for_status()
		return pdb_resp.text
	except Exception:
		logger.debug("Could not fetch PDB for %s", gene_name)
		return None


async def _fetch_sdf_for_drug(drug_name: str, client: httpx.AsyncClient) -> bytes | None:
	"""Download SDF file for a drug from PubChem (includes full 3D coordinates)."""
	try:
		resp = await client.get(
			f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/SDF",
			timeout=15.0,
		)
		if resp.status_code != 200:
			return None
		return resp.content
	except Exception:
		logger.debug("Could not fetch SDF for %s", drug_name)
	return None


async def molecular_dock(compound_name: str, protein_name: str) -> ToolResponse:
	"""Submit a molecular docking job to Tamarind Bio DiffDock.

	Workflow:
	1. Fetch protein PDB from RCSB PDB
	2. Download drug SDF from PubChem (full 3D structure)
	3. Upload both files to Tamarind Bio
	4. Submit DiffDock job
	"""
	if not settings.tamarind_bio_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Molecular docking skipped for {compound_name} + {protein_name}: no Tamarind Bio API key configured.",
			raw_data={"compound": compound_name, "protein": protein_name, "reason": "missing_api_key"},
		)

	headers = {"x-api-key": settings.tamarind_bio_api_key}

	try:
		async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
			# Step 1: Fetch protein PDB
			pdb_content = await _fetch_pdb_for_gene(protein_name, client)
			if not pdb_content:
				return ToolResponse(
					status="partial",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"No PDB structure found for {protein_name}. Cannot run docking.",
					raw_data={"protein": protein_name, "reason": "no_pdb_structure"},
				)

			# Step 2: Fetch drug SDF from PubChem
			sdf_content = await _fetch_sdf_for_drug(compound_name, client)
			if not sdf_content:
				return ToolResponse(
					status="partial",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"No SDF found for {compound_name} on PubChem. Cannot run docking.",
					raw_data={"compound": compound_name, "reason": "no_sdf"},
				)

			# Step 3: Upload protein PDB to Tamarind
			pdb_filename = f"nexus-{protein_name}.pdb".replace(" ", "_")
			upload_resp = await client.put(
				f"{UPLOAD_URL}/{pdb_filename}",
				content=pdb_content.encode(),
				headers={**headers, "Content-Type": "application/octet-stream"},
			)
			upload_resp.raise_for_status()

			# Step 4: Upload ligand SDF to Tamarind
			sdf_filename = f"nexus-{compound_name}.sdf".replace(" ", "_")
			upload_resp = await client.put(
				f"{UPLOAD_URL}/{sdf_filename}",
				content=sdf_content,
				headers={**headers, "Content-Type": "application/octet-stream"},
			)
			upload_resp.raise_for_status()

			# Step 5: Submit DiffDock job
			ts = int(time.time())
			job_name = f"nexus-dock-{compound_name}-{protein_name}-{ts}".replace(" ", "_")[:64]
			payload = {
				"jobName": job_name,
				"type": "diffdock",
				"settings": {
					"proteinFile": pdb_filename,
					"ligandFile": sdf_filename,
					"ligandFormat": "sdf/mol2 file",
				},
			}

			resp = await client.post(SUBMIT_URL, json=payload, headers={**headers, "Content-Type": "application/json"})
			resp.raise_for_status()

			response_text = resp.text.strip()

		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"DiffDock job submitted for {compound_name} + {protein_name}: {response_text}",
			raw_data={"job_name": job_name, "response": response_text},
		)

	except httpx.HTTPError as exc:
		logger.warning("Tamarind Bio docking failed for %s + %s: %s", compound_name, protein_name, exc)
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Tamarind Bio docking submission failed: {exc}",
			raw_data={"error": str(exc)},
		)
	except Exception as exc:
		logger.warning("Molecular docking error for %s + %s: %s", compound_name, protein_name, exc)
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Molecular docking error: {exc}",
			raw_data={"error": str(exc)},
		)
