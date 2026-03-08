import pytest
from unittest.mock import AsyncMock, patch

from nexus.graph.abc import (
	INTERMEDIARY_TIERS,
	QUERY_TIMEOUT,
	_merge_records,
	find_abc_hypotheses,
)


def _make_records(prefix: str, count: int, b_type: str = "Gene") -> list[dict]:
	"""Generate mock ABC records with unique (a_id, c_id) pairs."""
	return [
		{
			"a_id": "DOID:1234",
			"a_name": "multiple sclerosis",
			"a_type": "Disease",
			"c_id": f"{prefix}:{i}",
			"c_name": f"Drug_{prefix}_{i}",
			"c_type": "Drug",
			"intermediaries": [
				{
					"b_id": f"B:{prefix}:{i}",
					"b_name": f"inter_{prefix}_{i}",
					"b_type": b_type,
					"ab_rel": "ASSOCIATED_WITH",
					"bc_rel": "TARGET",
				},
			],
			"path_count": 1,
		}
		for i in range(count)
	]


def test_intermediary_tiers_defined():
	"""Verify INTERMEDIARY_TIERS has 3 tiers with expected types."""
	assert len(INTERMEDIARY_TIERS) == 3
	assert INTERMEDIARY_TIERS[0] == ["Gene"]
	assert "Pathway" in INTERMEDIARY_TIERS[1]
	assert "BiologicalProcess" in INTERMEDIARY_TIERS[1]
	assert "Anatomy" in INTERMEDIARY_TIERS[2]
	assert "Phenotype" in INTERMEDIARY_TIERS[2]
	assert "MolecularFunction" in INTERMEDIARY_TIERS[2]
	assert "CellularComponent" in INTERMEDIARY_TIERS[2]
	assert QUERY_TIMEOUT == 10.0


@pytest.mark.asyncio
async def test_fanout_skips_lower_tiers_when_enough_results():
	"""When tier 1 returns >= 10 results, only 1 execute_read call (Gene only)."""
	gene_records = _make_records("GENE", 12, b_type="Gene")

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(return_value=gene_records)

		results = await find_abc_hypotheses(
			source_name="multiple sclerosis",
			source_type="Disease",
			target_type="Drug",
			min_results=10,
		)

	# Tier 1 has only ["Gene"], so exactly 1 execute_read call
	assert mock_client.execute_read.await_count == 1
	assert len(results) == 12


@pytest.mark.asyncio
async def test_fanout_expands_to_tier2_when_insufficient():
	"""When tier 1 returns < 10, tier 2 queries also run."""
	gene_records = _make_records("GENE", 3, b_type="Gene")
	pathway_records = _make_records("PW", 5, b_type="Pathway")
	bp_records = _make_records("BP", 4, b_type="BiologicalProcess")

	call_count = 0

	async def mock_execute_read(query, **params):
		nonlocal call_count
		call_count += 1
		if "b:Gene" in query:
			return gene_records
		if "b:Pathway" in query:
			return pathway_records
		if "b:BiologicalProcess" in query:
			return bp_records
		return []

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(side_effect=mock_execute_read)

		results = await find_abc_hypotheses(
			source_name="multiple sclerosis",
			source_type="Disease",
			target_type="Drug",
			min_results=10,
		)

	# Tier 1 (Gene) = 3 results < 10, so tier 2 (Pathway + BiologicalProcess) also runs
	# Total: 1 (Gene) + 2 (Pathway, BiologicalProcess) = 3 calls
	assert mock_client.execute_read.await_count == 3
	# 3 + 5 + 4 = 12 unique results (all different c_id prefixes)
	assert len(results) == 12


@pytest.mark.asyncio
async def test_fanout_all_tiers_when_insufficient():
	"""When tiers 1+2 combined < min_results, tier 3 also runs."""
	gene_records = _make_records("GENE", 2, b_type="Gene")
	# Tier 2 returns nothing
	# Tier 3 returns some

	async def mock_execute_read(query, **params):
		if "b:Gene" in query:
			return gene_records
		if "b:Anatomy" in query:
			return _make_records("ANAT", 3, b_type="Anatomy")
		return []

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(side_effect=mock_execute_read)

		results = await find_abc_hypotheses(
			source_name="test",
			source_type="Disease",
			target_type="Drug",
			min_results=10,
		)

	# All 3 tiers queried: 1 + 2 + 4 = 7 calls
	assert mock_client.execute_read.await_count == 7
	assert len(results) == 5  # 2 Gene + 3 Anatomy


