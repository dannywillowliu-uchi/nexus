from nexus.tools.registry import TOOL_REGISTRY


def test_registry_has_all_tools():
	expected_tools = [
		"literature_validate",
		"compound_lookup",
		"pathway_overlap",
		"protein_interaction",
		"expression_correlate",
		"molecular_dock",
		"generate_protocol",
	]
	for tool_name in expected_tools:
		assert tool_name in TOOL_REGISTRY, f"Missing tool: {tool_name}"


def test_registry_tools_are_callable():
	for name, func in TOOL_REGISTRY.items():
		assert callable(func), f"Tool '{name}' is not callable"


def test_registry_count():
	assert len(TOOL_REGISTRY) == 7
