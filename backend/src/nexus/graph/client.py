from dataclasses import dataclass

from neo4j import AsyncDriver, AsyncGraphDatabase

from nexus.config import settings


@dataclass
class ResolvedEntity:
	"""Result of resolving a user-provided entity name against the graph."""
	name: str
	type: str
	identifier: str
	match_method: str  # "exact", "contains", "unresolved"
	original_query: str


class GraphClient:
	"""Async Neo4j graph database client."""

	def __init__(self) -> None:
		self._driver: AsyncDriver | None = None

	async def connect(self) -> None:
		"""Create an async Neo4j driver connection. Skips if URI not configured."""
		if not settings.neo4j_uri:
			return
		self._driver = AsyncGraphDatabase.driver(
			settings.neo4j_uri,
			auth=(settings.neo4j_username, settings.neo4j_password),
		)

	async def close(self) -> None:
		"""Close the driver connection."""
		if self._driver is not None:
			await self._driver.close()
			self._driver = None

	@property
	def driver(self) -> AsyncDriver:
		"""Return the async driver, raising if not connected."""
		if self._driver is None:
			raise RuntimeError("GraphClient is not connected. Call connect() first.")
		return self._driver

	async def execute_read(self, query: str, **params: object) -> list[dict]:
		"""Run a read transaction and return results as list of dicts."""
		async with self.driver.session() as session:
			async def _work(tx):
				result = await tx.run(query, params)
				records = await result.fetch(10000)
				return [record.data() for record in records]
			return await session.execute_read(_work)

	async def execute_write(self, query: str, **params: object) -> list[dict]:
		"""Run a write transaction and return results as list of dicts."""
		async with self.driver.session() as session:
			async def _work(tx):
				result = await tx.run(query, params)
				records = await result.fetch(10000)
				return [record.data() for record in records]
			return await session.execute_write(_work)

	async def node_count(self) -> int:
		"""Return count of all nodes in the graph."""
		records = await self.execute_read("MATCH (n) RETURN count(n) AS count")
		return records[0]["count"]

	async def edge_count(self) -> int:
		"""Return count of all relationships in the graph."""
		records = await self.execute_read("MATCH ()-[r]->() RETURN count(r) AS count")
		return records[0]["count"]

	async def resolve_entity_multi(
		self, query: str, entity_type: str | None = None, limit: int = 5,
	) -> list[ResolvedEntity]:
		"""Resolve a user-provided entity name to multiple candidate nodes."""
		type_filter = f":{entity_type}" if entity_type else ""

		exact_query = f"""
			MATCH (n{type_filter})
			WHERE toLower(n.name) = toLower($search_term)
			RETURN n.name AS name, labels(n)[0] AS type, coalesce(n.identifier, '') AS identifier
			LIMIT 1
		"""
		records = await self.execute_read(exact_query, search_term=query)
		if records:
			r = records[0]
			return [ResolvedEntity(
				name=r["name"],
				type=r["type"],
				identifier=r["identifier"],
				match_method="exact",
				original_query=query,
			)]

		contains_query = f"""
			MATCH (n{type_filter})
			WHERE toLower(n.name) CONTAINS toLower($search_term)
			RETURN n.name AS name, labels(n)[0] AS type, coalesce(n.identifier, '') AS identifier
			ORDER BY size(n.name) ASC
			LIMIT $limit
		"""
		records = await self.execute_read(contains_query, search_term=query, limit=limit)
		if records:
			return [
				ResolvedEntity(
					name=r["name"],
					type=r["type"],
					identifier=r["identifier"],
					match_method="contains",
					original_query=query,
				)
				for r in records
			]

		return []

	async def resolve_entity(self, query: str, entity_type: str | None = None) -> ResolvedEntity:
		"""Resolve a user-provided entity name to the best canonical node name."""
		candidates = await self.resolve_entity_multi(query, entity_type=entity_type, limit=5)
		if candidates:
			return candidates[0]
		return ResolvedEntity(
			name=query,
			type=entity_type or "Unknown",
			identifier="",
			match_method="unresolved",
			original_query=query,
		)


graph_client = GraphClient()
