from __future__ import annotations

import anthropic

from nexus.config import settings
from nexus.tools.schema import ToolResponse


PROTOCOL_SYSTEM_PROMPT = """You are a wet-lab protocol designer. Given a biological hypothesis, generate a structured experimental protocol to test it. Include:
1. Objective
2. Materials needed
3. Step-by-step procedure
4. Controls (positive and negative)
5. Expected results
6. Estimated timeline
7. Safety considerations

Return the protocol as a JSON object with these keys: objective, materials, steps, controls, expected_results, timeline, safety."""


async def generate_protocol(hypothesis: dict) -> ToolResponse:
	"""Use Claude to generate a wet-lab protocol for testing a hypothesis."""
	if not settings.anthropic_api_key:
		return ToolResponse(
			status="partial",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary="Protocol generation skipped: no Anthropic API key configured.",
			raw_data={"reason": "missing_api_key"},
		)

	a_name = hypothesis.get("a_name", "")
	b_name = hypothesis.get("b_name", "")
	c_name = hypothesis.get("c_name", "")
	ab_relationship = hypothesis.get("ab_relationship", "")
	bc_relationship = hypothesis.get("bc_relationship", "")

	user_prompt = (
		f"Generate a wet-lab protocol to test this hypothesis:\n"
		f"Entity A: {a_name}\n"
		f"Intermediary B: {b_name}\n"
		f"Entity C: {c_name}\n"
		f"A-B relationship: {ab_relationship}\n"
		f"B-C relationship: {bc_relationship}\n"
		f"Hypothesis: {a_name} may be connected to {c_name} through {b_name}."
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

		message = await client.messages.create(
			model="claude-sonnet-4-20250514",
			max_tokens=2048,
			system=PROTOCOL_SYSTEM_PROMPT,
			messages=[{"role": "user", "content": user_prompt}],
		)

		protocol_text = message.content[0].text

		return ToolResponse(
			status="success",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Generated wet-lab protocol for testing {a_name}-{b_name}-{c_name} connection.",
			raw_data={
				"protocol": protocol_text,
				"hypothesis": {
					"a_name": a_name,
					"b_name": b_name,
					"c_name": c_name,
					"ab_relationship": ab_relationship,
					"bc_relationship": bc_relationship,
				},
			},
		)

	except anthropic.APIError as exc:
		return ToolResponse(
			status="error",
			confidence_delta=0.0,
			evidence_type="neutral",
			summary=f"Protocol generation failed: {exc}",
			raw_data={"error": str(exc)},
		)
