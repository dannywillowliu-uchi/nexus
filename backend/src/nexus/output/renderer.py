"""SVG rendering for research output visuals."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from nexus.config import settings
from nexus.output.models import VisualAsset

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000

PATHWAY_SVG_PROMPT = """Generate a clean SVG diagram (800x400px) showing a biomedical discovery path.

Path: {a_name} ({a_type}) --[{ab_rel}]--> {b_name} ({b_type}) --[{bc_rel}]--> {c_name} ({c_type})

Scores:
- Novelty: {novelty:.2f}
- Evidence: {evidence:.2f}
- Path strength: {path_strength:.2f}
- Overall: {overall:.2f}

{intermediaries_text}

Design requirements:
- Three main nodes (A, B, C) connected by labeled arrows
- Node shapes: rounded rectangles with entity type as subtitle
- Color coding: Disease=#E74C3C, Drug=#3498DB, Gene=#2ECC71, Pathway=#9B59B6, other=#95A5A6
- Edge labels showing relationship type
- Score badges below each edge
- Clean white background, legible text, scientific illustration style
- Include a title at top: "{title}"

Output ONLY valid SVG XML. No markdown fences, no explanation."""

MOA_SVG_PROMPT = """Generate an SVG diagram (800x500px) illustrating the mechanism of action for this biomedical hypothesis.

Hypothesis: {title}
Description: {description}

Drug/Compound: {a_name}
Intermediary: {b_name} ({b_type})
Target: {c_name} ({c_type})
Relationships: {a_name} --[{ab_rel}]--> {b_name} --[{bc_rel}]--> {c_name}

Connection explanation: {connection_explanation}

Design requirements:
- Show the biological mechanism visually (not just boxes and arrows)
- Include cellular/molecular context where relevant
- Use scientific illustration style with clear labels
- Color coding consistent with biomedical conventions
- Clean white background, publication-quality aesthetics

Output ONLY valid SVG XML. No markdown fences, no explanation."""


def _extract_svg(text: str) -> str:
	"""Extract SVG content from Claude response, stripping any wrapper."""
	cleaned = text.strip()
	if cleaned.startswith("```"):
		lines = cleaned.split("\n")
		lines = [line for line in lines[1:] if line.strip() != "```"]
		cleaned = "\n".join(lines)
	# Ensure we start at the SVG tag
	svg_start = cleaned.find("<svg")
	if svg_start > 0:
		cleaned = cleaned[svg_start:]
	return cleaned


def _fallback_pathway_svg(hypothesis: dict[str, Any]) -> str:
	"""Generate a simple fallback SVG when Claude is unavailable."""
	abc = hypothesis.get("abc_path", {})
	a = abc.get("a", {})
	b = abc.get("b", {})
	c = abc.get("c", {})

	colors = {
		"Disease": "#E74C3C", "Drug": "#3498DB", "Gene": "#2ECC71",
		"Pathway": "#9B59B6", "Compound": "#3498DB",
	}

	a_color = colors.get(a.get("type", ""), "#95A5A6")
	b_color = colors.get(b.get("type", ""), "#95A5A6")
	c_color = colors.get(c.get("type", ""), "#95A5A6")

	return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300">
	<style>
		text {{ font-family: Arial, sans-serif; }}
		.node-label {{ font-size: 16px; font-weight: bold; fill: white; text-anchor: middle; }}
		.node-type {{ font-size: 11px; fill: white; opacity: 0.8; text-anchor: middle; }}
		.edge-label {{ font-size: 12px; fill: #555; text-anchor: middle; }}
		.title {{ font-size: 18px; font-weight: bold; fill: #333; text-anchor: middle; }}
		.score {{ font-size: 11px; fill: #777; text-anchor: middle; }}
	</style>
	<text x="400" y="35" class="title">{hypothesis.get("title", "")}</text>
	<rect x="40" y="100" width="180" height="70" rx="12" fill="{a_color}"/>
	<text x="130" y="135" class="node-label">{a.get("name", "A")}</text>
	<text x="130" y="155" class="node-type">{a.get("type", "")}</text>
	<rect x="310" y="100" width="180" height="70" rx="12" fill="{b_color}"/>
	<text x="400" y="135" class="node-label">{b.get("name", "B")}</text>
	<text x="400" y="155" class="node-type">{b.get("type", "")}</text>
	<rect x="580" y="100" width="180" height="70" rx="12" fill="{c_color}"/>
	<text x="670" y="135" class="node-label">{c.get("name", "C")}</text>
	<text x="670" y="155" class="node-type">{c.get("type", "")}</text>
	<line x1="220" y1="135" x2="310" y2="135" stroke="#999" stroke-width="2" marker-end="url(#arrow)"/>
	<line x1="490" y1="135" x2="580" y2="135" stroke="#999" stroke-width="2" marker-end="url(#arrow)"/>
	<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#999"/></marker></defs>
	<text x="265" y="120" class="edge-label">{hypothesis.get("description", "").split("(")[-1].split("/")[0].strip() if "(" in hypothesis.get("description", "") else ""}</text>
	<text x="535" y="120" class="edge-label">{hypothesis.get("description", "").split("/")[-1].split(")")[0].strip() if "/" in hypothesis.get("description", "") else ""}</text>
	<text x="400" y="220" class="score">Overall score: {hypothesis.get("overall_score", 0):.2f} | Novelty: {hypothesis.get("novelty_score", 0):.2f} | Evidence: {hypothesis.get("evidence_score", 0):.2f}</text>
</svg>"""


