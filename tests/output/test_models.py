"""Tests for output models."""

from nexus.output.models import ResearchOutput, VisualAsset


def test_visual_asset_creation():
	asset = VisualAsset(label="Test", svg="<svg></svg>", asset_type="pathway")
	assert asset.label == "Test"
	assert asset.svg == "<svg></svg>"
	assert asset.asset_type == "pathway"


def test_research_output_defaults():
	output = ResearchOutput(hypothesis_title="A -> C via B")
	assert output.hypothesis_title == "A -> C via B"
	assert output.visuals == []
	assert output.discovery_narrative == ""
	assert output.pitch_markdown == ""


def test_research_output_with_visuals():
	asset = VisualAsset(label="Pathway", svg="<svg>test</svg>", asset_type="pathway")
	output = ResearchOutput(
		hypothesis_title="Drug -> Gene via Pathway",
		visuals=[asset],
		discovery_narrative="The pipeline discovered...",
		pitch_markdown="# Pitch\n\nContent",
	)
	assert len(output.visuals) == 1
	assert output.visuals[0].label == "Pathway"
	assert "discovered" in output.discovery_narrative
