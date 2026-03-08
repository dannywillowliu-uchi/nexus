from dataclasses import dataclass, field
from enum import Enum


class CheckpointDecision(Enum):
	CONTINUE = "continue"
	PIVOT = "pivot"
	BRANCH = "branch"


@dataclass
class CheckpointResult:
	decision: CheckpointDecision
	reason: str
	pivot_entity: str | None = None
	pivot_entity_type: str | None = None
	confidence: float = 0.0


@dataclass
class CheckpointContext:
	stage: str  # "literature", "graph", "validation", "experiment"
	original_query: str
	current_entity: str
	current_entity_type: str
	pivot_count: int
	max_pivots: int
	triples: list[dict] = field(default_factory=list)
	hypotheses: list[dict] = field(default_factory=list)
	validation_results: list[dict] = field(default_factory=list)
	experiment_results: list[dict] = field(default_factory=list)
