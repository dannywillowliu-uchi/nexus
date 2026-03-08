"""Run PyLabRobot code against SimulatorBackend and capture logs.

Executes generated protocol code in a subprocess, captures stdout/stderr,
and returns structured execution results.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field


@dataclass
class SimulationResult:
	success: bool = False
	logs: list[str] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)
	wells_prepared: int = 0
	protocol_file: str = ""

	def to_dict(self) -> dict:
		return {
			"success": self.success,
			"logs": self.logs,
			"errors": self.errors,
			"wells_prepared": self.wells_prepared,
			"protocol_file": self.protocol_file,
		}


async def run_simulation(protocol_code: str, timeout_seconds: int = 120) -> SimulationResult:
	"""Execute PyLabRobot protocol code in a subprocess.

	Writes the code to a temp file, runs it with Python, captures output.
	Returns structured results with logs and error information.
	"""
	result = SimulationResult()

	# Write protocol to temp file
	with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
		f.write(protocol_code)
		result.protocol_file = f.name

	try:
		proc = await asyncio.create_subprocess_exec(
			"python", result.protocol_file,
			stdout=asyncio.subprocess.PIPE,
			stderr=asyncio.subprocess.PIPE,
		)

		try:
			stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
		except asyncio.TimeoutError:
			proc.kill()
			await proc.communicate()
			result.errors.append(f"Protocol execution timed out after {timeout_seconds} seconds")
			return result

		stdout_text = stdout.decode("utf-8", errors="replace").strip()
		stderr_text = stderr.decode("utf-8", errors="replace").strip()

		if stdout_text:
			result.logs = stdout_text.split("\n")

		if proc.returncode != 0:
			result.errors.append(f"Process exited with code {proc.returncode}")
			if stderr_text:
				result.errors.extend(stderr_text.split("\n"))
			return result

		if stderr_text:
			# Some warnings go to stderr but aren't fatal
			for line in stderr_text.split("\n"):
				if "error" in line.lower() or "traceback" in line.lower():
					result.errors.append(line)
				else:
					result.logs.append(f"[stderr] {line}")

		result.success = True

		# Try to extract wells_prepared from logs
		for line in result.logs:
			if "wells prepared" in line.lower():
				parts = line.split()
				for part in parts:
					if part.isdigit():
						result.wells_prepared = int(part)
						break

	except FileNotFoundError:
		result.errors.append("Python interpreter not found. Cannot run simulation.")
	except Exception as e:
		result.errors.append(f"Simulation error: {e}")

	return result


async def dry_run(protocol_code: str) -> SimulationResult:
	"""Validate protocol code without executing it (syntax check only)."""
	result = SimulationResult()

	try:
		compile(protocol_code, "<protocol>", "exec")
		result.success = True
		result.logs.append("Protocol code syntax is valid.")

		# Count operations
		aspirate_count = protocol_code.count("aspirate")
		dispense_count = protocol_code.count("dispense")
		tip_count = protocol_code.count("pick_up_tips")
		result.logs.append(f"Operations: {aspirate_count} aspirates, {dispense_count} dispenses, {tip_count} tip changes")

	except SyntaxError as e:
		result.errors.append(f"Syntax error at line {e.lineno}: {e.msg}")

	result.protocol_file = "(dry run — no file written)"
	return result
