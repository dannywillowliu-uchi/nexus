from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from nexus.config import settings


@dataclass
class Paper:
	paper_id: str
	title: str
	abstract: str
	year: int | None = None
	citation_count: int | None = None
	source: str = "pubmed"


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


async def search_pubmed(query: str, max_results: int = 10) -> list[Paper]:
	"""Search PubMed via NCBI E-utilities and return parsed Papers."""
	params: dict[str, str | int] = {
		"db": "pubmed",
		"term": query,
		"retmax": max_results,
		"retmode": "json",
	}
	if settings.ncbi_api_key:
		params["api_key"] = settings.ncbi_api_key

	async with httpx.AsyncClient(timeout=30.0) as client:
		# ESearch to get PMIDs
		resp = await client.get(ESEARCH_URL, params=params)
		resp.raise_for_status()
		data = resp.json()
		pmids: list[str] = data.get("esearchresult", {}).get("idlist", [])

		if not pmids:
			return []

		# EFetch to get article XML
		fetch_params: dict[str, str] = {
			"db": "pubmed",
			"id": ",".join(pmids),
			"retmode": "xml",
		}
		if settings.ncbi_api_key:
			fetch_params["api_key"] = settings.ncbi_api_key

		resp = await client.get(EFETCH_URL, params=fetch_params)
		resp.raise_for_status()

	return _parse_pubmed_xml(resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[Paper]:
	"""Parse PubMed EFetch XML into Paper objects."""
	root = ET.fromstring(xml_text)
	papers: list[Paper] = []

	for article in root.findall(".//PubmedArticle"):
		pmid_el = article.find(".//PMID")
		title_el = article.find(".//ArticleTitle")
		abstract_el = article.find(".//AbstractText")
		year_el = article.find(".//PubDate/Year")

		if pmid_el is None or title_el is None:
			continue

		papers.append(
			Paper(
				paper_id=pmid_el.text or "",
				title=title_el.text or "",
				abstract=abstract_el.text if abstract_el is not None and abstract_el.text else "",
				year=int(year_el.text) if year_el is not None and year_el.text else None,
				source="pubmed",
			)
		)

	return papers


async def search_semantic_scholar(query: str, max_results: int = 10) -> list[Paper]:
	"""Search Semantic Scholar API and return parsed Papers."""
	headers: dict[str, str] = {}
	if settings.semantic_scholar_api_key:
		headers["x-api-key"] = settings.semantic_scholar_api_key

	params: dict[str, str | int] = {
		"query": query,
		"limit": max_results,
		"fields": "paperId,title,abstract,year,citationCount",
	}

	async with httpx.AsyncClient(timeout=30.0) as client:
		resp = await client.get(S2_SEARCH_URL, params=params, headers=headers)
		resp.raise_for_status()
		data = resp.json()

	papers: list[Paper] = []
	for item in data.get("data", []):
		papers.append(
			Paper(
				paper_id=item.get("paperId", ""),
				title=item.get("title", ""),
				abstract=item.get("abstract") or "",
				year=item.get("year"),
				citation_count=item.get("citationCount"),
				source="semantic_scholar",
			)
		)

	return papers


async def search_papers(query: str, max_results: int = 10) -> list[Paper]:
	"""Search both PubMed and Semantic Scholar, deduplicate by title."""
	pubmed_papers = await search_pubmed(query, max_results=max_results)
	s2_papers = await search_semantic_scholar(query, max_results=max_results)

	seen_titles: set[str] = set()
	combined: list[Paper] = []

	for paper in pubmed_papers + s2_papers:
		normalized = paper.title.strip().lower()
		if normalized not in seen_titles:
			seen_titles.add(normalized)
			combined.append(paper)

	return combined