async def render_pathway_svg(hypothesis: dict[str, Any]) -> VisualAsset:
	"""Render an ABC pathway diagram as SVG.

	Uses Claude to generate a publication-quality SVG showing the A->B->C
	path with scores and relationship labels. Falls back to a simple
	template SVG if no API key is configured.
	"""
	if not settings.anthropic_api_key:
		return VisualAsset(
			label="Pathway Diagram",
			svg=_fallback_pathway_svg(hypothesis),
			asset_type="pathway",
		)

	abc = hypothesis.get("abc_path", {})
	a = abc.get("a", {})
	b = abc.get("b", {})
	c = abc.get("c", {})

	intermediaries = hypothesis.get("intermediaries", [])
	if intermediaries:
		intermediaries_text = "Additional intermediaries:\n" + "\n".join(
			f"- {i.get('name', '')} ({i.get('type', '')})" for i in intermediaries[:5]
		)
	else:
		intermediaries_text = ""

	prompt = PATHWAY_SVG_PROMPT.format(
		a_name=a.get("name", ""),
		a_type=a.get("type", ""),
		ab_rel=hypothesis.get("description", "").split("(")[-1].split("/")[0].strip() if "(" in hypothesis.get("description", "") else "relates_to",
		b_name=b.get("name", ""),
		b_type=b.get("type", ""),
		bc_rel=hypothesis.get("description", "").split("/")[-1].split(")")[0].strip() if "/" in hypothesis.get("description", "") else "relates_to",
		c_name=c.get("name", ""),
		c_type=c.get("type", ""),
		novelty=hypothesis.get("novelty_score", 0),
		evidence=hypothesis.get("evidence_score", 0),
		path_strength=hypothesis.get("path_strength", 0),
		overall=hypothesis.get("overall_score", 0),
		intermediaries_text=intermediaries_text,
		title=hypothesis.get("title", ""),
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)
		svg = _extract_svg(getattr(message.content[0], "text", ""))
		return VisualAsset(label="Pathway Diagram", svg=svg, asset_type="pathway")
	except Exception:
		logger.exception("Failed to generate pathway SVG, using fallback")
		return VisualAsset(
			label="Pathway Diagram",
			svg=_fallback_pathway_svg(hypothesis),
			asset_type="pathway",
		)


async def render_moa_svg(hypothesis: dict[str, Any]) -> VisualAsset | None:
	"""Render a mechanism-of-action diagram as SVG.

	Only generates for hypotheses that have a research brief with a
	connection explanation. Returns None if insufficient data or no API key.
	"""
	brief = hypothesis.get("research_brief")
	if not brief or not settings.anthropic_api_key:
		return None

	abc = hypothesis.get("abc_path", {})
	a = abc.get("a", {})
	b = abc.get("b", {})
	c = abc.get("c", {})

	prompt = MOA_SVG_PROMPT.format(
		title=hypothesis.get("title", ""),
		description=hypothesis.get("description", ""),
		a_name=a.get("name", ""),
		b_name=b.get("name", ""),
		b_type=b.get("type", ""),
		c_name=c.get("name", ""),
		c_type=c.get("type", ""),
		ab_rel=hypothesis.get("description", "").split("(")[-1].split("/")[0].strip() if "(" in hypothesis.get("description", "") else "relates_to",
		bc_rel=hypothesis.get("description", "").split("/")[-1].split(")")[0].strip() if "/" in hypothesis.get("description", "") else "relates_to",
		connection_explanation=brief.get("connection_explanation", ""),
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model=MODEL,
			max_tokens=MAX_TOKENS,
			messages=[{"role": "user", "content": prompt}],
		)
		svg = _extract_svg(getattr(message.content[0], "text", ""))
		return VisualAsset(label="Mechanism of Action", svg=svg, asset_type="mechanism")
	except Exception:
		logger.exception("Failed to generate MOA SVG")
		return None
