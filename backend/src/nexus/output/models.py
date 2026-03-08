"""Data models for research output generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VisualAsset:
	"""A single SVG visual asset."""

	label: str
	svg: str
	asset_type: str  # "pathway", "molecule", "mechanism"


@dataclass
class ResearchOutput:
	"""Complete research output for a single hypothesis."""

	hypothesis_title: str
	visuals: list[VisualAsset] = field(default_factory=list)
	discovery_narrative: str = ""
	pitch_markdown: str = ""
