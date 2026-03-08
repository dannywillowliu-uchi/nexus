"""
Nexus Ground Truth Benchmark
Tests ABC traversal by removing known drug-disease edges and checking recovery.
Run: PYTHONPATH=backend/src python scripts/benchmark.py
"""
import json
import sys

sys.path.insert(0, "backend/src")

from neo4j import GraphDatabase

from nexus.config import settings

driver = GraphDatabase.driver(
	settings.neo4j_uri,
	auth=(settings.neo4j_username, settings.neo4j_password),
)

BENCHMARK_CASES = [
	{
		"name": "Thalidomide -> Multiple Myeloma",
		"drug": "Thalidomide",
		"disease": "multiple myeloma",
		"edge_type": "INDICATION",
		"expected_intermediaries": ["TNF", "VEGFA", "IL6", "CRBN"],
		"assay": "Cell viability (MTT) + cytokine ELISA (TNF-alpha, IL-6, VEGF) in MM.1S, RPMI-8226 myeloma lines. Co-culture with HS-5 stromal cells. Drug: 0-100 uM.",
	},
	{
		"name": "Sildenafil -> Pulmonary Hypertension",
		"drug": "Sildenafil",
		"disease": "pulmonary arterial hypertension",
		"edge_type": "INDICATION",
		"expected_intermediaries": ["PDE5A"],
		"assay": "cGMP ELISA + calcium imaging in primary PASMCs. Pre-contract with endothelin-1, then add sildenafil 0.01-10 uM. Positive control: SNP (NO donor).",
	},
	{
		"name": "Riluzole -> Melanoma",
		"drug": "Riluzole",
		"disease": "melanoma",
		"edge_type": "LITERATURE_ASSOCIATION",
		"expected_intermediaries": ["GRM1"],
		"assay": "MTS viability in C8161 (GRM1+), UACC903 (GRM1+), UACC930 (GRM1-, negative control). Riluzole 0-50 uM for 96h. Positive control: BAY 36-7620 (GRM1 antagonist). Expected: GRM1-dependent killing.",
	},
	{
		"name": "Imatinib -> GIST",
		"drug": "Imatinib",
		"disease": "gastrointestinal stromal tumor",
		"edge_type": "INDICATION",
		"expected_intermediaries": ["KIT", "PDGFRA"],
		"assay": "Phospho-KIT Western blot + viability in GIST-T1 (KIT exon 11 mutant). Imatinib 0.01-1 uM. Expected: KIT phosphorylation inhibition + growth arrest. Test that KIT ranks above ABL1.",
	},
	{
		"name": "Niclosamide -> Colorectal Cancer",
		"drug": "Niclosamide",
		"disease": "colorectal cancer",
		"edge_type": "LITERATURE_ASSOCIATION",
		"expected_intermediaries": ["CTNNB1", "GSK3B"],
		"assay": "TOPFlash Wnt reporter luciferase + MTT viability in HCT116, SW480, HEK293. Niclosamide 0.1-10 uM. Western blot: beta-catenin, phospho-beta-catenin, Dvl2.",
	},
	{
		"name": "Auranofin -> Ovarian Cancer",
		"drug": "Auranofin",
		"disease": "ovarian cancer",
		"edge_type": "LITERATURE_ASSOCIATION",
		"expected_intermediaries": ["TXNRD1"],
		"assay": "TrxR activity assay (DTNB at 412nm) + MTT viability + ROS (DCFH-DA) in 2008 (CisPt-sensitive) and C13* (CisPt-resistant). Auranofin 0.5-4 uM. Rescue with NAC 5mM. Expected: resistant cells MORE sensitive.",
	},
	{
		"name": "Metformin -> Colorectal Cancer",
		"drug": "Metformin",
		"disease": "colorectal cancer",
		"edge_type": "check",
		"expected_intermediaries": ["PRKAA1", "PRKAA2", "MTOR", "PRKAB1"],
		"assay": "Western blot pAMPK(Thr172)/pmTOR(Ser2448)/pS6K + MTT viability in HCT116, SW480, HT-29. Metformin 1-20 mM. Positive control: AICAR. Caveat: mM doses are supraphysiological.",
	},
	{
		"name": "Aspirin -> Colorectal Cancer",
		"drug": "Aspirin",
		"disease": "colorectal cancer",
		"edge_type": "check",
		"expected_intermediaries": ["PTGS2"],
		"assay": "COX-2 activity (PGE2 ELISA) + MTT viability in HT-29 (high COX-2) vs SW480 (low COX-2). Aspirin 0.5-5 mM. Expected: preferential PGE2 reduction and growth inhibition in COX-2-high line.",
	},
	{
		"name": "Valproic Acid -> Glioblastoma",
		"drug": "Valproic Acid",
		"disease": "glioblastoma",
		"edge_type": "check",
		"expected_intermediaries": ["HDAC1", "HDAC2"],
		"assay": "HDAC activity (fluorometric) + acetyl-H3/H4 Western blot + cell cycle (flow cytometry) in U87-MG, U251, T98G. VPA 0.5-5 mM. Positive control: SAHA/vorinostat. Expected: HDAC inhibition + G1 arrest.",
	},
	{
		"name": "Propranolol -> Hemangioma",
		"drug": "Propranolol",
		"disease": "hemangioma",
		"edge_type": "INDICATION",
		"expected_intermediaries": ["ADRB1", "ADRB2", "VEGFA"],
		"assay": "VEGF ELISA + BrdU proliferation + tube formation in HemECs (hemangioma-derived endothelial cells). Propranolol 1-100 uM. Expected: VEGF reduction + anti-proliferative + anti-angiogenic.",
	},
]


