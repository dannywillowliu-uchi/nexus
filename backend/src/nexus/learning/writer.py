from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"


def _safe_filename(name: str) -> str:
	"""Convert a string to a filesystem-safe filename."""
	return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def write_session_log(
	session_id: str,
	query: str,
	entities_explored: list[str],
	pivots: list[dict],
	hypotheses: list[dict],
	learnings: list[str],
) -> Path:
	"""Write a structured session log to learning/sessions/<session_id>.md."""
	sessions_dir = LEARNING_DIR / "sessions"
	sessions_dir.mkdir(parents=True, exist_ok=True)

	timestamp = datetime.now(timezone.utc).isoformat()
	lines = [
		f"# Session {session_id}",
		"",
		f"**Date:** {timestamp}",
		f"**Query:** {query}",
		"",
		"## Entities Explored",
	]
	for entity in entities_explored:
		lines.append(f"- {entity}")

	lines.append("")
	lines.append("## Pivots")
	if pivots:
		for p in pivots:
			lines.append(f"- {p.get('from', '?')} -> {p.get('to', '?')}: {p.get('reason', '')}")
	else:
		lines.append("- None")

	lines.append("")
	lines.append("## Top Hypotheses")
	if hypotheses:
		for h in hypotheses:
			lines.append(f"- {h.get('a_name', '?')} -> {h.get('b_name', '?')} -> {h.get('c_name', '?')} "
				f"(novelty: {h.get('novelty_score', '?')})")
	else:
		lines.append("- None")

	lines.append("")
	lines.append("## Learnings")
	if learnings:
		for learning in learnings:
			lines.append(f"- {learning}")
	else:
		lines.append("- None")
	lines.append("")

	path = sessions_dir / f"{session_id}.md"
	path.write_text("\n".join(lines))
	logger.info("Wrote session log to %s", path)
	return path


def update_domain_playbook(disease_area: str, new_patterns: list[str]) -> Path:
	"""Append new patterns to a domain playbook, deduplicating entries."""
	playbooks_dir = LEARNING_DIR / "playbooks"
	playbooks_dir.mkdir(parents=True, exist_ok=True)

	safe_name = _safe_filename(disease_area)
	path = playbooks_dir / f"{safe_name}.md"

	existing_lines: list[str] = []
	if path.exists():
		existing_lines = path.read_text().splitlines()

	# Collect existing pattern lines for dedup
	existing_patterns: set[str] = set()
	for line in existing_lines:
		stripped = line.strip()
		if stripped.startswith("- "):
			existing_patterns.add(stripped)

	# Build new content
	if not existing_lines:
		existing_lines = [f"# {disease_area} Playbook", ""]

	added = 0
	for pattern in new_patterns:
		entry = f"- {pattern}"
		if entry not in existing_patterns:
			existing_lines.append(entry)
			existing_patterns.add(entry)
			added += 1

	existing_lines.append("")  # trailing newline
	path.write_text("\n".join(existing_lines))
	logger.info("Updated playbook %s: added %d new patterns", path, added)
	return path
