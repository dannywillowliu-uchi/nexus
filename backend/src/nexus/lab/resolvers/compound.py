"""PubChem PUG REST API client for compound resolution.

Resolves compound names to structured identifiers (CID, SMILES, InChIKey, MW)
with UniChem cross-reference for CAS numbers and local cache integration.
"""

from __future__ import annotations

import httpx

from nexus.lab.protocols.spec import CompoundSpec
from nexus.lab.resolvers.cache import lookup_compound, save_compound

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
UNICHEM_BASE = "https://www.ebi.ac.uk/unichem/rest"


async def _fetch_pubchem(name: str) -> dict | None:
	"""Query PubChem PUG REST by compound name, return raw property dict."""
	url = f"{PUBCHEM_BASE}/compound/name/{name}/JSON"
	async with httpx.AsyncClient(timeout=15) as client:
		resp = await client.get(url)
		if resp.status_code == 404:
			return None
		resp.raise_for_status()
		data = resp.json()

	compounds = data.get("PC_Compounds", [])
	if not compounds:
		return None

	compound = compounds[0]
	cid = compound.get("id", {}).get("id", {}).get("cid", 0)

	props: dict = {"pubchem_cid": cid}
	for prop in compound.get("props", []):
		urn = prop.get("urn", {})
		label = urn.get("label", "")
		value = prop.get("value", {})
		if label == "Molecular Weight":
			props["molecular_weight"] = float(value.get("sval", 0))
		elif label == "SMILES" and urn.get("name") == "Canonical":
			props["smiles"] = value.get("sval", "")
		elif label == "InChIKey":
			props["inchi_key"] = value.get("sval", "")
		elif label == "IUPAC Name" and urn.get("name") == "Preferred":
			props["iupac_name"] = value.get("sval", "")
		elif label == "Molecular Formula":
			props["molecular_formula"] = value.get("sval", "")
	return props


async def _fetch_pubchem_by_synonym(name: str) -> dict | None:
	"""Fallback: search PubChem by synonyms when direct name lookup fails."""
	url = f"{PUBCHEM_BASE}/compound/name/{name}/synonyms/JSON"
	async with httpx.AsyncClient(timeout=15) as client:
		resp = await client.get(url)
		if resp.status_code == 404:
			return None
		resp.raise_for_status()
		data = resp.json()

	info_list = data.get("InformationList", {}).get("Information", [])
	if not info_list:
		return None

	cid = info_list[0].get("CID", 0)
	if not cid:
		return None

	# Re-fetch full properties by CID
	url = f"{PUBCHEM_BASE}/compound/cid/{cid}/JSON"
	async with httpx.AsyncClient(timeout=15) as client:
		resp = await client.get(url)
		if resp.status_code == 404:
			return None
		resp.raise_for_status()
		return await _fetch_pubchem(name)  # Retry with known name


async def _fetch_cas_from_unichem(inchi_key: str) -> str:
	"""Cross-reference InChIKey via UniChem to find CAS number."""
	if not inchi_key:
		return ""
	url = f"{UNICHEM_BASE}/inchikey/{inchi_key}"
	try:
		async with httpx.AsyncClient(timeout=10) as client:
			resp = await client.get(url)
			if resp.status_code != 200:
				return ""
			entries = resp.json()

		# Source 15 = ChemIDplus / CAS-like registries
		for entry in entries:
			src_id = entry.get("src_id")
			if src_id in ("15", "7"):
				return entry.get("src_compound_id", "")
	except Exception:
		pass
	return ""


async def _fetch_cas_from_pubchem(cid: int) -> str:
	"""Fallback CAS lookup via PubChem synonyms (CAS numbers appear as synonyms)."""
	if not cid:
		return ""
	url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
	try:
		async with httpx.AsyncClient(timeout=10) as client:
			resp = await client.get(url)
			if resp.status_code != 200:
				return ""
			data = resp.json()

		info_list = data.get("InformationList", {}).get("Information", [])
		if not info_list:
			return ""

		import re
		cas_pattern = re.compile(r"^\d{2,7}-\d{2}-\d$")
		for synonym in info_list[0].get("Synonym", []):
			if cas_pattern.match(synonym):
				return synonym
	except Exception:
		pass
	return ""


async def resolve_compound(name: str) -> CompoundSpec:
	"""Resolve a compound name to a full CompoundSpec.

	Checks local cache first, then queries PubChem + UniChem.
	Results are cached for future lookups.
	"""
	# Check cache first
	cached = lookup_compound(name)
	if cached:
		return CompoundSpec.from_dict({**cached, "name": cached.get("name", name)})

	# Query PubChem
	props = await _fetch_pubchem(name)
	if not props:
		props = await _fetch_pubchem_by_synonym(name)
	if not props:
		return CompoundSpec(name=name)

	# Cross-reference CAS number
	cas = await _fetch_cas_from_unichem(props.get("inchi_key", ""))
	if not cas:
		cas = await _fetch_cas_from_pubchem(props.get("pubchem_cid", 0))

	spec = CompoundSpec(
		name=name,
		cas_number=cas,
		smiles=props.get("smiles", ""),
		inchi_key=props.get("inchi_key", ""),
		molecular_weight=props.get("molecular_weight", 0.0),
		iupac_name=props.get("iupac_name", ""),
		pubchem_cid=props.get("pubchem_cid", 0),
	)

	# Cache result
	save_compound(name, spec.to_dict())
	return spec
