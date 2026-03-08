from __future__ import annotations

import httpx

from nexus.config import settings
from nexus.tools.schema import ToolResponse


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Keywords used to classify abstracts as supporting or contradicting
SUPPORTING_KEYWORDS = ["associated", "correlat", "linked", "role in", "involved", "pathway", "target"]
CONTRADICTING_KEYWORDS = ["no association", "no correlation", "not linked", "failed to", "no evidence", "unrelated"]


async def literature_validate(hypothesis: dict) -> ToolResponse:
	"""Search PubMed for papers about the A-B-C connection and assess evidence."""
	a_name = hypothesis.get("a_name", "")
	b_name = hypothesis.get("b_name", "")
	c_name = hypothesis.get("c_name", "")

	query = f"{a_name} {b_name} {c_name}"

	try:
		params: dict[str, str | int] = {
			"db": "pubmed",
			"term": query,
			"retmax": 20,
			"retmode": "json",
		}
		if settings.ncbi_api_key:
			params["api_key"] = settings.ncbi_api_key

		async with httpx.AsyncClient(timeout=30.0) as client:
			resp = await client.get(ESEARCH_URL, params=params)
			resp.raise_for_status()
			data = resp.json()
			pmids: list[str] = data.get("esearchresult", {}).get("idlist", [])

			if not pmids:
				return ToolResponse(
					status="success",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"No PubMed articles found for '{query}'.",
					raw_data={"query": query, "pmids": [], "total_results": 0},
				)

			# Fetch abstracts
			fetch_params: dict[str, str] = {
				"db": "pubmed",
				"id": ",".join(pmids),
				"retmode": "xml",
			}
			if settings.ncbi_api_key:
				fetch_params["api_key"] = settings.ncbi_api_key

			resp = await client.get(EFETCH_URL, params=fetch_params)
			resp.raise_for_status()
			xml_text = resp.text

		# Count supporting vs contradicting evidence from abstracts
		supporting = 0
		contradicting = 0
		abstract_lower = xml_text.lower()

		for kw in SUPPORTING_KEYWORDS:
			supporting += abstract_lower.count(kw)
		for kw in CONTRADICTING_KEYWORDS:
			contradicting += abstract_lower.count(kw)

		total = supporting + contradicting
		if total == 0:
			confidence_delta = 0.1  # Found papers but no clear signal
			evidence_type = "neutral"
		elif supporting > contradicting:
			confidence_delta = min(0.5, (supporting - contradicting) / total)
			evidence_type = "supporting"
		else:
			confidence_delta = max(-0.5, -(contradicting - supporting) / total)
			evidence_type = "contradicting"

		return ToolResponse(
			status="success",
			confidence_delta=confidence_delta,
			evidence_type=evidence_type,
			summary=f"Found {len(pmids)} articles for '{query}'. Supporting signals: {supporting}, contradicting: {contradicting}.",
			raw_data={
				"query": query,
				"pmids": pmids,
				"total_results": len(pmids),
				"supporting_count": supporting,
				"contradicting_count": contradicting,
			},
		)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"PubMed search failed: {exc}",
			raw_data={"error": str(exc)},
		)
