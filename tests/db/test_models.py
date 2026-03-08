from nexus.db.models import ABCPath, ConfidenceAssessment, SessionRequest


def test_session_request_defaults():
	"""SessionRequest should have correct default values."""
	req = SessionRequest(
		query="test query",
		disease_area="oncology",
		start_entity="TP53",
		start_type="Gene",
		target_types=["Compound"],
	)
	assert req.max_hypotheses == 10
	assert req.reasoning_depth == "quick"
	assert req.max_pivots == 3
	assert req.max_hops == 2


def test_abc_path():
	"""ABCPath should store and return node dicts."""
	path = ABCPath(
		a={"id": "1", "name": "Aspirin", "type": "Compound"},
		b={"id": "2", "name": "COX2", "type": "Gene"},
		c={"id": "3", "name": "Inflammation", "type": "Disease"},
	)
	assert path.a["name"] == "Aspirin"
	assert path.b["type"] == "Gene"
	assert path.c["id"] == "3"


def test_confidence_assessment_defaults():
	"""ConfidenceAssessment should default all scores to 0.0 and strings to empty."""
	assessment = ConfidenceAssessment()
	assert assessment.graph_evidence == 0.0
	assert assessment.graph_reasoning == ""
	assert assessment.literature_support == 0.0
	assert assessment.literature_reasoning == ""
	assert assessment.biological_plausibility == 0.0
	assert assessment.plausibility_reasoning == ""
	assert assessment.novelty == 0.0
	assert assessment.novelty_reasoning == ""
