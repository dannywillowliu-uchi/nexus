"""
Load PrimeKG into Neo4j with tiered edge loading.

Run: .venv/bin/python scripts/load_primekg.py --tier 2 --no-clear
"""
import os
import time
import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

LABEL_MAP = {
	'gene/protein': 'Gene',
	'drug': 'Drug',
	'disease': 'Disease',
	'biological_process': 'BiologicalProcess',
	'molecular_function': 'MolecularFunction',
	'cellular_component': 'CellularComponent',
	'pathway': 'Pathway',
	'anatomy': 'Anatomy',
	'effect/phenotype': 'Phenotype',
	'phenotype': 'Phenotype',
	'exposure': 'Exposure',
}

TIER_1 = ['indication', 'contraindication', 'off-label use', 'drug_protein']
TIER_2 = ['disease_protein']
TIER_3 = ['protein_protein', 'bioprocess_protein', 'pathway_protein']
TIER_4 = [
	'molfunc_protein', 'cellcomp_protein', 'anatomy_protein_present',
	'anatomy_protein_absent', 'phenotype_protein', 'disease_phenotype_positive',
	'disease_phenotype_negative', 'drug_drug', 'exposure_protein',
	'exposure_disease', 'exposure_bioprocess', 'drug_effect',
]

TIERS = {
	1: TIER_1,
	2: TIER_1 + TIER_2,
	3: TIER_1 + TIER_2 + TIER_3,
	4: TIER_1 + TIER_2 + TIER_3 + TIER_4,
}


def clean_label(node_type: str) -> str:
	return LABEL_MAP.get(node_type.lower(), node_type.replace('/', '_').replace(' ', '_').title())


def clean_rel_type(relation: str) -> str:
	return str(relation).upper().replace(' ', '_').replace('-', '_').replace('/', '_')


def load_edges_for_relation(session, kg_subset, label=""):
	"""Load edges for a filtered subset. Returns count of edges loaded."""
	if len(kg_subset) == 0:
		return 0

	kg_subset = kg_subset.copy()
	kg_subset['x_label'] = kg_subset['x_type'].map(clean_label)
	kg_subset['y_label'] = kg_subset['y_type'].map(clean_label)
	kg_subset['rel_type'] = kg_subset['display_relation'].map(clean_rel_type)

	loaded = 0
	batch_size = 5000

	for (x_label, y_label, rel_type), group in kg_subset.groupby(['x_label', 'y_label', 'rel_type']):
		records = group[['x_index', 'y_index']].copy()
		records['x_index'] = records['x_index'].astype(int)
		records['y_index'] = records['y_index'].astype(int)

		record_list = records.to_dict('records')

		for i in range(0, len(record_list), batch_size):
			batch = record_list[i:i + batch_size]
			session.run(
				f"UNWIND $batch AS row "
				f"MATCH (a:{x_label} {{primekg_index: row.x_index}}) "
				f"MATCH (b:{y_label} {{primekg_index: row.y_index}}) "
				f"MERGE (a)-[r:`{rel_type}`]->(b) "
				f"SET r.source = 'primekg', r.is_novel = false",
				batch=batch,
			)

		loaded += len(record_list)

	return loaded


