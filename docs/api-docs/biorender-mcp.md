# BioRender MCP Connector Reference

## Overview
The BioRender MCP connector enables searching BioRender's library of scientifically accurate icons and templates via AI assistants (Claude, etc.).

## MCP Server URL
```
https://mcp.services.biorender.com/mcp
```

## Setup
1. Add MCP server connection in your AI assistant settings
2. Enter server URL: `https://mcp.services.biorender.com/mcp`
3. Connect using BioRender credentials
4. Approve requested permissions

## Capabilities
- Search BioRender's icon library using natural language
- Find templates for experimental workflows
- Get scientifically accurate figures for:
	- Presentations and slide decks
	- Posters and grant proposals
	- Journal graphical abstracts
	- Protocol diagrams
	- Pathway illustrations

## Usage Pattern
Describe your needs in natural language and receive curated icon/template suggestions.

Example prompts:
- "Find icons for a CRISPR gene editing workflow"
- "Show me templates for a cell signaling pathway"
- "I need figures for a drug mechanism of action diagram"

## Integration with Claude for Life Sciences
BioRender partnered with Anthropic (Oct 2025) to integrate directly into Claude for Life Sciences.
- Scientists describe needs -> receive recommended scientific figures
- Works alongside Benchling, PubMed, 10x Genomics integrations

## Authentication
OAuth-based via BioRender account credentials.

## Free Tier
BioRender free tier exists for basic usage. MCP connector access may require paid plan -- verify at biorender.com.

## Source
- https://help.biorender.com/hc/en-gb/articles/30870978672157
- https://claude.com/connectors/biorender
