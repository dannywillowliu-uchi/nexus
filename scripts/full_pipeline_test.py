"""
Full pipeline edge-removal test.
For each benchmark case: remove edges, run Literature Agent + Graph enrichment, check recovery.
Run: PYTHONPATH=backend/src uv run python scripts/full_pipeline_test.py
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

import logging

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
# Show entity resolution and triple recovery logs
logging.getLogger("nexus.pipeline.orchestrator").setLevel(logging.INFO)
logging.getLogger("nexus.agents.literature.extract").setLevel(logging.INFO)
# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)

from dotenv import load_dotenv

load_dotenv()

from neo4j import GraphDatabase

from nexus.agents.literature.agent import run_literature_agent
from nexus.graph.abc import find_abc_hypotheses
from nexus.graph.client import graph_client
from nexus.pipeline.orchestrator import merge_triples_to_graph

# Sync driver for edge removal/restoration (simpler than async for setup/teardown)
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.getenv("NEO4J_PASSWORD")),
)


def disease_matches(query_disease: str, result_disease: str) -> bool:
    """Check if a result disease name matches the query disease."""
    q = query_disease.lower().strip()
    r = result_disease.lower().strip()
    if q == r or q in r or r in q:
        return True
    q_words = set(q.split())
    r_words = set(r.split())
    shared = q_words & r_words
    if len(shared) >= 2:
        return True
    significant_shared = {w for w in shared if len(w) >= 5}
    if significant_shared:
        return True
    return False


PIPELINE_TEST_CASES = [
    {
        "name": "Riluzole -> Melanoma",
        "drug": "Riluzole",
        "disease": "melanoma",
        "literature_query": "riluzole GRM1 metabotropic glutamate receptor melanoma",
        "expected_intermediary": "GRM1",
        "edges_to_remove": [
            {"from": "Riluzole", "to": "GRM1"},
            {"from": "GRM1", "to": "melanoma"},
        ],
    },
    {
        "name": "Sildenafil -> PAH",
        "drug": "Sildenafil",
        "disease": "pulmonary arterial hypertension",
        "literature_query": "sildenafil PDE5 phosphodiesterase pulmonary hypertension cGMP vasodilation",
        "expected_intermediary": "PDE5A",
        "edges_to_remove": [
            {"from": "PDE5A", "to": "pulmonary arterial hypertension"},
        ],
    },
    {
        "name": "Thalidomide -> Myeloma",
        "drug": "Thalidomide",
        "disease": "multiple myeloma",
        "literature_query": "thalidomide TNF cereblon CRBN multiple myeloma immunomodulatory",
        "expected_intermediary": "TNF",
        "edges_to_remove": [
            {"from": "TNF", "to": "plasma cell myeloma"},
            {"from": "IL6", "to": "plasma cell myeloma"},
            {"from": "VEGFA", "to": "plasma cell myeloma"},
        ],
    },
    {
        "name": "Valproic Acid -> GBM",
        "drug": "Valproic Acid",
        "disease": "glioblastoma",
        "literature_query": "valproic acid HDAC histone deacetylase glioblastoma epigenetic",
        "expected_intermediary": "HDAC2",
        "edges_to_remove": [
            {"from": "HDAC1", "to": "glioblastoma"},
            {"from": "HDAC2", "to": "glioblastoma"},
        ],
    },
    {
        "name": "Propranolol -> Hemangioma",
        "drug": "Propranolol",
        "disease": "hemangioma",
        "literature_query": "propranolol beta adrenergic receptor hemangioma VEGF angiogenesis",
        "expected_intermediary": "ADRB2",
        "edges_to_remove": [
            {"from": "ADRB1", "to": "hemangioma"},
            {"from": "ADRB2", "to": "hemangioma"},
        ],
    },
]


def remove_literature_edges(session, edges: list[dict]) -> int:
    """Remove specific LITERATURE_ASSOCIATION edges. Returns count removed."""
    removed = 0
    for edge in edges:
        result = session.run(
            """MATCH (a {name: $from_name})-[r:LITERATURE_ASSOCIATION]-(b)
            WHERE toLower(b.name) CONTAINS toLower($to_name)
            DELETE r
            RETURN count(r) AS deleted""",
            from_name=edge["from"],
            to_name=edge["to"],
        ).single()
        if result:
            removed += result["deleted"]
    return removed


def restore_literature_edges(session, edges: list[dict]) -> int:
    """Re-create LITERATURE_ASSOCIATION edges. Returns count restored."""
    restored = 0
    for edge in edges:
        result = session.run(
            """MATCH (a {name: $from_name})
            MATCH (b) WHERE toLower(b.name) CONTAINS toLower($to_name)
            MERGE (a)-[r:LITERATURE_ASSOCIATION]->(b)
            SET r.source = 'literature', r.is_novel = true, r.confidence = 0.92,
                r.predicate = 'associated_with', r.evidence_type = 'experimental',
                r.assertion_strength = 'direct', r.restored = true
            RETURN count(r) AS created""",
            from_name=edge["from"],
            to_name=edge["to"],
        ).single()
        if result:
            restored += result["created"]
    return restored


def verify_path_broken(session, drug: str, disease: str) -> bool:
    """Check if the ABC path Drug->Gene->Disease is broken after edge removal."""
    result = session.run(
        """MATCH (a:Drug)-[r1]-(b:Gene)-[r2:ASSOCIATED_WITH|LITERATURE_ASSOCIATION]-(c:Disease)
        WHERE a.name =~ $drug_pattern
        AND toLower(c.name) CONTAINS toLower($disease)
        RETURN count(DISTINCT c) AS cnt""",
        drug_pattern=f"(?i).*{drug}.*",
        disease=disease,
    ).single()
    return result["cnt"] == 0


async def run_pipeline_test():
    results = []

    # Connect the async graph client (needed by merge_triples_to_graph and find_abc_hypotheses)
    await graph_client.connect()

    for case in PIPELINE_TEST_CASES:
        print(f"\n{'='*70}")
        print(f"PIPELINE TEST: {case['name']}")
        print(f"{'='*70}")
        t0 = time.time()

        # Step 1: Remove LITERATURE_ASSOCIATION edges
        with driver.session() as session:
            removed = remove_literature_edges(session, case["edges_to_remove"])
            print(f"  Step 1: Removed {removed} LITERATURE_ASSOCIATION edges")

            # Step 2: Verify the ABC path is broken
            path_broken = verify_path_broken(session, case["drug"], case["disease"])
            if path_broken:
                print(f"  Step 2: Path broken confirmed — disease not reachable via ABC")
            else:
                print(f"  Step 2: WARNING — path still exists (may have ASSOCIATED_WITH edges)")

        # Step 3: Run Literature Agent to search PubMed and extract triples
        print(f"  Step 3: Searching PubMed for: '{case['literature_query']}'")
        try:
            lit_result = await run_literature_agent(case["literature_query"], max_papers=10)
            papers_found = len(lit_result.papers)
            triples_extracted = len(lit_result.triples)
            print(f"    Found {papers_found} papers, extracted {triples_extracted} triples")
            if lit_result.errors:
                print(f"    Errors: {lit_result.errors}")

            # Show triples mentioning our expected intermediary
            relevant_triples = [
                t for t in lit_result.triples
                if case["expected_intermediary"].lower() in t.subject.lower()
                or case["expected_intermediary"].lower() in t.object.lower()
            ]
            print(f"    Triples mentioning {case['expected_intermediary']}: {len(relevant_triples)}")
            for t in relevant_triples[:5]:
                print(f"      ({t.subject}) -[{t.predicate}]-> ({t.object}) [conf={t.confidence:.2f}]")

            # Show all triples for inspection
            if triples_extracted > 0 and not relevant_triples:
                print(f"    All {min(triples_extracted, 5)} triples (no match to {case['expected_intermediary']}):")
                for t in lit_result.triples[:5]:
                    print(f"      ({t.subject}) -[{t.predicate}]-> ({t.object}) [conf={t.confidence:.2f}]")

        except Exception as e:
            print(f"    ERROR in Literature Agent: {e}")
            lit_result = None
            papers_found = 0
            triples_extracted = 0
            relevant_triples = []

        # Step 4: Merge extracted triples into the graph
        edges_added = 0
        if lit_result and lit_result.triples:
            print(f"  Step 4: Merging {triples_extracted} triples into graph...")
            try:
                edges_added = await merge_triples_to_graph(lit_result.triples)
                print(f"    Added {edges_added} edges to graph")
            except Exception as e:
                print(f"    ERROR merging triples: {e}")
        else:
            print(f"  Step 4: No triples to merge")

        # Step 5: Run ABC traversal to check recovery
        print(f"  Step 5: Running ABC traversal for {case['drug']}...")
        rank = None
        found_intermediaries = []
        intermediary_found = False
        try:
            hypotheses = await find_abc_hypotheses(
                source_name=case["drug"],
                source_type="Drug",
                target_type="Disease",
                max_results=50,
                exclude_known=True,
                fuzzy=True,
            )
            print(f"    Got {len(hypotheses)} hypotheses")

            # Check if target disease appears
            for i, h in enumerate(hypotheses):
                if disease_matches(case["disease"], h.c_name):
                    rank = i + 1
                    found_intermediaries = [inter.get("b_name", "") for inter in h.intermediaries[:5]]
                    intermediary_found = case["expected_intermediary"].lower() in [fi.lower() for fi in found_intermediaries]
                    break

            if rank:
                print(f"    RECOVERED at rank {rank}")
                print(f"      Intermediaries: {found_intermediaries}")
                print(f"      Expected ({case['expected_intermediary']}): {'FOUND' if intermediary_found else 'NOT FOUND'}")
            else:
                print(f"    NOT RECOVERED in top 50 results")
                if hypotheses:
                    print(f"      Top 3: {[(h.c_name[:40], h.b_name) for h in hypotheses[:3]]}")

        except Exception as e:
            print(f"    ERROR in ABC traversal: {e}")

        elapsed = time.time() - t0
        result = {
            "case": case["name"],
            "papers_found": papers_found,
            "triples_extracted": triples_extracted,
            "relevant_triples": len(relevant_triples),
            "edges_added": edges_added,
            "recovered": rank is not None,
            "rank": rank,
            "intermediary_found": intermediary_found,
            "found_intermediaries": found_intermediaries,
            "path_was_broken": path_broken if 'path_broken' in dir() else None,
            "elapsed_seconds": round(elapsed, 1),
        }
        results.append(result)

        # Step 6: Restore original edges (clean up literature-extracted AND re-seed originals)
        print(f"  Step 6: Restoring original edges...")
        with driver.session() as session:
            # First remove any literature-extracted edges that might conflict
            # Then restore our original seeded edges
            restored = restore_literature_edges(session, case["edges_to_remove"])
            print(f"    Restored {restored} edges")

        print(f"  Completed in {elapsed:.1f}s")

    # Close async client
    await graph_client.close()

    # Summary
    print(f"\n{'='*70}")
    print("FULL PIPELINE TEST SUMMARY")
    print(f"{'='*70}")
    print(f"{'Case':<30s} {'Papers':>7s} {'Triples':>8s} {'Relevant':>9s} {'Added':>6s} {'Rank':>5s} {'Status':>8s}")
    print(f"{'-'*30} {'-'*7} {'-'*8} {'-'*9} {'-'*6} {'-'*5} {'-'*8}")

    for r in results:
        rank_str = str(r["rank"]) if r["recovered"] else "-"
        status = "PASS" if r["recovered"] else "FAIL"
        print(
            f"  {r['case']:<28s} {r['papers_found']:>7d} {r['triples_extracted']:>8d} "
            f"{r['relevant_triples']:>9d} {r['edges_added']:>6d} {rank_str:>5s} {status:>8s}"
        )

    recovered = sum(1 for r in results if r["recovered"])
    total = len(results)
    print(f"\nRecovery rate: {recovered}/{total} ({recovered/total*100:.0f}%)")
    print(f"Intermediary accuracy: {sum(1 for r in results if r.get('intermediary_found'))}/{total}")

    with open("pipeline_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to pipeline_test_results.json")


if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