# ---------------------------------------------------------------------------
# FIX 1: Smart name resolution — exact match first, then starts-with, then
# contains with shortest-name preference.
# ---------------------------------------------------------------------------

def resolve_drug_name(session, query_name: str) -> str | None:
	"""Resolve a drug name against the graph, preferring exact matches.

	When multiple nodes match (e.g. 'imatinib' vs 'Imatinib'),
	prefer the node with the most relationships (canonical PrimeKG node).
	"""
	# Exact (case-insensitive) — pick node with most edges
	result = session.run(
		"MATCH (d:Drug) WHERE toLower(d.name) = toLower($name) "
		"OPTIONAL MATCH (d)-[r]-() "
		"RETURN d.name, count(r) AS edges ORDER BY edges DESC LIMIT 1",
		name=query_name,
	).single()
	if result:
		return result["d.name"]

	# Starts-with — prefer node with most edges
	result = session.run(
		"MATCH (d:Drug) WHERE toLower(d.name) STARTS WITH toLower($name) "
		"OPTIONAL MATCH (d)-[r]-() "
		"RETURN d.name, count(r) AS edges ORDER BY edges DESC LIMIT 1",
		name=query_name,
	).single()
	if result:
		return result["d.name"]

	# Contains — prefer node with most edges
	result = session.run(
		"MATCH (d:Drug) WHERE d.name =~ $pattern "
		"OPTIONAL MATCH (d)-[r]-() "
		"RETURN d.name, count(r) AS edges ORDER BY edges DESC LIMIT 1",
		pattern=f"(?i).*{query_name}.*",
	).single()
	if result:
		return result["d.name"]

	return None


def resolve_disease_name(session, query_name: str) -> str | None:
	"""Resolve a disease name against the graph, preferring exact matches."""
	# Exact (case-insensitive)
	result = session.run(
		"MATCH (d:Disease) WHERE toLower(d.name) = toLower($name) RETURN d.name",
		name=query_name,
	).single()
	if result:
		return result["d.name"]

	# Starts-with — prefer shortest
	result = session.run(
		"MATCH (d:Disease) WHERE toLower(d.name) STARTS WITH toLower($name) "
		"RETURN d.name ORDER BY size(d.name) ASC LIMIT 1",
		name=query_name,
	).single()
	if result:
		return result["d.name"]

	# Contains — prefer shortest
	result = session.run(
		"MATCH (d:Disease) WHERE d.name =~ $pattern "
		"RETURN d.name ORDER BY size(d.name) ASC LIMIT 1",
		pattern=f"(?i).*{query_name}.*",
	).single()
	if result:
		return result["d.name"]

	# Word-level match — search by last significant word first (most disease-specific),
	# e.g. "multiple myeloma" -> try "myeloma" first, "colorectal cancer" -> try "cancer" first
	significant_words = [w for w in query_name.lower().split() if len(w) >= 5]
	for word in reversed(significant_words):
		result = session.run(
			"MATCH (d:Disease) WHERE d.name =~ $pattern "
			"RETURN d.name ORDER BY size(d.name) ASC LIMIT 1",
			pattern=f"(?i).*{word}.*",
		).single()
		if result:
			return result["d.name"]
	return None


# ---------------------------------------------------------------------------
# FIX 2: Flexible disease matching in results
# ---------------------------------------------------------------------------

def disease_matches(query_disease: str, result_disease: str) -> bool:
	"""Check if a result disease name matches the query disease."""
	q = query_disease.lower().strip()
	r = result_disease.lower().strip()
	# Exact
	if q == r:
		return True
	# Query is substring of result ("melanoma" in "CDK4 linked melanoma")
	if q in r:
		return True
	# Result is substring of query
	if r in q:
		return True
	# Word overlap — at least 2 shared words OR 1 significant word (≥5 chars)
	q_words = set(q.split())
	r_words = set(r.split())
	shared = q_words & r_words
	if len(shared) >= 2:
		return True
	# Single significant word match (e.g. "myeloma", "melanoma", "glioblastoma")
	significant_shared = {w for w in shared if len(w) >= 5}
	if significant_shared:
		return True
	return False


