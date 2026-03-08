import pytest
from unittest.mock import patch, AsyncMock

from nexus.graph.abc import (
	ABCHypothesis,
	compute_novelty,
	find_abc_hypotheses,
	rel_weight,
)


def test_abc_hypothesis_dataclass():
	"""Create an ABCHypothesis and verify all fields are set correctly."""
	h = ABCHypothesis(
		a_id="D001",
		a_name="Epilepsy",
		a_type="Disease",
		b_id="G042",
		b_name="GABA receptor",
		b_type="Gene",
		c_id="C007",
		c_name="Valproate",
		c_type="Compound",
		ab_relationship="ASSOCIATES_DaG",
		bc_relationship="BINDS_CbG",
		path_count=3,
		novelty_score=0.95,
		path_strength=0.87,
		intermediaries=[{"b_id": "G042", "b_name": "GABA receptor"}],
	)
	assert h.a_id == "D001"
	assert h.a_name == "Epilepsy"
	assert h.a_type == "Disease"
	assert h.b_id == "G042"
	assert h.b_name == "GABA receptor"
	assert h.b_type == "Gene"
	assert h.c_id == "C007"
	assert h.c_name == "Valproate"
	assert h.c_type == "Compound"
	assert h.ab_relationship == "ASSOCIATES_DaG"
	assert h.bc_relationship == "BINDS_CbG"
	assert h.path_count == 3
	assert h.novelty_score == 0.95
	assert h.path_strength == 0.87
	assert len(h.intermediaries) == 1


def test_abc_hypothesis_defaults():
	"""Verify default values for optional fields."""
	h = ABCHypothesis(
		a_id="D001",
		a_name="Epilepsy",
		a_type="Disease",
		b_id="G042",
		b_name="GABA receptor",
		b_type="Gene",
		c_id="C007",
		c_name="Valproate",
		c_type="Compound",
		ab_relationship="ASSOCIATES_DaG",
		bc_relationship="BINDS_CbG",
		path_count=3,
		novelty_score=0.95,
	)
	assert h.path_strength == 0.0
	assert h.intermediaries == []


def test_compute_novelty():
	"""Test novelty scores across all path_count ranges."""
	# <= 2
	assert compute_novelty(1) == 0.9
	assert compute_novelty(2) == 0.9
	# 3-5
	assert compute_novelty(3) == 0.95
	assert compute_novelty(5) == 0.95
	# 6-10
	assert compute_novelty(6) == 0.8
	assert compute_novelty(10) == 0.8
	# 11-20
	assert compute_novelty(11) == 0.6
	assert compute_novelty(20) == 0.6
	# > 20
	assert compute_novelty(21) == 0.4
	assert compute_novelty(100) == 0.4


def test_rel_weight_known():
	"""Known relationship types should return their assigned weights."""
	assert rel_weight("TREATS_CtD") == 1.0
	assert rel_weight("BINDS_CbG") == 0.9
	assert rel_weight("ASSOCIATES_DaG") == 0.85
	assert rel_weight("INTERACTS_GiG") == 0.8
	assert rel_weight("PARTICIPATES_GpBP") == 0.8


def test_rel_weight_unknown():
	"""Unknown relationship types should return the default weight of 0.5."""
	assert rel_weight("UNKNOWN_REL") == 0.5
	assert rel_weight("") == 0.5
	assert rel_weight("MADE_UP_TYPE") == 0.5


