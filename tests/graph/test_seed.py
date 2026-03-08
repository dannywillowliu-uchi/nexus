from nexus.graph.seed import parse_metaedge


def test_parse_metaedge_compound_binds_gene():
	"""Parse 'Compound - binds - Gene > CbG' into its components."""
	result = parse_metaedge("Compound - binds - Gene > CbG")
	assert result == ("Compound", "binds", "Gene")


def test_parse_metaedge_disease_associates_gene():
	"""Parse 'Disease - associates - Gene > DaG' into its components."""
	result = parse_metaedge("Disease - associates - Gene > DaG")
	assert result == ("Disease", "associates", "Gene")
