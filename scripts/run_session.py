#!/usr/bin/env python3
"""CLI runner for testing the Nexus pipeline with full tracing.

Usage:
	python scripts/run_session.py "curcumin and inflammation"
	python scripts/run_session.py "alzheimer's disease" --entity "Alzheimer" --type Disease
	python scripts/run_session.py "BRCA1 cancer" --max-papers 5 --no-graph
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from nexus.config import settings
from nexus.tracing.tracer import Tracer, set_tracer


def setup_logging(verbose: bool = False) -> None:
	level = logging.DEBUG if verbose else logging.WARNING
	logging.basicConfig(
		level=level,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
		datefmt="%H:%M:%S",
	)


def check_config() -> dict[str, bool]:
	"""Check which services are configured."""
	checks = {
		"anthropic": bool(settings.anthropic_api_key),
		"ncbi": bool(settings.ncbi_api_key),
		"semantic_scholar": bool(settings.semantic_scholar_api_key),
		"neo4j": bool(settings.neo4j_uri and settings.neo4j_username),
		"supabase": bool(settings.supabase_url),
		"tamarind": bool(settings.tamarind_bio_api_key),
	}
	print("\n--- Service Configuration ---")
	for service, configured in checks.items():
		status = "OK" if configured else "MISSING"
		print(f"  {service:20s} [{status}]")
	print()
	return checks


async def run_literature_only(query: str, max_papers: int, tracer: Tracer) -> dict:
	"""Run just the literature pipeline (no graph/Neo4j required)."""
	from nexus.agents.literature.agent import run_literature_agent

	with tracer.span("pipeline", input_data={"query": query, "mode": "literature_only"}) as pipeline_span:
		lit_result = await run_literature_agent(query, max_papers=max_papers)
		pipeline_span.set_output({
			"papers": len(lit_result.papers),
			"triples": len(lit_result.triples),
			"errors": lit_result.errors,
		})

	return {
		"papers": [{"title": p.title, "id": p.paper_id, "source": p.source, "year": p.year} for p in lit_result.papers],
		"triples": [
			{"subject": t.subject, "predicate": t.predicate, "object": t.object, "confidence": t.confidence}
			for t in lit_result.triples
		],
		"errors": lit_result.errors,
	}


async def run_full_pipeline(
	query: str,
	start_entity: str | None,
	start_type: str,
	max_hypotheses: int,
	max_pivots: int,
	tracer: Tracer,
	session_id: str,
) -> dict:
	"""Run the full pipeline including graph search, validation, and lab experiments."""
	from nexus.db.models import SessionRequest
	from nexus.graph.client import graph_client
	from nexus.harness.event_store import EventStore
	from nexus.harness.runner import run_research_session

	with tracer.span("pipeline", input_data={
		"query": query,
		"entity": start_entity,
		"type": start_type,
		"mode": "full",
	}) as pipeline_span:
		# Connect to Neo4j
		with tracer.span("neo4j_connect") as conn_span:
			try:
				await graph_client.connect()
				node_count = await graph_client.node_count()
				conn_span.set_output({"nodes": node_count})
			except Exception as exc:
				conn_span.set_error(str(exc))
				raise

		try:
			# Set up event store with live CLI output
			event_store = EventStore()
			event_store.register_callback(
				lambda e: print(f"  [EVENT] {e.event_type}: {json.dumps(e.output_data, default=str)[:120] if e.output_data else ''}")
			)

			# Build session request
			request = SessionRequest(
				query=query,
				start_entity=start_entity,
				start_type=start_type,
				max_hypotheses=max_hypotheses,
				max_pivots=max_pivots,
			)

			# Run complete research session (pipeline + validation + lab experiments + reasoning)
			result = await run_research_session(session_id, request, event_store)

			pipeline_span.set_output({
				"hypotheses": len(result.get("hypotheses", [])),
				"pivot_count": result.get("pivot_count", 0),
				"events_count": result.get("events_count", 0),
			})

		finally:
			await graph_client.close()

	return result


async def main() -> None:
	parser = argparse.ArgumentParser(description="Run a Nexus discovery session with tracing")
	parser.add_argument("query", help="Research query (e.g., 'curcumin and inflammation')")
	parser.add_argument("--entity", help="Start entity name (defaults to query)")
	parser.add_argument("--type", default="Disease", help="Start entity type (default: Disease)")
	parser.add_argument("--max-papers", type=int, default=5, help="Max papers to search (default: 5)")
	parser.add_argument("--max-hypotheses", type=int, default=10, help="Max hypotheses (default: 10)")
	parser.add_argument("--max-pivots", type=int, default=2, help="Max pivots (default: 2)")
	parser.add_argument("--no-graph", action="store_true", help="Skip graph stage (literature only)")
	parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
	parser.add_argument("--output", "-o", help="Output trace file (default: traces/<session_id>.json)")
	args = parser.parse_args()

	setup_logging(args.verbose)

	session_id = str(uuid.uuid4())[:8]
	tracer = Tracer(session_id=session_id, verbose=True)
	set_tracer(tracer)

	print(f"\n{'='*60}")
	print(f"NEXUS DISCOVERY SESSION | {session_id}")
	print(f"Query: {args.query}")
	print(f"{'='*60}")

	config = check_config()

	if not config["anthropic"]:
		print("ERROR: ANTHROPIC_API_KEY is required for triple extraction.")
		sys.exit(1)

	skip_graph = args.no_graph or not config["neo4j"]
	if not config["neo4j"] and not args.no_graph:
		print("WARNING: Neo4j not configured. Running literature-only mode.")
		print("  Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in .env to enable graph search.\n")

	try:
		if skip_graph:
			results = await run_literature_only(args.query, args.max_papers, tracer)
		else:
			results = await run_full_pipeline(
				query=args.query,
				start_entity=args.entity,
				start_type=args.type,
				max_hypotheses=args.max_hypotheses,
				max_pivots=args.max_pivots,
				tracer=tracer,
				session_id=session_id,
			)

		# Print results summary
		tracer.print_summary()

		print("--- RESULTS ---")
		if "papers" in results:
			print(f"\nPapers found: {len(results['papers'])}")
			for p in results["papers"][:5]:
				print(f"  [{p['source']}] {p['title'][:80]}")

		if "triples" in results:
			print(f"\nTriples extracted: {len(results['triples'])}")
			for t in results["triples"][:10]:
				print(f"  {t['subject']} --{t['predicate']}--> {t['object']} (conf: {t['confidence']:.2f})")

		if "hypotheses" in results and results["hypotheses"]:
			print(f"\nTop hypotheses: {len(results['hypotheses'])}")
			for idx, h in enumerate(results["hypotheses"][:5]):
				print(f"\n  [{idx+1}] {h.get('title', '?')} | score: {h.get('overall_score', 0):.3f}")
				if h.get("summary"):
					print(f"      Summary: {h['summary'][:120]}")

				# Validation result
				vr = h.get("validation_result", {})
				if vr:
					print(f"      Validation: {vr.get('verdict', 'N/A')} (confidence: {vr.get('confidence', 'N/A')})")

				# Lab experiment results
				exp = h.get("experiment", {})
				if exp and exp.get("status") != "error":
					print(f"\n      --- Lab Experiment ---")
					# Protocol validation
					validation = exp.get("validation", {})
					if validation:
						print(f"      Protocol valid: {validation.get('valid', '?')}")
						for w in validation.get("warnings", []):
							print(f"        Warning: {w}")

					# Dry run
					dry_run = exp.get("dry_run", {})
					for log_line in dry_run.get("logs", []):
						print(f"        {log_line}")

					# Simulated results
					sim = exp.get("simulated_results", {})
					if sim:
						# QC metrics
						qc = sim.get("qc_metrics", {})
						if qc:
							z = qc.get("z_factor", 0)
							s2b = qc.get("signal_to_background", 0)
							cv = qc.get("cv_percent", 0)
							print(f"      QC Metrics: Z-factor={z:.3f} ({'PASS' if qc.get('pass_z_factor') else 'FAIL'}) | "
								  f"S/B={s2b:.1f} ({'PASS' if qc.get('pass_s2b') else 'FAIL'}) | CV={cv:.1f}%")

						# Dose-response table
						dose_resp = sim.get("dose_response", [])
						if dose_resp:
							print(f"      Dose-Response ({len(dose_resp)} points):")
							print(f"        {'Conc (uM)':>10}  {'Mean':>8}  {'Std':>8}  {'CV%':>6}")
							print(f"        {'-'*10}  {'-'*8}  {'-'*8}  {'-'*6}")
							for pt in dose_resp:
								print(f"        {pt['concentration_uM']:>10.2f}  {pt['mean_response']:>8.4f}  {pt['std']:>8.4f}  {pt['cv_percent']:>6.1f}")

						# Analysis
						analysis = sim.get("analysis", {})
						if analysis:
							active = analysis.get("active", False)
							print(f"      Activity: {'ACTIVE' if active else 'INACTIVE'}")
							if active:
								print(f"        IC50 = {analysis.get('ic50_uM', 'N/A')} uM | "
									  f"Hill = {analysis.get('hill_coefficient', 'N/A')} | "
									  f"Max inhibition = {analysis.get('max_inhibition_percent', 'N/A')}%")

					# Interpretation
					interp = exp.get("interpretation", {})
					if interp:
						verdict = interp.get("verdict", "N/A").upper()
						conf = interp.get("confidence", 0)
						print(f"      Verdict: {verdict} (confidence: {conf:.2f})")
						print(f"      Reasoning: {interp.get('reasoning', 'N/A')[:200]}")
						concerns = interp.get("concerns", [])
						if concerns:
							print(f"      Concerns:")
							for c in concerns:
								print(f"        - {c}")
						next_steps = interp.get("next_steps", [])
						if next_steps:
							print(f"      Next steps:")
							for s in next_steps:
								print(f"        - {s}")

					# Retry experiment (if refuted and retried)
					retry = h.get("experiment_retry", {})
					if retry:
						print(f"\n      --- Retry Experiment (standard budget) ---")
						retry_interp = retry.get("interpretation", {})
						if retry_interp:
							print(f"      Verdict: {retry_interp.get('verdict', 'N/A').upper()} "
								  f"(confidence: {retry_interp.get('confidence', 0):.2f})")
							print(f"      Reasoning: {retry_interp.get('reasoning', 'N/A')[:200]}")

				elif exp.get("status") == "error":
					print(f"      Experiment error: {exp.get('error', 'unknown')}")

		if results.get("pivot_count"):
			print(f"\nPivots: {results['pivot_count']}")
		if results.get("events_count"):
			print(f"Events: {results['events_count']}")

		if results.get("errors"):
			print(f"\nErrors: {len(results['errors'])}")
			for e in results["errors"]:
				print(f"  ! {e}")

		# Save trace
		trace_dir = Path(__file__).parent.parent / "traces"
		trace_path = args.output or str(trace_dir / f"{session_id}.json")
		tracer.save(trace_path)

		# Also save results
		results_path = trace_dir / f"{session_id}-results.json"
		results_path.parent.mkdir(parents=True, exist_ok=True)
		with open(results_path, "w") as f:
			json.dump(results, f, indent=2, default=str)
		print(f"Results saved to {results_path}")

	except KeyboardInterrupt:
		print("\n\nInterrupted. Saving partial trace...")
		trace_dir = Path(__file__).parent.parent / "traces"
		tracer.save(trace_dir / f"{session_id}-partial.json")
	except Exception as exc:
		print(f"\nFATAL: {exc}")
		tracer.print_summary()
		trace_dir = Path(__file__).parent.parent / "traces"
		tracer.save(trace_dir / f"{session_id}-error.json")
		raise


if __name__ == "__main__":
	asyncio.run(main())
