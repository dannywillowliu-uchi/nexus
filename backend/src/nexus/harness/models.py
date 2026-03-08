from dataclasses import dataclass


@dataclass
class HarnessConfig:
	max_iterations_per_hypothesis: int = 10
	max_total_tool_calls: int = 50
	timeout_minutes: int = 30


@dataclass
class Event:
	event_id: str
	session_id: str
	event_type: str  # "tool_call", "verdict", "session_created", "checkpoint", "pivot"
	hypothesis_id: str | None = None
	tool_name: str | None = None
	input_data: dict | None = None
	output_data: dict | None = None
	confidence_snapshot: float | None = None
	timestamp: str = ""
