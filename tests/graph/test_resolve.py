"""Tests for entity name resolution against the Neo4j graph."""
from unittest.mock import AsyncMock, patch

import pytest

from nexus.graph.client import GraphClient, ResolvedEntity


@pytest.fixture
def client():
	c = GraphClient()
	c._driver = AsyncMock()
	return c


class TestResolveEntity:
	@pytest.mark.asyncio
	async def test_exact_match_case_insensitive(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.return_value = [
				{"name": "Alzheimer's disease", "type": "Disease", "identifier": "DOID:10652"}
			]
			result = await client.resolve_entity("alzheimer's disease", entity_type="Disease")

		assert result.match_method == "exact"
		assert result.name == "Alzheimer's disease"
		assert result.type == "Disease"
		assert result.identifier == "DOID:10652"
		assert result.original_query == "alzheimer's disease"

	@pytest.mark.asyncio
	async def test_contains_match_partial_name(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			# First call (exact) returns nothing, second call (contains) returns matches
			mock_read.side_effect = [
				[],
				[
					{"name": "Alzheimer's disease", "type": "Disease", "identifier": "DOID:10652"},
					{"name": "Alzheimer's disease pathway", "type": "Pathway", "identifier": "PW:001"},
				],
			]
			result = await client.resolve_entity("Alzheimer", entity_type="Disease")

		assert result.match_method == "contains"
		assert result.name == "Alzheimer's disease"
		assert result.type == "Disease"
		assert result.original_query == "Alzheimer"

	@pytest.mark.asyncio
	async def test_contains_prefers_shortest_name(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.side_effect = [
				[],
				[
					{"name": "diabetes mellitus", "type": "Disease", "identifier": "DOID:9351"},
					{"name": "diabetes mellitus type 2", "type": "Disease", "identifier": "DOID:9352"},
				],
			]
			result = await client.resolve_entity("diabetes")

		assert result.name == "diabetes mellitus"

	@pytest.mark.asyncio
	async def test_unresolved_when_no_match(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.side_effect = [[], []]
			result = await client.resolve_entity("xyzzy_nonexistent_thing", entity_type="Disease")

		assert result.match_method == "unresolved"
		assert result.name == "xyzzy_nonexistent_thing"
		assert result.type == "Disease"

	@pytest.mark.asyncio
	async def test_unresolved_without_entity_type(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.side_effect = [[], []]
			result = await client.resolve_entity("nothing_here")

		assert result.match_method == "unresolved"
		assert result.type == "Unknown"

	@pytest.mark.asyncio
	async def test_no_entity_type_filter(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.return_value = [
				{"name": "BRCA1", "type": "Gene", "identifier": "672"}
			]
			result = await client.resolve_entity("brca1")

		assert result.match_method == "exact"
		assert result.name == "BRCA1"
		assert result.type == "Gene"
		# Should not have included a type filter in the Cypher
		cypher = mock_read.call_args[0][0]
		assert ":" not in cypher.split("(n")[1].split(")")[0]

	@pytest.mark.asyncio
	async def test_with_entity_type_filter(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.return_value = [
				{"name": "Aspirin", "type": "Compound", "identifier": "DB00945"}
			]
			result = await client.resolve_entity("aspirin", entity_type="Compound")

		assert result.name == "Aspirin"
		# The Cypher should include :Compound type filter
		cypher = mock_read.call_args[0][0]
		assert ":Compound" in cypher

	@pytest.mark.asyncio
	async def test_exact_match_takes_priority_over_contains(self, client):
		with patch.object(client, "execute_read", new_callable=AsyncMock) as mock_read:
			mock_read.return_value = [
				{"name": "Parkinson disease", "type": "Disease", "identifier": "DOID:14330"}
			]
			result = await client.resolve_entity("Parkinson disease")

		assert result.match_method == "exact"
		# execute_read should only be called once (exact match hit)
		mock_read.assert_called_once()


class TestResolvedEntityDataclass:
	def test_fields(self):
		entity = ResolvedEntity(
			name="Alzheimer's disease",
			type="Disease",
			identifier="DOID:10652",
			match_method="exact",
			original_query="alzheimer",
		)
		assert entity.name == "Alzheimer's disease"
		assert entity.type == "Disease"
		assert entity.identifier == "DOID:10652"
		assert entity.match_method == "exact"
		assert entity.original_query == "alzheimer"