def _make_mock_records(source_type="Disease", target_type="Compound"):
	"""Build realistic mock records for ABC traversal results."""
	return [
		{
			"a_id": "DOID:1234",
			"a_name": "multiple sclerosis",
			"a_type": source_type,
			"c_id": "DB00123",
			"c_name": "Methotrexate",
			"c_type": target_type,
			"intermediaries": [
				{
					"b_id": "GENE:5678",
					"b_name": "TNF",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATES_DaG",
					"bc_rel": "BINDS_CbG",
				},
				{
					"b_id": "GENE:9999",
					"b_name": "IL6",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATES_DaG",
					"bc_rel": "DOWNREGULATES_CdG",
				},
			],
			"path_count": 2,
		},
		{
			"a_id": "DOID:1234",
			"a_name": "multiple sclerosis",
			"a_type": source_type,
			"c_id": "DB00456",
			"c_name": "Rituximab",
			"c_type": target_type,
			"intermediaries": [
				{
					"b_id": "GENE:1111",
					"b_name": "CD20",
					"b_type": "Gene",
					"ab_rel": "ASSOCIATES_DaG",
					"bc_rel": "TREATS_CtD",
				},
			],
			"path_count": 1,
		},
	]


@pytest.mark.asyncio
async def test_find_abc_hypotheses_disease_to_compound():
	"""Test ABC traversal from Disease to Compound with mocked graph data."""
	mock_records = _make_mock_records()

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(return_value=mock_records)

		results = await find_abc_hypotheses(
			source_name="multiple sclerosis",
			source_type="Disease",
			target_type="Compound",
			max_results=20,
		)

	assert len(results) == 2

	# First result: Methotrexate (path_count=2, two intermediaries)
	h0 = results[0]
	assert h0.a_name == "multiple sclerosis"
	assert h0.a_type == "Disease"
	assert h0.c_name == "Methotrexate"
	assert h0.c_type == "Compound"
	assert h0.path_count == 2
	assert h0.novelty_score == 0.9
	assert len(h0.intermediaries) == 2
	# Best intermediary should be the one with highest path_strength
	# ASSOCIATES_DaG(0.85) * BINDS_CbG(0.9) -> sqrt(0.765) ~ 0.875
	# ASSOCIATES_DaG(0.85) * DOWNREGULATES_CdG(0.7) -> sqrt(0.595) ~ 0.771
	assert h0.b_name == "TNF"
	assert h0.path_strength > 0.87

	# Second result: Rituximab
	h1 = results[1]
	assert h1.c_name == "Rituximab"
	assert h1.path_count == 1


@pytest.mark.asyncio
async def test_find_abc_hypotheses_gene_source():
	"""Test ABC traversal with Gene as source type."""
	mock_records = [
		{
			"a_id": "GENE:5678",
			"a_name": "TNF",
			"a_type": "Gene",
			"c_id": "DB00789",
			"c_name": "Infliximab",
			"c_type": "Compound",
			"intermediaries": [
				{
					"b_id": "DOID:4567",
					"b_name": "rheumatoid arthritis",
					"b_type": "Disease",
					"ab_rel": "ASSOCIATES_GaD",
					"bc_rel": "TREATS_CtD",
				},
			],
			"path_count": 1,
		},
	]

	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(return_value=mock_records)

		results = await find_abc_hypotheses(
			source_name="TNF",
			source_type="Gene",
			target_type="Compound",
			max_results=10,
		)

	assert len(results) == 1
	h = results[0]
	assert h.a_type == "Gene"
	assert h.a_name == "TNF"
	assert h.b_type == "Disease"
	assert h.c_type == "Compound"
	assert h.c_name == "Infliximab"


@pytest.mark.asyncio
async def test_find_abc_hypotheses_exclude_known():
	"""Verify the exclude_known flag affects the Cypher query."""
	with patch("nexus.graph.abc.graph_client") as mock_client:
		mock_client.execute_read = AsyncMock(return_value=[])

		# With exclude_known=True (default)
		await find_abc_hypotheses(source_name="test", exclude_known=True)
		query_with_exclude = mock_client.execute_read.call_args[0][0]
		assert "NOT (a)-[]-(c)" in query_with_exclude

		mock_client.execute_read.reset_mock()

		# With exclude_known=False
		await find_abc_hypotheses(source_name="test", exclude_known=False)
		query_without_exclude = mock_client.execute_read.call_args[0][0]
		assert "NOT (a)-[]-(c)" not in query_without_exclude
