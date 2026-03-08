from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from nexus.harness.event_store import EventStore
from nexus.harness.models import Event, HarnessConfig


class Harness:
	"""Agent harness with budget enforcement and tool failure tracking."""

	def __init__(self, config: HarnessConfig, event_store: EventStore) -> None:
		self.config = config
		self.event_store = event_store
		self._tool_call_count: int = 0
		self._hypothesis_calls: dict[str, int] = {}
		self._consecutive_failures: dict[str, int] = {}
		self._disabled_tools: set[str] = set()

	def can_continue(self, hypothesis_id: str) -> bool:
		"""Check whether the hypothesis is within budget limits."""
		if self._tool_call_count >= self.config.max_total_tool_calls:
			return False
		hypothesis_count = self._hypothesis_calls.get(hypothesis_id, 0)
		if hypothesis_count >= self.config.max_iterations_per_hypothesis:
			return False
		return True

	def record_tool_call(
		self,
		session_id: str,
		hypothesis_id: str,
		tool_name: str,
		input_data: dict,
		output_data: dict,
		confidence: float,
	) -> Event:
		"""Record a tool call, update counts, and track consecutive failures."""
		self._tool_call_count += 1
		self._hypothesis_calls[hypothesis_id] = self._hypothesis_calls.get(hypothesis_id, 0) + 1

		# Track consecutive failures per tool
		status = output_data.get("status", "")
		if status == "error":
			self._consecutive_failures[tool_name] = self._consecutive_failures.get(tool_name, 0) + 1
			if self._consecutive_failures[tool_name] >= 3:
				self._disabled_tools.add(tool_name)
		else:
			self.reset_failure_count(tool_name)

		event = Event(
			event_id=str(uuid.uuid4()),
			session_id=session_id,
			event_type="tool_call",
			hypothesis_id=hypothesis_id,
			tool_name=tool_name,
			input_data=input_data,
			output_data=output_data,
			confidence_snapshot=confidence,
			timestamp=datetime.now(timezone.utc).isoformat(),
		)
		self.event_store.add(event)
		return event

	def get_available_tools(self, tool_registry: dict[str, Callable]) -> dict[str, Callable]:
		"""Return tools from the registry minus any disabled ones."""
		return {
			name: func
			for name, func in tool_registry.items()
			if name not in self._disabled_tools
		}

	def reset_failure_count(self, tool_name: str) -> None:
		"""Reset the consecutive failure count for a tool."""
		self._consecutive_failures[tool_name] = 0
