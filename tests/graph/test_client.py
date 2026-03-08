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