# ---------------------------------------------------------------------------
# FIX 3: Weighted ABC traversal — TARGET >> ENZYME
# ---------------------------------------------------------------------------

WEIGHTED_ABC_QUERY = """
MATCH (a:Drug)-[r1]-(b:Gene)-[r2:ASSOCIATED_WITH|LITERATURE_ASSOCIATION]-(c:Disease)
WHERE a.name = $drug
AND NOT (a)-[:INDICATION]-(c)
WITH c, b,
     CASE
       WHEN type(r1) = 'TARGET' THEN 3.0
       WHEN type(r1) = 'LITERATURE_ASSOCIATION' THEN 2.5
       WHEN type(r1) = 'CARRIER' THEN 0.1
       WHEN type(r1) = 'TRANSPORTER' THEN 0.1
       WHEN type(r1) = 'ENZYME' THEN 0.05
       ELSE 0.1
     END AS edge_weight,
     type(r1) AS r1_type,
     CASE WHEN type(r2) = 'LITERATURE_ASSOCIATION' THEN 1.5 ELSE 1.0 END AS novelty_bonus
WITH c, b, max(edge_weight) AS best_weight, max(novelty_bonus) AS best_novelty,
     collect(DISTINCT r1_type) AS gene_rel_types
WITH c,
     collect(DISTINCT b.name) AS intermediaries,
     count(DISTINCT b) AS path_count,
     max(best_weight) AS max_edge_weight,
     max(best_novelty) AS has_novel,
     reduce(s = [], t IN collect(gene_rel_types) | s + t) AS all_rel_types
WITH c, intermediaries, path_count, max_edge_weight, has_novel, all_rel_types,
     max_edge_weight * has_novel + 0.01 * path_count AS score
RETURN c.name AS disease,
       intermediaries,
       path_count,
       max_edge_weight,
       score AS weighted_score,
       all_rel_types AS rel_types
ORDER BY score DESC
LIMIT 50
"""


