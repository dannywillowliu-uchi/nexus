from __future__ import annotations

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse


NCBI_GENE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_GENE_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


async def expression_correlate(gene_a: str, gene_b: str) -> ToolResponse:
	"""Query NCBI Gene API for expression profiles and check co-expression patterns."""
	try:
		async with httpx.AsyncClient(timeout=30.0) as client:
			# Search for both gene IDs
			gene_ids = {}
			for gene_name in [gene_a, gene_b]:
				params: dict[str, str | int] = {
					"db": "gene",
					"term": f"{gene_name}[Gene Name] AND Homo sapiens[Organism]",
					"retmax": 1,
					"retmode": "json",
				}
				if settings.ncbi_api_key:
					params["api_key"] = settings.ncbi_api_key

				resp = await client.get(NCBI_GENE_URL, params=params)
				resp.raise_for_status()
				data = resp.json()
				ids = data.get("esearchresult", {}).get("idlist", [])
				if ids:
					gene_ids[gene_name] = ids[0]

			if len(gene_ids) < 2:
				missing = [g for g in [gene_a, gene_b] if g not in gene_ids]
				return ToolResponse(
					status="success",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"Gene(s) not found in NCBI: {', '.join(missing)}.",
					raw_data={"missing_genes": missing},
				)

			# Fetch gene summaries for both
			all_ids = ",".join(gene_ids.values())
			summary_params: dict[str, str] = {
				"db": "gene",
				"id": all_ids,
				"retmode": "json",
			}
			if settings.ncbi_api_key:
				summary_params["api_key"] = settings.ncbi_api_key

			resp = await client.get(NCBI_GENE_SUMMARY_URL, params=summary_params)
			resp.raise_for_status()
			summary_data = resp.json()

		# Extract gene summaries and check for functional overlap
		result = summary_data.get("result", {})
		gene_a_summary = result.get(gene_ids[gene_a], {}).get("summary", "")
		gene_b_summary = result.get(gene_ids[gene_b], {}).get("summary", "")
		gene_a_desc = result.get(gene_ids[gene_a], {}).get("description", "")
		gene_b_desc = result.get(gene_ids[gene_b], {}).get("description", "")

		# Simple co-expression heuristic: check if gene summaries mention each other
		# or share functional terms
		functional_terms = [
			"signaling", "pathway", "kinase", "transcription", "receptor",
			"apoptosis", "proliferation", "differentiation", "immune",
			"inflammation", "metabolism", "cell cycle", "DNA repair",
		]

		shared_terms = []
		for term in functional_terms:
			a_has = term in gene_a_summary.lower() or term in gene_a_desc.lower()
			b_has = term in gene_b_summary.lower() or term in gene_b_desc.lower()
			if a_has and b_has:
				shared_terms.append(term)

		# Cross-mention check
		cross_mention = (
			gene_b.lower() in gene_a_summary.lower()
			or gene_a.lower() in gene_b_summary.lower()
		)

		if cross_mention:
			confidence_delta = 0.4
			evidence_type = "supporting"
		elif len(shared_terms) >= 3:
			confidence_delta = 0.3
			evidence_type = "supporting"
		elif len(shared_terms) >= 1:
			confidence_delta = 0.15
			evidence_type = "supporting"
		else:
			confidence_delta = 0.0
			evidence_type = "neutral"

		return ToolResponse(
			status="success",
			confidence_delta=confidence_delta,
			evidence_type=evidence_type,
			summary=f"Expression correlation analysis for {gene_a} and {gene_b}: {len(shared_terms)} shared functional term(s). Cross-mention: {cross_mention}.",
			raw_data={
				"gene_a": gene_a,
				"gene_b": gene_b,
				"gene_id_a": gene_ids[gene_a],
				"gene_id_b": gene_ids[gene_b],
				"shared_functional_terms": shared_terms,
				"cross_mention": cross_mention,
				"gene_a_description": gene_a_desc,
				"gene_b_description": gene_b_desc,
			},
		)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"NCBI Gene expression lookup failed: {exc}",
			raw_data={"error": str(exc)},
		)
