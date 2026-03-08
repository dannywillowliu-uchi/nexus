from unittest.mock import AsyncMock, patch

from nexus.heartbeat.engine import run_heartbeat_cycle, start_heartbeat_loop


@patch("nexus.heartbeat.engine.detect_deltas")
@patch("nexus.heartbeat.engine.ingest_recent_papers")
async def test_run_heartbeat_cycle(mock_ingest, mock_deltas):
	mock_ingest.side_effect = [
		{
			"papers_found": 5,
			"triples_extracted": 10,
			"edges_merged": 8,
			"triples": [
				{"subject": "A", "object": "B", "predicate": "inhibits"},
				{"subject": "C", "object": "D", "predicate": "activates"},
			],
		},
		{
			"papers_found": 3,
			"triples_extracted": 4,
			"edges_merged": 4,
			"triples": [
				{"subject": "E", "object": "F", "predicate": "causes"},
			],
		},
	]
	mock_deltas.return_value = [
		{"subject": "A", "object": "B", "predicate": "inhibits", "new_paths_count": 5},
	]

	result = await run_heartbeat_cycle(["ALS", "Parkinson"], days=7)

	assert result["total_papers"] == 8
	assert result["total_triples"] == 14
	assert result["high_delta_edges"] == 1

	# Verify detect_deltas was called with all triples combined
	call_args = mock_deltas.call_args[0][0]
	assert len(call_args) == 3


@patch("nexus.heartbeat.engine.asyncio.sleep", new_callable=AsyncMock)
@patch("nexus.heartbeat.engine.run_heartbeat_cycle")
async def test_start_heartbeat_loop_max_cycles(mock_cycle, mock_sleep):
	mock_cycle.return_value = {
		"total_papers": 2,
		"total_triples": 3,
		"high_delta_edges": 0,
	}

	await start_heartbeat_loop(
		queries=["ALS"],
		interval_hours=24,
		max_cycles=3,
	)

	assert mock_cycle.call_count == 3
	# Sleep is called between cycles (not after the last one)
	assert mock_sleep.call_count == 2
	mock_sleep.assert_called_with(24 * 3600)
