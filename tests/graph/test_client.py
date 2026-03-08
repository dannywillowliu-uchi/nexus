from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.graph.client import GraphClient


def test_graph_client_init():
	"""After init, _driver should be None."""
	client = GraphClient()
	assert client._driver is None


def test_graph_client_not_connected():
	"""Accessing driver before connect() should raise RuntimeError."""
	client = GraphClient()
	with pytest.raises(RuntimeError, match="not connected"):
		_ = client.driver


@pytest.mark.asyncio
async def test_execute_read_uses_managed_transaction():
	"""execute_read should use session.execute_read with a transaction function."""
	mock_record = MagicMock()
	mock_record.data.return_value = {"name": "test"}

	mock_session = AsyncMock()
	mock_session.execute_read = AsyncMock(return_value=[{"name": "test"}])
	mock_session.__aenter__ = AsyncMock(return_value=mock_session)
	mock_session.__aexit__ = AsyncMock(return_value=False)

	mock_driver = MagicMock()
	mock_driver.session.return_value = mock_session

	client = GraphClient()
	client._driver = mock_driver

	result = await client.execute_read("MATCH (n) RETURN n.name AS name")

	mock_session.execute_read.assert_called_once()
	assert result == [{"name": "test"}]


@pytest.mark.asyncio
async def test_execute_write_uses_managed_transaction():
	"""execute_write should use session.execute_write with a transaction function."""
	mock_session = AsyncMock()
	mock_session.execute_write = AsyncMock(return_value=[{"id": 1}])
	mock_session.__aenter__ = AsyncMock(return_value=mock_session)
	mock_session.__aexit__ = AsyncMock(return_value=False)

	mock_driver = MagicMock()
	mock_driver.session.return_value = mock_session

	client = GraphClient()
	client._driver = mock_driver

	result = await client.execute_write("CREATE (n:Test) RETURN id(n) AS id")

	mock_session.execute_write.assert_called_once()
	assert result == [{"id": 1}]


@pytest.mark.asyncio
async def test_execute_read_transaction_function_runs_query():
	"""The transaction function passed to execute_read should run the query on tx."""
	mock_record = MagicMock()
	mock_record.data.return_value = {"count": 42}

	mock_result = AsyncMock()
	mock_result.fetch = AsyncMock(return_value=[mock_record])

	mock_tx = AsyncMock()
	mock_tx.run = AsyncMock(return_value=mock_result)

	async def fake_execute_read(work):
		return await work(mock_tx)

	mock_session = AsyncMock()
	mock_session.execute_read = fake_execute_read
	mock_session.__aenter__ = AsyncMock(return_value=mock_session)
	mock_session.__aexit__ = AsyncMock(return_value=False)

	mock_driver = MagicMock()
	mock_driver.session.return_value = mock_session

	client = GraphClient()
	client._driver = mock_driver

	result = await client.execute_read("MATCH (n) RETURN count(n) AS count")

	mock_tx.run.assert_called_once_with("MATCH (n) RETURN count(n) AS count", {})
	mock_result.fetch.assert_called_once_with(10000)
	assert result == [{"count": 42}]
