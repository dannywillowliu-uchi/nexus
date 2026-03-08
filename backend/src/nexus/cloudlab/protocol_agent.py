import json

import anthropic

from nexus.cloudlab.provider import CloudLabProvider, ExperimentProtocol, ExperimentSubmission
from nexus.config import settings
from nexus.graph.abc import ABCHypothesis


async def run_protocol_agent(
	hypothesis: ABCHypothesis,
	hypothesis_type: str,
	provider: CloudLabProvider,
) -> ExperimentSubmission | None:
	if not settings.anthropic_api_key:
		return None

	client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

	prompt = (
		f"You are an expert in designing Autoprotocol experiments for cloud laboratories.\n\n"
		f"Given the following hypothesis from a literature-based discovery system, "
		f"generate an Autoprotocol-formatted JSON experiment design.\n\n"
		f"Hypothesis type: {hypothesis_type}\n"
		f"Path: {hypothesis.a_name} ({hypothesis.a_type}) "
		f"--[{hypothesis.ab_relationship}]--> "
		f"{hypothesis.b_name} ({hypothesis.b_type}) "
		f"--[{hypothesis.bc_relationship}]--> "
		f"{hypothesis.c_name} ({hypothesis.c_type})\n"
		f"Novelty score: {hypothesis.novelty_score}\n"
		f"Path strength: {hypothesis.path_strength}\n\n"
		f"Respond with ONLY a valid JSON object representing the Autoprotocol experiment design. "
		f"No markdown, no explanation, just the JSON."
	)

	message = await client.messages.create(
		model="claude-sonnet-4-20250514",
		max_tokens=2000,
		messages=[{"role": "user", "content": prompt}],
	)

	protocol_text = message.content[0].text
	try:
		protocol_json = json.loads(protocol_text)
	except json.JSONDecodeError:
		protocol_json = {"raw_response": protocol_text}

	hypothesis_id = f"{hypothesis.a_id}-{hypothesis.b_id}-{hypothesis.c_id}"
	protocol = ExperimentProtocol(
		hypothesis_id=hypothesis_id,
		title=f"{hypothesis.a_name} -> {hypothesis.b_name} -> {hypothesis.c_name}",
		description=f"Validate {hypothesis_type} hypothesis: {hypothesis.a_name} connects to {hypothesis.c_name} via {hypothesis.b_name}",
		protocol_json=protocol_json,
	)

	await provider.validate_protocol(protocol)
	submission = await provider.submit_experiment(protocol)
	return submission
