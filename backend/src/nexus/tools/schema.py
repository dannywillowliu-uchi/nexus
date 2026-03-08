from dataclasses import dataclass, field


@dataclass
class ToolResponse:
	status: str  # "success", "partial", "error"
	confidence_delta: float  # -1.0 to 1.0
	evidence_type: str  # "supporting", "contradicting", "neutral"
	summary: str
	raw_data: dict = field(default_factory=dict)
