from unittest.mock import AsyncMock, patch

from nexus.heartbeat.delta import detect_deltas


@patch("nexus.heartbeat.delta.graph_client")
async def test_detect_deltas_returns_high_delta_edges(mock_graph_client):
	# For each triple, two queries are run (one per node).
	# Return results indicating new paths exist.
	mock_graph_client.execute_read = AsyncMock(
		side_effect=[
			[{"new_paths": 3}],  # paths through subject "BRCA1"
			[{"new_paths": 1}],  # paths through object "Breast Cancer"
			[{"new_paths": 0}],  # paths through subject "TP53"
			[{"new_paths": 0}],  # paths through object "Lung Cancer"
		]
	)

	new_triples = [
		{"subject": "BRCA1", "object": "Breast Cancer", "predicate": "associated_with"},
		{"subject": "TP53", "object": "Lung Cancer", "predicate": "suppresses"},
	]

	result = await detect_deltas(new_triples)

	assert len(result) == 1
	assert result[0]["subject"] == "BRCA1"
	assert result[0]["object"] == "Breast Cancer"
	assert result[0]["predicate"] == "associated_with"
	assert result[0]["new_paths_count"] == 4  # 3 + 1


async def test_detect_deltas_empty_input():
	result = await detect_deltas([])
	assert result == []
