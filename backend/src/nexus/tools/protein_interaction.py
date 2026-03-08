from __future__ import annotations

import httpx

from nexus.tools.schema import ToolResponse


STRING_URL = "https://string-db.org/api/json/interaction_partners"


async def protein_interaction(protein_name: str) -> ToolResponse:
	"""Query STRING database for known protein interaction partners."""
	try:
		params = {
			"identifiers": protein_name,
			"species": 9606,  # Homo sapiens
			"limit": 10,
			"caller_identity": "nexus",
		}

		async with httpx.AsyncClient(timeout=30.0) as client:
			resp = await client.get(STRING_URL, params=params)
			resp.raise_for_status()
			interactions = resp.json()

		if not interactions:
			return ToolResponse(
				status="success",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"No interaction partners found for '{protein_name}' in STRING.",
				raw_data={"query": protein_name, "partners": []},
			)

		partners = []
		for interaction in interactions:
			partners.append({
				"name": interaction.get("preferredName_B", ""),
				"score": interaction.get("score", 0.0),
				"string_id": interaction.get("stringId_B", ""),
			})

		# Higher confidence if many strong interactions found
		avg_score = sum(p["score"] for p in partners) / len(partners) if partners else 0
		confidence_delta = min(0.5, avg_score * 0.5)

		return ToolResponse(
			status="success",
			confidence_delta=confidence_delta,
			evidence_type="supporting",
			summary=f"Found {len(partners)} interaction partner(s) for '{protein_name}'. Top: {partners[0]['name']} (score: {partners[0]['score']}).",
			raw_data={
				"query": protein_name,
				"partner_count": len(partners),
				"partners": partners,
				"average_score": avg_score,
			},
		)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"STRING interaction lookup failed: {exc}",
			raw_data={"error": str(exc)},
		)
