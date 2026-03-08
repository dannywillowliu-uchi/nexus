# Research Output Module Design

**Date:** 2026-03-08
**Branch:** feature/research-output
**Worktree:** .worktrees/research-output

## Problem

After a pipeline run produces hypotheses with validation results, there's no
way to present the findings visually or as a structured research pitch. We need
output that's informative, parsable, and tells the story of the discovery.

## Components

### 1. Visual Rendering (SVG)

Three layers of visual output, all server-side SVG generation:

| Layer | Purpose | Method |
|-------|---------|--------|
| ABC Pathway Diagram | Node-link graph: A→B→C with edge labels, scores, intermediaries | Claude SVG generation |
| Molecular Structure | 2D compound structure when SMILES available | RDKit MolDraw2DSVG |
| Mechanism of Action | Drug-target interaction with pathway context | Claude SVG generation |

No external API dependencies beyond existing Anthropic key. BioRender has no
public API for diagram generation — the existing viz_agent.py endpoint is
speculative and won't work in production.

### 2. Research Pitch Report (Markdown)

Claude-generated structured document per hypothesis:

1. **Executive Summary** — What was discovered, why it matters
2. **Methodology Rationale** — Why Swanson ABC, why these validation tools,
   how the adaptive pipeline navigated to this result
3. **Discovery Process** — Chronological narrative of the pipeline's journey,
   key decisions, pivots, branches, and their reasoning
4. **Evidence Chain** — Literature → graph path → validation, confidence breakdown
5. **Clinical/Research Significance** — Field impact, comparison to existing knowledge
6. **Proposed Next Steps** — Experimental validation, suggested assays
7. **Embedded Visuals** — Inline SVGs from Component 1

### 3. Discovery Narrative

Synthesized from checkpoint_log, pivots, and branches into a readable story:
- Pipeline decisions at each checkpoint (CONTINUE/PIVOT/BRANCH + reason)
- Validation tool results and confidence deltas
- Branch comparisons and why the final path was selected
- Embedded as "Discovery Process" section in the pitch report

## Data Flow

```
PipelineResult
  → scored_hypotheses[0:3] (top 3 with research_briefs)
  → for each hypothesis:
      → render_pathway_svg(abc_path, intermediaries, scores)
      → render_molecule_svg(compound_smiles)  [if compound node]
      → render_moa_svg(hypothesis_data)
      → generate_discovery_narrative(checkpoint_log, pivots, branches)
      → generate_research_pitch(hypothesis, narrative, validations)
  → ResearchOutput(visuals, pitch_markdown, narrative)
```

## Module Structure

```
backend/src/nexus/output/
  __init__.py
  models.py      — ResearchOutput, VisualAsset dataclasses
  renderer.py    — SVG generation (Claude + RDKit)
  narrative.py   — Discovery process narrative from pipeline trace
  pitch.py       — Research pitch report assembly
```

## Key Design Decisions

- **Claude for SVG** over BioRender: no public BioRender API exists; Claude
  generates custom diagrams at zero extra cost
- **RDKit for molecules**: industry standard, pure Python, deterministic output
- **Markdown output**: universally parsable, embeds in web frontends, converts
  to PDF easily
- **Server-side generation**: reports are self-contained, no frontend dependency
- **Top 3 only**: full reports are expensive (multiple Claude calls); limit to
  the highest-scoring hypotheses