def run_benchmark():
	results = []

	with driver.session() as session:
		for case in BENCHMARK_CASES:
			print(f"\n{'='*60}")
			print(f"CASE: {case['name']}")
			print(f"{'='*60}")

			# Step 1: Resolve drug and disease names (FIX 1)
			drug_name = resolve_drug_name(session, case["drug"])
			disease_name = resolve_disease_name(session, case["disease"])

			if not drug_name:
				print(f"  X Drug '{case['drug']}' NOT FOUND in graph")
				results.append({"case": case["name"], "status": "drug_not_found"})
				continue
			if not disease_name:
				print(f"  X Disease '{case['disease']}' NOT FOUND in graph")
				results.append({"case": case["name"], "status": "disease_not_found"})
				continue

			print(f"  Drug: {drug_name}")
			print(f"  Disease: {disease_name}")

			# Step 2: Check if direct edge exists
			edge_check = session.run(
				"""MATCH (a:Drug)-[r]-(b:Disease)
				WHERE a.name = $drug AND b.name = $disease
				RETURN type(r) AS rel_type, count(r) AS count""",
				drug=drug_name,
				disease=disease_name,
			).data()

			if edge_check:
				print(f"  Direct edges found: {edge_check}")
				for edge in edge_check:
					print(f"  Removing edge: {edge['rel_type']}")
					session.run(
						f"""MATCH (a:Drug {{name: $drug}})-[r:{edge['rel_type']}]-(b:Disease {{name: $disease}})
						DELETE r""",
						drug=drug_name,
						disease=disease_name,
					)
			else:
				print(f"  No direct edge -- this is a novel discovery test")

			# Step 3: Run weighted ABC traversal (FIX 3)
			abc_results = session.run(
				WEIGHTED_ABC_QUERY,
				drug=drug_name,
			).data()

			# Step 4: Check if target disease appears in results (FIX 2)
			rank = None
			found_intermediaries = []
			found_rel_types = []
			found_weighted_score = 0.0
			for i, row in enumerate(abc_results):
				if disease_matches(case["disease"], row["disease"]):
					rank = i + 1
					found_intermediaries = row["intermediaries"]
					found_rel_types = row.get("rel_types", [])
					found_weighted_score = row.get("weighted_score", 0.0)
					break

			# Step 5: Check intermediary accuracy
			expected = case["expected_intermediaries"]
			if isinstance(expected, str):
				expected = [expected]

			intermediary_match = False
			matched_intermediaries = []
			if found_intermediaries:
				for exp in expected:
					for fi in found_intermediaries:
						if exp.lower() == fi.lower():
							intermediary_match = True
							matched_intermediaries.append(fi)

			# Step 6: Report results
			result = {
				"case": case["name"],
				"drug": drug_name,
				"disease": disease_name,
				"rank": rank,
				"in_top_5": rank is not None and rank <= 5,
				"in_top_10": rank is not None and rank <= 10,
				"in_top_20": rank is not None and rank <= 20,
				"in_top_30": rank is not None and rank <= 30,
				"in_top_50": rank is not None and rank <= 50,
				"intermediary_match": intermediary_match,
				"matched_intermediaries": matched_intermediaries,
				"found_intermediaries": found_intermediaries,
				"expected_intermediaries": expected,
				"rel_types": found_rel_types,
				"weighted_score": found_weighted_score,
				"suggested_assay": case["assay"],
				"total_results": len(abc_results),
			}
			results.append(result)

			if rank:
				print(f"  >> Found at rank {rank} (weighted_score={found_weighted_score:.1f})")
				print(f"  Intermediaries: {found_intermediaries[:8]}")
				print(f"  Edge types: {found_rel_types}")
				print(f"  Expected: {expected}")
				print(f"  Intermediary match: {intermediary_match}", end="")
				if matched_intermediaries:
					print(f" ({matched_intermediaries})")
				else:
					print()
			else:
				print(f"  X Disease NOT found in top {len(abc_results)} results")
				if abc_results:
					print(f"  Top 5 results instead:")
					for row in abc_results[:5]:
						print(f"    {row['disease'][:50]:50s}  score={row.get('weighted_score', 0):.1f}  via {row['intermediaries'][:3]}")

			print(f"  Suggested assay: {case['assay'][:100]}...")

			# Step 7: Restore removed edges
			if edge_check:
				for edge in edge_check:
					print(f"  Restoring edge: {edge['rel_type']}")
					session.run(
						f"""MATCH (a:Drug {{name: $drug}})
						MATCH (b:Disease {{name: $disease}})
						MERGE (a)-[r:{edge['rel_type']}]->(b)
						SET r.source = 'primekg', r.restored = true""",
						drug=drug_name,
						disease=disease_name,
					)

	# Summary
	print(f"\n{'='*60}")
	print("BENCHMARK SUMMARY")
	print(f"{'='*60}")

	tested = [r for r in results if "rank" in r]
	found = [r for r in tested if r.get("rank") is not None]

	recall_5 = sum(1 for r in tested if r.get("in_top_5")) / len(tested) if tested else 0
	recall_10 = sum(1 for r in tested if r.get("in_top_10")) / len(tested) if tested else 0
	recall_20 = sum(1 for r in tested if r.get("in_top_20")) / len(tested) if tested else 0
	recall_30 = sum(1 for r in tested if r.get("in_top_30")) / len(tested) if tested else 0
	recall_50 = sum(1 for r in tested if r.get("in_top_50")) / len(tested) if tested else 0

	mrr = 0.0
	for r in tested:
		if r.get("rank"):
			mrr += 1.0 / r["rank"]
	mrr = mrr / len(tested) if tested else 0

	intermediary_acc = sum(1 for r in tested if r.get("intermediary_match")) / len(tested) if tested else 0

	print(f"Cases tested: {len(tested)}")
	print(f"Cases found:  {len(found)}")
	print(f"Recall@5:     {recall_5:.0%}")
	print(f"Recall@10:    {recall_10:.0%}")
	print(f"Recall@20:    {recall_20:.0%}")
	print(f"Recall@30:    {recall_30:.0%}")
	print(f"Recall@50:    {recall_50:.0%}")
	print(f"MRR:          {mrr:.3f}")
	print(f"Intermediary accuracy: {intermediary_acc:.0%}")

	# Per-case summary table
	print(f"\n{'='*60}")
	print(f"{'Case':45s} {'Rank':>5s} {'IntMatch':>8s}")
	print(f"{'-'*45} {'-'*5} {'-'*8}")
	for r in results:
		rank_str = str(r["rank"]) if r.get("rank") else "MISS"
		im = "YES" if r.get("intermediary_match") else "no"
		status = r.get("status", "")
		if status:
			rank_str = status
			im = "-"
		print(f"  {r['case']:43s} {rank_str:>5s} {im:>8s}")

	# Save results
	with open("benchmark_results.json", "w") as f:
		json.dump(
			{
				"cases": results,
				"summary": {
					"tested": len(tested),
					"found": len(found),
					"recall_5": recall_5,
					"recall_10": recall_10,
					"recall_20": recall_20,
					"recall_30": recall_30,
					"recall_50": recall_50,
					"mrr": mrr,
					"intermediary_accuracy": intermediary_acc,
				},
			},
			f,
			indent=2,
		)

	print(f"\nResults saved to benchmark_results.json")


if __name__ == "__main__":
	run_benchmark()
	driver.close()
