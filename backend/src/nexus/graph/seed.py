import json
import re
from pathlib import Path

from nexus.graph.client import graph_client


def parse_metaedge(metaedge: str) -> tuple[str, str, str]:
	"""Parse a Hetionet metaedge string into (source_label, rel_type, target_label).

	Example: "Compound - binds - Gene > CbG" -> ("Compound", "binds", "Gene")
	"""
	# Strip the abbreviation after ">"
	main_part = metaedge.split(">")[0].strip()
	# Match: SourceLabel - relation - TargetLabel
	match = re.match(r"^(\w+)\s*-\s*(.+?)\s*-\s*(\w+)$", main_part)
	if not match:
		raise ValueError(f"Cannot parse metaedge: {metaedge!r}")
	return match.group(1), match.group(2).strip(), match.group(3)


def _sanitize_label(label: str) -> str:
	"""Sanitize a node label for Cypher (replace spaces with underscores)."""
	return re.sub(r"[^a-zA-Z0-9_]", "_", label)


def _extract_edge_fields(edge: dict) -> tuple[str, str, str, str, str]:
	"""Extract (source_label, source_id, target_label, target_id, rel_type) from an edge.

	Handles two formats:
	- Hetionet v1.0 JSON: source_id/target_id are [kind, identifier] arrays, kind is a verb
	- Metaedge format: source/target are identifiers, kind/metaedge is "Source - rel - Target > Abbr"
	"""
	if "source_id" in edge and isinstance(edge["source_id"], list):
		# Hetionet v1.0 format: source_id = [kind, identifier]
		source_label = edge["source_id"][0]
		source_id = str(edge["source_id"][1])
		target_label = edge["target_id"][0]
		target_id = str(edge["target_id"][1])
		rel_type = edge["kind"]
	else:
		# Metaedge string format
		metaedge_str = edge.get("kind", edge.get("metaedge", ""))
		source_label, rel_type, target_label = parse_metaedge(metaedge_str)
		source_id = str(edge["source"])
		target_id = str(edge["target"])

	return source_label, source_id, target_label, target_id, rel_type


async def seed_nodes(nodes_path: Path) -> int:
	"""Load nodes from a Hetionet JSON file into Neo4j. Returns count of nodes created."""
	with open(nodes_path) as f:
		data = json.load(f)

	nodes = data if isinstance(data, list) else data.get("nodes", data.get("data", []))
	count = 0

	# Batch by label for efficiency
	batches: dict[str, list[dict]] = {}
	for node in nodes:
		label = _sanitize_label(node.get("kind", node.get("label", "Node")))
		props = {
			"identifier": str(node["identifier"]),
			"name": node.get("name", str(node["identifier"])),
		}
		# Include extra data if present
		if "data" in node and isinstance(node["data"], dict):
			props.update({k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in node["data"].items()})
		batches.setdefault(label, []).append(props)

	for label, batch in batches.items():
		# Use UNWIND for batch creation
		query = f"UNWIND $batch AS props CREATE (n:{label}) SET n = props"
		await graph_client.execute_write(query, batch=batch)
		count += len(batch)

	return count


async def seed_edges(edges_path: Path) -> int:
	"""Load edges from a Hetionet JSON file into Neo4j. Returns count of edges created."""
	with open(edges_path) as f:
		data = json.load(f)

	edges = data if isinstance(data, list) else data.get("edges", data.get("data", []))
	count = 0

	# Batch by (source_label, rel_type, target_label)
	batches: dict[str, list[dict]] = {}
	for edge in edges:
		source_label, source_id, target_label, target_id, rel_type = _extract_edge_fields(edge)
		source_label = _sanitize_label(source_label)
		target_label = _sanitize_label(target_label)
		key = f"{source_label}|{rel_type}|{target_label}"
		batches.setdefault(key, []).append({
			"source_id": source_id,
			"target_id": target_id,
		})

	for key, batch in batches.items():
		source_label, rel_type, target_label = key.split("|")
		# Sanitize rel_type for Cypher (replace spaces/hyphens with underscores)
		cypher_rel = re.sub(r"[^a-zA-Z0-9_]", "_", rel_type).upper()
		query = (
			f"UNWIND $batch AS edge "
			f"MATCH (s:{source_label} {{identifier: edge.source_id}}) "
			f"MATCH (t:{target_label} {{identifier: edge.target_id}}) "
			f"CREATE (s)-[:{cypher_rel}]->(t)"
		)
		await graph_client.execute_write(query, batch=batch)
		count += len(batch)

	return count


async def seed_all(data_dir: Path | None = None) -> dict[str, int]:
	"""Run full Hetionet seed. Returns dict with node and edge counts."""
	if data_dir is None:
		data_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "hetionet"

	nodes_path = data_dir / "hetionet-v1.0-nodes.json"
	edges_path = data_dir / "hetionet-v1.0-edges.json"

	await graph_client.connect()
	try:
		node_count = await seed_nodes(nodes_path)
		edge_count = await seed_edges(edges_path)
		return {"nodes": node_count, "edges": edge_count}
	finally:
		await graph_client.close()