@pytest.mark.asyncio
async def test_fanout_deduplicates_by_ac_pair():
	"""Duplicate (a_id, c_id) pairs are deduplicated, keeping the one with more intermediaries."""
	records_small = [
		{
			"a_id": "A:1",
			"a_name": "Disease X",
			"a_type": "Disease",
			"c_id": "C:1",
			"c_name": "Drug Y",
			"c_type": "Drug",
			"intermediaries": [{"b_id": "B:1", "b_name": "gene1", "b_type": "Gene", "ab_rel": "ASSOCIATED_WITH", "bc_rel": "TARGET"}],
			"path_count": 1,
		},
	]
	records_bigger = [
		{
			"a_id": "A:1",
			"a_name": "Disease X",
			"a_type": "Disease",
			"c_id": "C:1",
			"c_name": "Drug Y",
			"c_type": "Drug",
			"intermediaries": [
				{"b_id": "B:2", "b_name": "pathway1", "b_type": "Pathway", "ab_rel": "ASSOCIATED_WITH", "bc_rel": "TARGET"},
				{"b_id": "B:3", "b_name": "pathway2", "b_type": "Pathway", "ab_rel": "ASSOCIATED_WITH", "bc_rel": "TARGET"},
			],
			"path_count": 2,
		},
	]

	async def mock_execute_read(query, **params):
		if "b:Gene" in query:
			return records_small
		if "b:Pathway" in query:
			return records_bigger
		return []

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(side_effect=mock_execute_read)

		results = await find_abc_hypotheses(
			source_name="test",
			source_type="Disease",
			target_type="Drug",
			min_results=10,
		)

	# Only 1 unique (a_id, c_id) pair, kept the one with more intermediaries
	assert len(results) == 1
	assert len(results[0].intermediaries) == 2


@pytest.mark.asyncio
async def test_fanout_handles_timeout_gracefully():
	"""Timed-out queries are skipped without crashing."""
	import asyncio

	async def slow_query(query, **params):
		if "b:Gene" in query:
			await asyncio.sleep(20)  # Will exceed QUERY_TIMEOUT
			return []
		return _make_records("PW", 3, b_type="Pathway")

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(side_effect=slow_query)
		with patch("nexus.graph.abc.QUERY_TIMEOUT", 0.01):  # Very short timeout
			results = await find_abc_hypotheses(
				source_name="test",
				source_type="Disease",
				target_type="Drug",
				min_results=10,
			)

	# Gene timed out, but other tiers still returned results
	assert len(results) >= 3


def test_merge_records_keeps_more_intermediaries():
	"""_merge_records keeps the record with more intermediaries on duplicate keys."""
	existing: dict[tuple[str, str], dict] = {}
	record_1 = [{"a_id": "A", "c_id": "C", "intermediaries": [{"b": 1}], "path_count": 1}]
	record_2 = [{"a_id": "A", "c_id": "C", "intermediaries": [{"b": 1}, {"b": 2}], "path_count": 2}]

	_merge_records(existing, record_1)
	assert len(existing[("A", "C")]["intermediaries"]) == 1

	_merge_records(existing, record_2)
	assert len(existing[("A", "C")]["intermediaries"]) == 2

	# Merging a smaller one shouldn't overwrite
	_merge_records(existing, record_1)
	assert len(existing[("A", "C")]["intermediaries"]) == 2


@pytest.mark.asyncio
async def test_backward_compatible_signature():
	"""find_abc_hypotheses can be called without min_results (backward compatible)."""
	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(return_value=[])

		# Should work without min_results
		results = await find_abc_hypotheses(
			source_name="test",
			source_type="Disease",
			target_type="Drug",
			max_results=20,
			exclude_known=True,
			fuzzy=False,
		)

	assert results == []
