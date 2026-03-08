"""UniProt API client for protein/gene target resolution.

Resolves gene names to UniProt entries with PDB structures, function
annotations, and protein classification data used by the assay selector.
"""

from __future__ import annotations

import httpx

from nexus.lab.protocols.spec import ProteinSpec

UNIPROT_API = "https://rest.uniprot.org/uniprotkb"

RECEPTOR_ENZYME_KEYWORDS = {
	"receptor", "kinase", "protease", "phosphatase", "ligase", "transferase",
	"synthase", "oxidase", "reductase", "dehydrogenase", "hydrolase",
	"transporter", "channel", "pump", "enzyme",
}


async def resolve_protein(gene_name: str, organism: str = "Homo sapiens") -> ProteinSpec:
	"""Resolve a gene name to a ProteinSpec via UniProt API.

	Fetches protein metadata including PDB cross-references, function
	annotations, and protein classification for assay selection.
	"""
	try:
		query = f"(gene:{gene_name}) AND (organism_name:{organism}) AND (reviewed:true)"
		async with httpx.AsyncClient(timeout=15) as client:
			resp = await client.get(
				f"{UNIPROT_API}/search",
				params={
					"query": query,
					"format": "json",
					"size": 1,
					"fields": "accession,gene_names,protein_name,organism_name,cc_function,xref_pdb,keyword",
				},
			)
			if resp.status_code != 200:
				return ProteinSpec(name=gene_name, gene_name=gene_name)

			data = resp.json()
			results = data.get("results", [])
			if not results:
				return ProteinSpec(name=gene_name, gene_name=gene_name)

		entry = results[0]

		# Extract accession
		uniprot_id = entry.get("primaryAccession", "")

		# Extract gene name
		genes = entry.get("genes", [])
		primary_gene = genes[0].get("geneName", {}).get("value", gene_name) if genes else gene_name

		# Extract protein name
		protein_name_data = entry.get("proteinDescription", {})
		rec_name = protein_name_data.get("recommendedName", {})
		full_name = rec_name.get("fullName", {}).get("value", gene_name) if rec_name else gene_name

		# Extract PDB cross-references
		xrefs = entry.get("uniProtKBCrossReferences", [])
		pdb_ids = [x.get("id", "") for x in xrefs if x.get("database") == "PDB"]

		# Extract function
		comments = entry.get("comments", [])
		function_text = ""
		for comment in comments:
			if comment.get("commentType") == "FUNCTION":
				texts = comment.get("texts", [])
				if texts:
					function_text = texts[0].get("value", "")
					break

		# Determine protein class from keywords
		keywords = entry.get("keywords", [])
		keyword_values = {kw.get("value", "").lower() for kw in keywords}
		protein_class = _classify_protein(keyword_values, full_name)

		return ProteinSpec(
			name=full_name,
			uniprot_id=uniprot_id,
			gene_name=primary_gene,
			organism=organism,
			pdb_ids=pdb_ids[:5],  # Top 5 structures
			function=function_text[:500] if function_text else "",
			protein_class=protein_class,
		)

	except Exception:
		return ProteinSpec(name=gene_name, gene_name=gene_name)


def _classify_protein(keywords: set[str], name: str) -> str:
	"""Classify protein as receptor, enzyme, etc. from UniProt keywords."""
	name_lower = name.lower()
	for kw in RECEPTOR_ENZYME_KEYWORDS:
		if kw in keywords or kw in name_lower:
			return kw
	return "other"


def has_structural_data(spec: ProteinSpec) -> bool:
	"""Check if a protein has PDB structures available."""
	return len(spec.pdb_ids) > 0


def is_receptor_or_enzyme(spec: ProteinSpec) -> bool:
	"""Check if a protein is classified as a receptor or enzyme."""
	return spec.protein_class in RECEPTOR_ENZYME_KEYWORDS
