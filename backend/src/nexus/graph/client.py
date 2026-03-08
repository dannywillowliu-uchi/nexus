from neo4j import AsyncDriver, AsyncGraphDatabase

from nexus.config import settings


class GraphClient:
	"""Async Neo4j graph database client."""

	def __init__(self) -> None:
		self._driver: AsyncDriver | None = None

	async def connect(self) -> None:
		"""Create an async Neo4j driver connection."""
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


graph_client = GraphClient()
