from __future__ import annotations

from typing import Callable

from nexus.harness.models import Event


class EventStore:
	"""In-memory event store with callback support for SSE streaming."""

	def __init__(self) -> None:
		self.events: list[Event] = []
		self.callbacks: list[Callable[[Event], None]] = []

	def add(self, event: Event) -> None:
		"""Store an event and dispatch to all registered callbacks."""
		self.events.append(event)
		for callback in self.callbacks:
			callback(event)

	def get_by_session(self, session_id: str) -> list[Event]:
		"""Return all events for a given session."""
		return [e for e in self.events if e.session_id == session_id]

	def get_by_hypothesis(self, hypothesis_id: str) -> list[Event]:
		"""Return all events for a given hypothesis."""
		return [e for e in self.events if e.hypothesis_id == hypothesis_id]

	def register_callback(self, callback: Callable[[Event], None]) -> None:
		"""Register a callback to be invoked on every new event."""
		self.callbacks.append(callback)
