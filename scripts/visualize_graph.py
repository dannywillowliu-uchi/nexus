#!/usr/bin/env python3
"""Visualize the Nexus knowledge graph neighborhood around an entity.

Usage:
	python scripts/visualize_graph.py "Alzheimer disease"
	python scripts/visualize_graph.py "Alzheimer disease" --depth 2 --limit 50
	python scripts/visualize_graph.py --from-trace traces/bf952667-results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))


NODE_COLORS = {
	"Disease": "#e74c3c",
	"Drug": "#3498db",
	"Gene": "#2ecc71",
	"Compound": "#9b59b6",
	"Phenotype": "#f39c12",
	"Anatomy": "#1abc9c",
	"BiologicalProcess": "#e67e22",
	"MolecularFunction": "#16a085",
	"CellularComponent": "#27ae60",
	"Pathway": "#d35400",
	"PharmacologicClass": "#8e44ad",
	"SideEffect": "#c0392b",
	"Symptom": "#f1c40f",
	"Entity": "#95a5a6",
}

EDGE_COLORS = {
	"INDICATION": "#27ae60",
	"CONTRAINDICATION": "#e74c3c",
	"TARGET": "#3498db",
	"ENZYME": "#9b59b6",
	"TRANSPORTER": "#f39c12",
	"CARRIER": "#1abc9c",
	"ASSOCIATED_WITH": "#e67e22",
	"PHENOTYPE_PRESENT": "#f1c40f",
	"OFF_LABEL_USE": "#16a085",
	"LITERATURE_EDGE": "#2c3e50",
}


async def query_neighborhood(entity: str, depth: int = 1, limit: int = 80) -> dict:
	"""Query Neo4j for the neighborhood around an entity."""
	from nexus.graph.client import graph_client

	await graph_client.connect()

	# Resolve entity name first
	resolved = await graph_client.resolve_entity(entity)
	if resolved.match_method == "unresolved":
		print(f"WARNING: Could not resolve '{entity}' in graph")
		resolved_name = entity
	else:
		resolved_name = resolved.name
		print(f"Resolved: '{entity}' -> '{resolved_name}' ({resolved.type})")

	query = f"""
		MATCH path = (a {{name: $entity}})-[r*1..{depth}]-(b)
		WHERE a <> b
		WITH a, b, relationships(path) AS rels
		LIMIT $limit
		RETURN
			a.name AS source_name, labels(a)[0] AS source_type,
			b.name AS target_name, labels(b)[0] AS target_type,
			[r IN rels | type(r)] AS rel_types
	"""
	records = await graph_client.execute_read(query, entity=resolved_name, limit=limit)
	await graph_client.close()

	nodes = {}
	edges = []

	for row in records:
		src = row["source_name"]
		tgt = row["target_name"]
		src_type = row["source_type"]
		tgt_type = row["target_type"]
		rel_types = row["rel_types"]

		nodes[src] = src_type
		nodes[tgt] = tgt_type
		edges.append({
			"from": src,
			"to": tgt,
			"label": " / ".join(rel_types),
			"rel_type": rel_types[0] if rel_types else "UNKNOWN",
		})

	return {"center": resolved_name, "nodes": nodes, "edges": edges}


def build_from_trace(trace_path: str) -> dict:
	"""Build graph data from a trace results file."""
	with open(trace_path) as f:
		data = json.load(f)

	nodes = {}
	edges = []

	for h in data.get("hypotheses", []):
		abc = h.get("abc_path", {})
		a = abc.get("a", {})
		b = abc.get("b", {})
		c = abc.get("c", {})

		if a.get("name"):
			nodes[a["name"]] = a.get("type", "Entity")
		if b.get("name"):
			nodes[b["name"]] = b.get("type", "Entity")
		if c.get("name"):
			nodes[c["name"]] = c.get("type", "Entity")

		# A -> B edge
		if a.get("name") and b.get("name"):
			ab_rel = h.get("description", "").split("(")[-1].split("/")[0].strip() if "(" in h.get("description", "") else "RELATED"
			edges.append({"from": a["name"], "to": b["name"], "label": ab_rel, "rel_type": ab_rel})

		# B -> C edge
		if b.get("name") and c.get("name"):
			bc_rel = h.get("description", "").split("/")[-1].replace(")", "").strip() if "/" in h.get("description", "") else "RELATED"
			edges.append({"from": b["name"], "to": c["name"], "label": bc_rel, "rel_type": bc_rel})

		# Add intermediaries
		for inter in h.get("intermediaries", [])[:3]:
			b_name = inter.get("b_name", "")
			if b_name and b_name != b.get("name"):
				nodes[b_name] = inter.get("b_type", "Entity")
				edges.append({"from": a["name"], "to": b_name, "label": inter.get("ab_rel", ""), "rel_type": inter.get("ab_rel", "")})
				edges.append({"from": b_name, "to": c["name"], "label": inter.get("bc_rel", ""), "rel_type": inter.get("bc_rel", "")})

	center = data["hypotheses"][0]["abc_path"]["a"]["name"] if data.get("hypotheses") else "unknown"
	return {"center": center, "nodes": nodes, "edges": edges}


def render_html(graph_data: dict, output_path: str) -> str:
	"""Generate an interactive HTML visualization using pyvis."""
	from pyvis.network import Network

	net = Network(
		height="800px",
		width="100%",
		bgcolor="#1a1a2e",
		font_color="#ffffff",
		directed=True,
	)
	net.barnes_hut(gravity=-3000, central_gravity=0.3, spring_length=150)

	center = graph_data["center"]

	# Deduplicate edges
	seen_edges = set()
	unique_edges = []
	for e in graph_data["edges"]:
		key = (e["from"], e["to"], e["label"])
		if key not in seen_edges:
			seen_edges.add(key)
			unique_edges.append(e)

	# Add nodes
	for name, node_type in graph_data["nodes"].items():
		color = NODE_COLORS.get(node_type, "#95a5a6")
		size = 30 if name == center else 18
		border_width = 3 if name == center else 1
		net.add_node(
			name,
			label=name,
			color=color,
			size=size,
			borderWidth=border_width,
			title=f"{name} ({node_type})",
			font={"size": 14 if name == center else 10},
		)

	# Add edges
	for e in unique_edges:
		color = EDGE_COLORS.get(e["rel_type"], "#7f8c8d")
		net.add_edge(
			e["from"],
			e["to"],
			title=e["label"],
			label=e["label"],
			color=color,
			font={"size": 8, "color": "#aaaaaa"},
			arrows="to",
			width=1.5,
		)

	# Save
	p = Path(output_path)
	p.parent.mkdir(parents=True, exist_ok=True)
	net.save_graph(str(p))
	print(f"\nGraph saved to {p}")
	print(f"  Nodes: {len(graph_data['nodes'])}")
	print(f"  Edges: {len(unique_edges)}")
	return str(p)


async def main() -> None:
	parser = argparse.ArgumentParser(description="Visualize Nexus knowledge graph")
	parser.add_argument("entity", nargs="?", help="Entity to center the visualization on")
	parser.add_argument("--depth", type=int, default=1, help="Traversal depth (default: 1)")
	parser.add_argument("--limit", type=int, default=80, help="Max edges (default: 80)")
	parser.add_argument("--from-trace", help="Build from a trace results JSON file instead of Neo4j")
	parser.add_argument("--output", "-o", default="traces/graph.html", help="Output HTML file")
	args = parser.parse_args()

	if args.from_trace:
		graph_data = build_from_trace(args.from_trace)
	elif args.entity:
		graph_data = await query_neighborhood(args.entity, depth=args.depth, limit=args.limit)
	else:
		parser.error("Provide an entity name or --from-trace")

	render_html(graph_data, args.output)
	print(f"\nOpen in browser: file://{Path(args.output).resolve()}")


if __name__ == "__main__":
	asyncio.run(main())
