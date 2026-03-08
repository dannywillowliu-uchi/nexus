from __future__ import annotations

import asyncio
import logging

from nexus.heartbeat.delta import detect_deltas
from nexus.heartbeat.ingest import ingest_recent_papers

logger = logging.getLogger(__name__)


async def run_heartbeat_cycle(
	queries: list[str],
	days: int = 7,
) -> dict:
	"""Run a single heartbeat cycle: ingest papers, detect deltas.

	Returns {"total_papers": int, "total_triples": int, "high_delta_edges": int}
	"""
	total_papers = 0
	total_triples = 0
	all_triples: list[dict] = []

	for query in queries:
		result = await ingest_recent_papers(query, days=days)
		total_papers += result["papers_found"]
		total_triples += result["triples_extracted"]
		all_triples.extend(result["triples"])

	high_deltas = await detect_deltas(all_triples)

	return {
		"total_papers": total_papers,
		"total_triples": total_triples,
		"high_delta_edges": len(high_deltas),
	}


async def start_heartbeat_loop(
	queries: list[str],
	interval_hours: int = 24,
	max_cycles: int | None = None,
) -> None:
	"""Run heartbeat cycles on an interval.

	Args:
		queries: Disease areas to monitor.
		interval_hours: Hours between cycles.
		max_cycles: Maximum number of cycles. None = infinite.
	"""
	cycles_run = 0

	while True:
		logger.info("Starting heartbeat cycle %d", cycles_run + 1)
		try:
			result = await run_heartbeat_cycle(queries)
			logger.info(
				"Heartbeat cycle %d complete: %d papers, %d triples, %d high-delta edges",
				cycles_run + 1,
				result["total_papers"],
				result["total_triples"],
				result["high_delta_edges"],
			)
		except Exception:
			logger.exception("Heartbeat cycle %d failed", cycles_run + 1)

		cycles_run += 1
		if max_cycles is not None and cycles_run >= max_cycles:
			break

		await asyncio.sleep(interval_hours * 3600)
