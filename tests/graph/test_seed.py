import json
from pathlib import Path

import pytest

from nexus.graph.seed import _extract_edge_fields, _sanitize_label, parse_metaedge


DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "hetionet"
NODES_PATH = DATA_DIR / "hetionet-v1.0-nodes.json"
EDGES_PATH = DATA_DIR / "hetionet-v1.0-edges.json"


# --- parse_metaedge tests ---


def test_parse_metaedge_compound_binds_gene():
	"""Parse 'Compound - binds - Gene > CbG' into its components."""
	result = parse_metaedge("Compound - binds - Gene > CbG")
	assert result == ("Compound", "binds", "Gene")


def test_parse_metaedge_disease_associates_gene():
	"""Parse 'Disease - associates - Gene > DaG' into its components."""
	result = parse_metaedge("Disease - associates - Gene > DaG")
	assert result == ("Disease", "associates", "Gene")


def test_parse_metaedge_no_abbreviation():
	"""Parse metaedge without abbreviation suffix."""
	result = parse_metaedge("Gene - interacts - Gene")
	assert result == ("Gene", "interacts", "Gene")


def test_parse_metaedge_invalid():
	"""Invalid metaedge string raises ValueError."""
	with pytest.raises(ValueError):
		parse_metaedge("not a valid metaedge")


# --- _sanitize_label tests ---


def test_sanitize_label_with_spaces():
	assert _sanitize_label("Molecular Function") == "Molecular_Function"


def test_sanitize_label_simple():
	assert _sanitize_label("Gene") == "Gene"


# --- _extract_edge_fields tests ---


def test_extract_edge_fields_hetionet_format():
	"""Extract fields from Hetionet v1.0 array-style edge."""
	edge = {
		"source_id": ["Anatomy", "UBERON:0000178"],
		"target_id": ["Gene", 9489],
		"kind": "upregulates",
		"direction": "both",
		"data": {"source": "Bgee"},
	}
	src_label, src_id, tgt_label, tgt_id, rel = _extract_edge_fields(edge)
	assert src_label == "Anatomy"
	assert src_id == "UBERON:0000178"
	assert tgt_label == "Gene"
	assert tgt_id == "9489"
	assert rel == "upregulates"


def test_extract_edge_fields_metaedge_format():
	"""Extract fields from metaedge-string-style edge."""
	edge = {
		"source": "DB00945",
		"target": "1565",
		"kind": "Compound - binds - Gene > CbG",
	}
	src_label, src_id, tgt_label, tgt_id, rel = _extract_edge_fields(edge)
	assert src_label == "Compound"
	assert src_id == "DB00945"
	assert tgt_label == "Gene"
	assert tgt_id == "1565"
	assert rel == "binds"


# --- Data file validation tests ---


@pytest.mark.skipif(not NODES_PATH.exists(), reason="Hetionet nodes data not downloaded")
class TestHetionetNodesData:
	def test_nodes_file_is_valid_json(self):
		with open(NODES_PATH) as f:
			nodes = json.load(f)
		assert isinstance(nodes, list)
		assert len(nodes) > 0

	def test_nodes_have_expected_fields(self):
		with open(NODES_PATH) as f:
			nodes = json.load(f)
		sample = nodes[:10]
		for node in sample:
			assert "identifier" in node, f"Node missing 'identifier': {node}"
			assert "name" in node, f"Node missing 'name': {node}"
			assert "kind" in node, f"Node missing 'kind': {node}"

	def test_nodes_kind_values(self):
		with open(NODES_PATH) as f:
			nodes = json.load(f)
		kinds = {n["kind"] for n in nodes}
		# Hetionet v1.0 has 11 node types
		assert len(kinds) == 11
		assert "Gene" in kinds
		assert "Compound" in kinds
		assert "Disease" in kinds


@pytest.mark.skipif(not EDGES_PATH.exists(), reason="Hetionet edges data not downloaded")
class TestHetionetEdgesData:
	def test_edges_file_is_valid_json(self):
		# Only load first chunk to avoid memory issues with 423MB file
		with open(EDGES_PATH) as f:
			edges = json.load(f)
		assert isinstance(edges, list)
		assert len(edges) > 0

	def test_edges_have_expected_fields(self):
		with open(EDGES_PATH) as f:
			edges = json.load(f)
		sample = edges[:10]
		for edge in sample:
			assert "source_id" in edge, f"Edge missing 'source_id': {edge}"
			assert "target_id" in edge, f"Edge missing 'target_id': {edge}"
			assert "kind" in edge, f"Edge missing 'kind': {edge}"
			# source_id and target_id should be [kind, identifier] arrays
			assert isinstance(edge["source_id"], list) and len(edge["source_id"]) == 2
			assert isinstance(edge["target_id"], list) and len(edge["target_id"]) == 2

	def test_edges_extract_with_real_data(self):
		"""Verify _extract_edge_fields works with actual downloaded edge data."""
		with open(EDGES_PATH) as f:
			edges = json.load(f)
		sample = edges[:20]
		for edge in sample:
			src_label, src_id, tgt_label, tgt_id, rel = _extract_edge_fields(edge)
			assert isinstance(src_label, str) and len(src_label) > 0
			assert isinstance(src_id, str) and len(src_id) > 0
			assert isinstance(tgt_label, str) and len(tgt_label) > 0
			assert isinstance(tgt_id, str) and len(tgt_id) > 0
			assert isinstance(rel, str) and len(rel) > 0
