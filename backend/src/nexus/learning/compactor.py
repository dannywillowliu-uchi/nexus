from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from nexus.config import settings

logger = logging.getLogger(__name__)

LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"


def _log_compaction(what: str, detail: str, path: Path) -> None:
	"""Append a compaction event to learning/compaction-log.md."""
	log_path = LEARNING_DIR / "compaction-log.md"
	timestamp = datetime.now(timezone.utc).isoformat()
	entry = f"- [{timestamp}] **{what}**: {detail} ({path})\n"
	with open(log_path, "a") as f:
		f.write(entry)


async def _summarize_text(text: str, instruction: str) -> str:
	"""Use Claude to summarize/distill text. Falls back to keeping first 50% of lines."""
	if not settings.anthropic_api_key:
		lines = text.splitlines()
		cutoff = max(1, len(lines) // 2)
		return "\n".join(lines[:cutoff])

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model="claude-sonnet-4-20250514",
			max_tokens=4096,
			messages=[{"role": "user", "content": f"{instruction}\n\n---\n\n{text}"}],
		)
		return message.content[0].text.strip()
	except Exception:
		logger.exception("Claude summarization failed, falling back to truncation")
		lines = text.splitlines()
		cutoff = max(1, len(lines) // 2)
		return "\n".join(lines[:cutoff])


async def compact_session_logs(max_sessions: int = 50) -> bool:
	"""If >max_sessions logs exist, summarize oldest 80% into an archive digest."""
	sessions_dir = LEARNING_DIR / "sessions"
	if not sessions_dir.exists():
		return False

	log_files = sorted(sessions_dir.glob("*.md"))
	if len(log_files) <= max_sessions:
		return False

	# Take oldest 80%
	cutoff = int(len(log_files) * 0.8)
	to_archive = log_files[:cutoff]

	combined = []
	for f in to_archive:
		combined.append(f.read_text())

	full_text = "\n\n---\n\n".join(combined)
	summary = await _summarize_text(
		full_text,
		"Summarize these biological discovery session logs into a concise digest. "
		"Preserve key learnings, successful pivots, and important hypotheses. "
		"Use markdown with bullet points.",
	)

	digest_path = sessions_dir / "archive-digest.md"
	existing = ""
	if digest_path.exists():
		existing = digest_path.read_text() + "\n\n---\n\n"
	digest_path.write_text(existing + summary)

	for f in to_archive:
		f.unlink()

	_log_compaction("session_logs", f"Archived {len(to_archive)} sessions", digest_path)
	return True


async def compact_playbook(playbook_path: Path, max_lines: int = 200) -> bool:
	"""If a playbook exceeds max_lines, distill it using Claude."""
	if not playbook_path.exists():
		return False

	text = playbook_path.read_text()
	lines = text.splitlines()
	if len(lines) <= max_lines:
		return False

	summary = await _summarize_text(
		text,
		"Distill this domain playbook into a more concise version. "
		"Merge similar rules, remove redundancies, and keep the most impactful patterns. "
		"Preserve markdown formatting.",
	)

	playbook_path.write_text(summary)
	_log_compaction("playbook", f"Distilled from {len(lines)} to ~{len(summary.splitlines())} lines", playbook_path)
	return True


async def compact_pivot_rules(max_rules: int = 50) -> bool:
	"""If pivot rules exceed max_rules entries, prune using Claude."""
	rules_path = LEARNING_DIR / "pivot-rules.md"
	if not rules_path.exists():
		return False

	text = rules_path.read_text()
	rule_count = sum(1 for line in text.splitlines() if line.strip().startswith("- "))
	if rule_count <= max_rules:
		return False

	summary = await _summarize_text(
		text,
		"Prune and consolidate these pivot rules. Remove redundant rules, merge similar ones, "
		"and keep only the most effective patterns. Preserve the markdown structure with "
		"stage-based sections.",
	)

	rules_path.write_text(summary)
	_log_compaction("pivot_rules", f"Pruned from {rule_count} rules", rules_path)
	return True
