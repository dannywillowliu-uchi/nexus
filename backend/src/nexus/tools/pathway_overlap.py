from __future__ import annotations

import httpx

from nexus.tools.schema import ToolResponse


KEGG_FIND_URL = "https://rest.kegg.jp/find/genes/{gene}"
KEGG_LINK_URL = "https://rest.kegg.jp/link/pathway/{gene_id}"
KEGG_GET_URL = "https://rest.kegg.jp/get/{pathway_id}"


def _parse_kegg_tab(text: str) -> list[list[str]]:
	"""Parse KEGG tab-delimited response into rows."""
	rows = []
	for line in text.strip().split("\n"):
		if line.strip():
			rows.append(line.split("\t"))
	return rows


async def pathway_overlap(gene_a: str, gene_b: str) -> ToolResponse:
	"""Check if two genes share KEGG pathways."""
	try:
		async with httpx.AsyncClient(timeout=30.0) as client:
			# Find gene IDs for both genes (search in human: hsa)
			resp_a = await client.get(KEGG_FIND_URL.format(gene=f"hsa:{gene_a}"))
			resp_a.raise_for_status()
			rows_a = _parse_kegg_tab(resp_a.text)

			resp_b = await client.get(KEGG_FIND_URL.format(gene=f"hsa:{gene_b}"))
			resp_b.raise_for_status()
			rows_b = _parse_kegg_tab(resp_b.text)

			if not rows_a or not rows_b:
				missing = []
				if not rows_a:
					missing.append(gene_a)
				if not rows_b:
					missing.append(gene_b)
				return ToolResponse(
					status="success",
					confidence_delta=0.0,
					evidence_type="neutral",
					summary=f"Gene(s) not found in KEGG: {', '.join(missing)}.",
					raw_data={"missing_genes": missing},
				)

			gene_id_a = rows_a[0][0]
			gene_id_b = rows_b[0][0]

			# Get pathways for each gene
			resp_pa = await client.get(KEGG_LINK_URL.format(gene_id=gene_id_a))
			resp_pa.raise_for_status()
			pathways_a = {row[1] for row in _parse_kegg_tab(resp_pa.text) if len(row) >= 2}

			resp_pb = await client.get(KEGG_LINK_URL.format(gene_id=gene_id_b))
			resp_pb.raise_for_status()
			pathways_b = {row[1] for row in _parse_kegg_tab(resp_pb.text) if len(row) >= 2}

		overlap = pathways_a & pathways_b
		overlap_count = len(overlap)

		if overlap_count == 0:
			return ToolResponse(
				status="success",
				confidence_delta=-0.1,
				evidence_type="neutral",
				summary=f"No shared KEGG pathways between {gene_a} and {gene_b}.",
				raw_data={
					"gene_a": gene_a,
					"gene_b": gene_b,
					"pathways_a_count": len(pathways_a),
					"pathways_b_count": len(pathways_b),
					"overlap_count": 0,
					"shared_pathways": [],
				},
			)

		confidence_delta = min(0.6, overlap_count * 0.1)

		return ToolResponse(
			status="success",
			confidence_delta=confidence_delta,
			evidence_type="supporting",
			summary=f"{gene_a} and {gene_b} share {overlap_count} KEGG pathway(s).",
			raw_data={
				"gene_a": gene_a,
				"gene_b": gene_b,
				"gene_id_a": gene_id_a,
				"gene_id_b": gene_id_b,
				"pathways_a_count": len(pathways_a),
				"pathways_b_count": len(pathways_b),
				"overlap_count": overlap_count,
				"shared_pathways": sorted(overlap),
			},
		)

	except httpx.HTTPError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"KEGG pathway lookup failed: {exc}",
			raw_data={"error": str(exc)},
		)
