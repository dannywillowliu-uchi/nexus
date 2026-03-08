"""Cellosaurus API client + local fallback for cell line resolution.

Resolves disease areas to recommended cell lines using the local cell_models.json
database, with optional Cellosaurus API lookup for additional metadata.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from nexus.lab.protocols.spec import CellModelSpec

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CELLOSAURUS_API = "https://api.cellosaurus.org/cell-line"


def _load_cell_models() -> dict:
	path = DATA_DIR / "cell_models.json"
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)


def resolve_cell_line_local(disease_area: str) -> CellModelSpec | None:
	"""Look up a recommended cell line from the local database by disease area."""
	models = _load_cell_models()

	# Normalize disease area for lookup
	key = disease_area.lower().replace("'s", "").replace(" disease", "").replace(" ", "_").strip()

	# Direct match
	if key in models:
		cell_lines = models[key].get("cell_lines", [])
		if cell_lines:
			return CellModelSpec.from_dict(cell_lines[0])

	# Fuzzy match on disease_area field
	for entry in models.values():
		if disease_area.lower() in entry.get("disease_area", "").lower():
			cell_lines = entry.get("cell_lines", [])
			if cell_lines:
				return CellModelSpec.from_dict(cell_lines[0])

	# Keyword match
	for keyword, entry in models.items():
		if keyword in disease_area.lower():
			cell_lines = entry.get("cell_lines", [])
			if cell_lines:
				return CellModelSpec.from_dict(cell_lines[0])

	return None


async def resolve_cell_line_cellosaurus(name: str) -> dict | None:
	"""Query Cellosaurus API for cell line metadata."""
	try:
		async with httpx.AsyncClient(timeout=15) as client:
			resp = await client.get(
				CELLOSAURUS_API,
				params={"q": name, "format": "json", "fields": "id,ac,sy,ca,sx,ag,di,ox"},
			)
			if resp.status_code != 200:
				return None
			data = resp.json()

		cell_lines = data.get("cell-line-list", [])
		if not cell_lines:
			return None

		cell = cell_lines[0]
		return {
			"accession": cell.get("ac", ""),
			"name": cell.get("id", name),
			"synonyms": cell.get("sy", []),
			"category": cell.get("ca", ""),
			"sex": cell.get("sx", ""),
			"age": cell.get("ag", ""),
			"diseases": [d.get("value", "") for d in cell.get("di", [])],
			"species": [o.get("value", "") for o in cell.get("ox", [])],
		}
	except Exception:
		return None


async def resolve_cell_line(disease_area: str, cell_name: str | None = None) -> CellModelSpec:
	"""Resolve a cell line: try local DB first, then Cellosaurus API.

	If cell_name is given, look up that specific line. Otherwise, pick the
	best match for the disease area from the local database.
	"""
	# If specific cell name requested, try Cellosaurus first for metadata
	if cell_name:
		api_data = await resolve_cell_line_cellosaurus(cell_name)
		if api_data:
			return CellModelSpec(
				name=api_data.get("name", cell_name),
				atcc_number=api_data.get("accession", ""),
				organism=api_data.get("species", ["Homo sapiens"])[0] if api_data.get("species") else "Homo sapiens",
				disease_relevance=", ".join(api_data.get("diseases", [])),
			)

	# Local database lookup by disease area
	local = resolve_cell_line_local(disease_area)
	if local:
		return local

	# Default fallback
	return CellModelSpec(
		name="HeLa",
		atcc_number="CCL-2",
		organism="Homo sapiens",
		tissue="Cervix / adenocarcinoma",
		culture_medium="DMEM",
		serum="10% FBS",
		seeding_density_cells_per_well=5000,
		doubling_time_hours=24,
		growth_mode="adherent",
		disease_relevance="General-purpose cancer cell line",
	)
