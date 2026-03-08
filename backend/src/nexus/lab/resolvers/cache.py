from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COMPOUND_CACHE_PATH = DATA_DIR / "compound_cache.json"


def _load_cache(path: Path) -> dict:
	if not path.exists():
		return {}
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)


def _save_cache(path: Path, data: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(data, f, indent="\t", ensure_ascii=False)


def get_compound_cache() -> dict:
	return _load_cache(COMPOUND_CACHE_PATH)


def lookup_compound(name: str) -> dict | None:
	cache = get_compound_cache()
	key = name.lower().replace(" ", "_").replace("-", "_")
	if key in cache:
		return cache[key]
	# Try fuzzy match on the name field
	for entry in cache.values():
		if entry.get("name", "").lower() == name.lower():
			return entry
	return None


def save_compound(name: str, data: dict) -> None:
	cache = get_compound_cache()
	key = name.lower().replace(" ", "_").replace("-", "_")
	cache[key] = data
	_save_cache(COMPOUND_CACHE_PATH, cache)