def load_graph(tier: int = 4, clear: bool = True, data_path: str = "data/primekg/kg.csv"):
	print(f"Reading PrimeKG from {data_path}...")
	t0 = time.time()

	if not os.path.exists(data_path) and not data_path.endswith(".gz"):
		gz_path = data_path + ".gz"
		if os.path.exists(gz_path):
			print(f"  CSV not found, using {gz_path}")
			data_path = gz_path

	kg = pd.read_csv(data_path, low_memory=False)
	print(f"Loaded {len(kg)} edges in {time.time() - t0:.1f}s")

	relations = TIERS[tier]

	with driver.session() as session:
		if clear:
			print("\nClearing existing graph...")
			session.run("MATCH (n) DETACH DELETE n")
		else:
			print("\nSkipping graph clear (--no-clear)")

		print("Creating indexes...")
		node_types = set(kg['x_type'].unique()) | set(kg['y_type'].unique())
		for nt in node_types:
			label = clean_label(nt)
			try:
				session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.primekg_index IS UNIQUE")
			except Exception as e:
				print(f"  Constraint for {label}: {e}")

		for label in ['Drug', 'Disease', 'Gene', 'Phenotype']:
			try:
				session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.name)")
			except Exception as e:
				print(f"  Name index for {label}: {e}")

		print("\nCollecting unique nodes...")
		t0 = time.time()

		x_nodes = kg[['x_index', 'x_id', 'x_name', 'x_type']].drop_duplicates(subset='x_index')
		x_nodes.columns = ['primekg_index', 'node_id', 'name', 'node_type']

		y_nodes = kg[['y_index', 'y_id', 'y_name', 'y_type']].drop_duplicates(subset='y_index')
		y_nodes.columns = ['primekg_index', 'node_id', 'name', 'node_type']

		all_nodes = pd.concat([x_nodes, y_nodes]).drop_duplicates(subset='primekg_index')
		all_nodes['primekg_index'] = all_nodes['primekg_index'].astype(int)
		all_nodes['node_id'] = all_nodes['node_id'].astype(str)
		all_nodes['name'] = all_nodes['name'].astype(str)
		all_nodes['label'] = all_nodes['node_type'].map(clean_label)

		print(f"Found {len(all_nodes)} unique nodes in {time.time() - t0:.1f}s")

		print("\nCreating nodes...")
		t0 = time.time()
		batch_size = 5000

		for label, group in all_nodes.groupby('label'):
			records = group[['primekg_index', 'node_id', 'name', 'node_type']].to_dict('records')
			for i in range(0, len(records), batch_size):
				batch = records[i:i + batch_size]
				session.run(
					f"UNWIND $batch AS row "
					f"MERGE (n:{label} {{primekg_index: row.primekg_index}}) "
					f"SET n.name = row.name, n.node_id = row.node_id, n.node_type = row.node_type",
					batch=batch,
				)
			print(f"  {label}: {len(records)} nodes")

		print(f"All nodes created in {time.time() - t0:.1f}s")

		print(f"\n{'='*60}")
		print(f"TIERED EDGE LOADING (tier {tier}: {len(relations)} relation types)")
		print(f"{'='*60}")
		total_loaded = 0

		for rel in relations:
			subset = kg[kg['relation'] == rel]
			print(f"  Loading '{rel}': {len(subset)} edges...")
			count = load_edges_for_relation(session, subset)
			total_loaded += count
			print(f"    Loaded: {count} | Running total: {total_loaded}")

		print(f"\n{'='*60}")
		print(f"TOTAL EDGES LOADED: {total_loaded}")
		print(f"{'='*60}")

	print("\nVerifying...")
	with driver.session() as session:
		node_count = session.run("MATCH (n) RETURN count(n) as c").single()['c']
		edge_count = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()['c']
		print(f"Nodes: {node_count}, Edges: {edge_count}")

		print("\nEdge breakdown:")
		result = session.run(
			"MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC"
		)
		for record in result:
			print(f"  {record['rel_type']}: {record['count']}")

		print("\n--- DEMO TEST: Riluzole ABC paths ---")
		result = session.run("""
			MATCH (a:Drug)-[r1]-(b:Gene)-[r2]-(c:Disease)
			WHERE a.name =~ '(?i).*riluzole.*'
			AND NOT (a)-[:INDICATION]-(c)
			RETURN c.name, collect(DISTINCT b.name) AS genes, count(DISTINCT b) AS gene_count
			ORDER BY gene_count DESC
			LIMIT 10
		""")
		for record in result:
			genes = record['genes']
			print(f"  {record['c.name']}: {record['gene_count']} genes — {genes[:5]}{'...' if len(genes) > 5 else ''}")


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="Load PrimeKG into Neo4j")
	parser.add_argument("--tier", type=int, default=4, choices=[1, 2, 3, 4])
	parser.add_argument("--no-clear", action="store_true")
	parser.add_argument("--data-path", default="data/primekg/kg.csv")
	args = parser.parse_args()
	load_graph(tier=args.tier, clear=not args.no_clear, data_path=args.data_path)
	driver.close()
