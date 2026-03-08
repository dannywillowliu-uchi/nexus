from unittest.mock import patch

from nexus.learning.compactor import compact_pivot_rules, compact_session_logs


async def test_compact_session_logs_under_threshold(tmp_path):
	sessions_dir = tmp_path / "sessions"
	sessions_dir.mkdir()

	# Create 10 session files (under default threshold of 50)
	for i in range(10):
		(sessions_dir / f"session-{i:03d}.md").write_text(f"# Session {i}\n")

	with patch("nexus.learning.compactor.LEARNING_DIR", tmp_path):
		result = await compact_session_logs(max_sessions=50)

	assert result is False
	# All files should remain
	assert len(list(sessions_dir.glob("*.md"))) == 10


async def test_compact_pivot_rules_under_threshold(tmp_path):
	rules_path = tmp_path / "pivot-rules.md"
	rules_path.write_text("# Pivot Rules\n\n- Rule 1\n- Rule 2\n- Rule 3\n")

	with patch("nexus.learning.compactor.LEARNING_DIR", tmp_path):
		result = await compact_pivot_rules(max_rules=50)

	assert result is False
	# File should be unchanged
	assert "Rule 1" in rules_path.read_text()
