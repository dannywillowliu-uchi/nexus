from unittest.mock import patch

from nexus.learning.writer import update_domain_playbook, write_session_log


def test_write_session_log(tmp_path):
	sessions_dir = tmp_path / "sessions"
	sessions_dir.mkdir()

	with patch("nexus.learning.writer.LEARNING_DIR", tmp_path):
		path = write_session_log(
			session_id="test-001",
			query="BRCA1 breast cancer",
			entities_explored=["BRCA1", "TP53"],
			pivots=[{"from": "BRCA1", "to": "TP53", "reason": "high co-occurrence"}],
			hypotheses=[{"a_name": "BRCA1", "b_name": "PALB2", "c_name": "Olaparib", "novelty_score": 0.9}],
			learnings=["BRCA1 and TP53 frequently co-mutate in triple-negative breast cancer"],
		)

	assert path.exists()
	content = path.read_text()
	assert "test-001" in content
	assert "BRCA1 breast cancer" in content
	assert "BRCA1" in content
	assert "TP53" in content
	assert "high co-occurrence" in content
	assert "Olaparib" in content
	assert "co-mutate" in content


def test_update_domain_playbook(tmp_path):
	playbooks_dir = tmp_path / "playbooks"
	playbooks_dir.mkdir()

	with patch("nexus.learning.writer.LEARNING_DIR", tmp_path):
		path = update_domain_playbook("Breast Cancer", ["Check BRCA1 mutations first", "Consider HER2 status"])
		assert path.exists()
		content = path.read_text()
		assert "Breast Cancer Playbook" in content
		assert "Check BRCA1 mutations first" in content
		assert "Consider HER2 status" in content

		# Deduplication: adding same patterns should not duplicate
		update_domain_playbook("Breast Cancer", ["Check BRCA1 mutations first", "New pattern"])
		content = path.read_text()
		assert content.count("Check BRCA1 mutations first") == 1
		assert "New pattern" in content
