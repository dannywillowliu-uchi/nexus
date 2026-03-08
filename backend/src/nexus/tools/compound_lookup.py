from __future__ import annotations

import httpx

from nexus.tools.schema import ToolResponse


PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON"


async def compound_lookup(compound_name: str) -> ToolResponse:
	"""Query PubChem REST API for compound information."""
	url = PUBCHEM_URL.format(name=compound_name)

	try:
		async with httpx.AsyncClient(timeout=30.0) as client:
			resp = await client.get(url)
			resp.raise_for_status()
			data = resp.json()

		compounds = data.get("PC_Compounds", [])
		if not compounds:
			return ToolResponse(
				status="success",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"No compound found for '{compound_name}'.",
				raw_data={"query": compound_name},
			)

		compound = compounds[0]
		cid = compound.get("id", {}).get("id", {}).get("cid")

		# Extract properties from the props array
		props: dict[str, str | float] = {}
		for prop in compound.get("props", []):
			urn = prop.get("urn", {})
			label = urn.get("label", "")
			value = prop.get("value", {})

			if label == "Molecular Formula":
				props["molecular_formula"] = value.get("sval", "")
			elif label == "Molecular Weight":
				props["molecular_weight"] = value.get("fval", 0.0)
			elif label == "IUPAC Name" and urn.get("name") == "Preferred":
				props["iupac_name"] = value.get("sval", "")

		return ToolResponse(
			status="success",
			confidence_delta=0.1,
			evidence_type="supporting",
			summary=f"Found compound '{compound_name}' (CID: {cid}). Formula: {props.get('molecular_formula', 'N/A')}, MW: {props.get('molecular_weight', 'N/A')}.",
			raw_data={
				"cid": cid,
				"compound_name": compound_name,
				**props,
			},
		)

	except httpx.HTTPStatusError as exc:
		if exc.response.status_code == 404:
			return ToolResponse(
				status="success",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"Compound '{compound_name}' not found in PubChem.",
				raw_data={"query": compound_name, "error": "not_found"},
			)
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"PubChem lookup failed: {exc}",
			raw_data={"error": str(exc)},
		)
	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"PubChem lookup failed: {exc}",
			raw_data={"error": str(exc)},
		)
