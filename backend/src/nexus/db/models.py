from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ABCPath(BaseModel):
	"""A three-node path: A -> B -> C through the knowledge graph."""

	a: dict  # {id, name, type}
	b: dict  # {id, name, type}
	c: dict  # {id, name, type}


class EvidenceItem(BaseModel):
	"""A single piece of literature evidence."""

	paper_id: str
	title: str
	snippet: str
	confidence: float


class ConfidenceAssessment(BaseModel):
	"""Multi-dimensional confidence scoring for a hypothesis."""

	graph_evidence: float = 0.0
	graph_reasoning: str = ""
	literature_support: float = 0.0
	literature_reasoning: str = ""
	biological_plausibility: float = 0.0
	plausibility_reasoning: str = ""
	novelty: float = 0.0
	novelty_reasoning: str = ""


class ResearchBrief(BaseModel):
	"""Structured research brief for a hypothesis."""

	hypothesis_title: str
	connection_explanation: str
	literature_evidence: list[EvidenceItem]
	existing_knowledge_comparison: str
	confidence: ConfidenceAssessment
	suggested_validation: str


class Hypothesis(BaseModel):
	"""A generated biological hypothesis."""

	id: UUID
	session_id: UUID
	title: str
	description: str
	disease_area: str
	hypothesis_type: str
	novelty_score: float
	evidence_score: float
	validation_score: float | None = None
	overall_score: float
	abc_path: ABCPath
	evidence_chain: list[EvidenceItem]
	research_brief: ResearchBrief | None = None
	validation_result: dict | None = None
	visualization_url: str | None = None
	is_public: bool = False
	created_at: datetime = Field(default_factory=datetime.utcnow)


class SessionRequest(BaseModel):
	"""Request to start a hypothesis generation session."""

	query: str
	disease_area: str | None = None
	start_entity: str | None = None
	start_type: str = "Disease"
	target_types: list[str] | None = None
	max_hypotheses: int = 10
	reasoning_depth: str = "quick"
	max_pivots: int = 3
	max_hops: int = 2


class SessionStatus(BaseModel):
	"""Status of a running session."""

	id: UUID
	status: str
	pipeline_step: str
	pivot_count: int
	branch_count: int


class FeedEntry(BaseModel):
	"""A public feed entry for a hypothesis."""

	id: UUID
	hypothesis_id: UUID
	disease_area: str
	published_at: datetime


class ExperimentRequest(BaseModel):
	"""Request to run a validation experiment."""

	hypothesis_id: UUID
	provider: str = "strateos"


class ExperimentStatus(BaseModel):
	"""Status of a validation experiment."""

	id: UUID
	hypothesis_id: UUID
	provider: str
	status: str
	result: dict | None = None
