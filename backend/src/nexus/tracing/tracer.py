"""Structured tracing for the Nexus pipeline.

Provides hierarchical spans with timing, inputs/outputs, and JSON trace export.
Each span captures what happened, how long it took, and any errors.

Usage:
	tracer = Tracer(session_id="abc123")
	with tracer.span("literature_search", input={"query": "curcumin"}) as s:
		results = await do_search()
		s.set_output({"papers": len(results)})
	tracer.save("traces/session-abc123.json")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

# Module-level tracer singleton
_tracer: Tracer | None = None


@dataclass
class Span:
	"""A single traced operation with timing and metadata."""

	name: str
	span_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
	parent_id: str | None = None
	start_time: float = 0.0
	end_time: float = 0.0
	duration_ms: float = 0.0
	status: str = "ok"
	input_data: dict[str, Any] | None = None
	output_data: dict[str, Any] | None = None
	error: str | None = None
	children: list[Span] = field(default_factory=list)
	metadata: dict[str, Any] = field(default_factory=dict)

	def set_output(self, data: dict[str, Any]) -> None:
		self.output_data = data

	def set_error(self, error: str) -> None:
		self.status = "error"
		self.error = error

	def set_metadata(self, key: str, value: Any) -> None:
		self.metadata[key] = value

	def to_dict(self) -> dict[str, Any]:
		d: dict[str, Any] = {
			"name": self.name,
			"span_id": self.span_id,
			"duration_ms": round(self.duration_ms, 1),
			"status": self.status,
		}
		if self.parent_id:
			d["parent_id"] = self.parent_id
		if self.input_data:
			d["input"] = self.input_data
		if self.output_data:
			d["output"] = self.output_data
		if self.error:
			d["error"] = self.error
		if self.metadata:
			d["metadata"] = self.metadata
		if self.children:
			d["children"] = [c.to_dict() for c in self.children]
		return d


class Tracer:
	"""Hierarchical span-based tracer with JSON export."""

	def __init__(self, session_id: str = "", verbose: bool = True) -> None:
		self.session_id = session_id
		self.verbose = verbose
		self.root_spans: list[Span] = []
		self._span_stack: list[Span] = []
		self._all_spans: list[Span] = []
		self.start_time = time.time()

	@contextmanager
	def span(self, name: str, input_data: dict[str, Any] | None = None) -> Generator[Span, None, None]:
		"""Create a traced span. Nests under the current active span if one exists."""
		s = Span(name=name, input_data=input_data)
		s.start_time = time.time()

		if self._span_stack:
			parent = self._span_stack[-1]
			s.parent_id = parent.span_id
			parent.children.append(s)
		else:
			self.root_spans.append(s)

		self._span_stack.append(s)
		self._all_spans.append(s)

		indent = "  " * (len(self._span_stack) - 1)
		if self.verbose:
			input_summary = ""
			if input_data:
				input_summary = f" | {_summarize(input_data)}"
			print(f"{indent}[TRACE] >> {name}{input_summary}")

		try:
			yield s
		except Exception as exc:
			s.set_error(str(exc))
			if self.verbose:
				print(f"{indent}[TRACE] !! {name} FAILED: {exc}")
			raise
		finally:
			s.end_time = time.time()
			s.duration_ms = (s.end_time - s.start_time) * 1000
			self._span_stack.pop()

			if self.verbose:
				status_icon = "OK" if s.status == "ok" else "ERR"
				output_summary = ""
				if s.output_data:
					output_summary = f" | {_summarize(s.output_data)}"
				print(f"{indent}[TRACE] << {name} [{status_icon} {s.duration_ms:.0f}ms]{output_summary}")

	def to_dict(self) -> dict[str, Any]:
		total_ms = (time.time() - self.start_time) * 1000
		return {
			"session_id": self.session_id,
			"total_duration_ms": round(total_ms, 1),
			"span_count": len(self._all_spans),
			"spans": [s.to_dict() for s in self.root_spans],
		}

	def save(self, path: str | Path) -> Path:
		"""Save the trace to a JSON file."""
		p = Path(path)
		p.parent.mkdir(parents=True, exist_ok=True)
		with open(p, "w") as f:
			json.dump(self.to_dict(), f, indent=2, default=str)
		if self.verbose:
			print(f"\n[TRACE] Saved to {p} ({len(self._all_spans)} spans)")
		return p

	def print_summary(self) -> None:
		"""Print a compact summary of all spans."""
		total_ms = (time.time() - self.start_time) * 1000
		print(f"\n{'='*60}")
		print(f"TRACE SUMMARY | session={self.session_id} | {total_ms:.0f}ms total | {len(self._all_spans)} spans")
		print(f"{'='*60}")
		for span in self.root_spans:
			_print_span_tree(span, indent=0)
		print(f"{'='*60}\n")


def get_tracer() -> Tracer | None:
	"""Get the module-level tracer singleton."""
	return _tracer


def set_tracer(tracer: Tracer | None) -> None:
	"""Set the module-level tracer singleton."""
	global _tracer
	_tracer = tracer


def _summarize(data: dict[str, Any], max_len: int = 80) -> str:
	"""Create a compact summary of a dict for trace output."""
	parts = []
	for k, v in data.items():
		if isinstance(v, list):
			parts.append(f"{k}=[{len(v)} items]")
		elif isinstance(v, dict):
			parts.append(f"{k}={{...}}")
		elif isinstance(v, str) and len(v) > 40:
			parts.append(f"{k}={v[:40]}...")
		else:
			parts.append(f"{k}={v}")
	text = ", ".join(parts)
	return text[:max_len] + "..." if len(text) > max_len else text


def _print_span_tree(span: Span, indent: int = 0) -> None:
	"""Recursively print a span tree."""
	prefix = "  " * indent
	icon = "OK" if span.status == "ok" else "ERR"
	line = f"{prefix}[{icon}] {span.name} ({span.duration_ms:.0f}ms)"
	if span.error:
		line += f" - {span.error[:60]}"
	print(line)
	for child in span.children:
		_print_span_tree(child, indent + 1)
