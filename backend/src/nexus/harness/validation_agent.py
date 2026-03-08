from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from nexus.config import settings
from nexus.graph.abc import ABCHypothesis
from nexus.harness.event_store import EventStore
from nexus.harness.harness import Harness
from nexus.harness.models import Event
from nexus.tools.registry import TOOL_REGISTRY
from nexus.tools.schema import ToolResponse

TOOL_STRATEGIES: dict[str, list[str]] = {
	"drug_repurposing": ["compound_lookup", "predict_structure", "dock_compound", "predict_properties", "literature_validate"],
	"mechanism": ["pathway_overlap", "expression_correlate", "literature_validate"],
	"target_discovery": ["protein_interaction", "predict_structure", "expression_correlate", "literature_validate"],
	"drug_interaction": ["compound_lookup", "dock_compound", "predict_properties", "literature_validate"],
	"comorbidity": ["pathway_overlap", "literature_validate", "expression_correlate"],
	"connection": ["literature_validate", "pathway_overlap", "protein_interaction"],
}

SYSTEM_PROMPT = """You are a validation agent for biomedical hypotheses. You decide which tool to call next to validate or refute a hypothesis.

Available tools: {tools}

Tool descriptions:
- literature_validate: Search scientific literature for evidence supporting or contradicting the hypothesis.
- compound_lookup: Look up compound information (structure, properties, known targets) from public databases.
- pathway_overlap: Check for shared biological pathways between entities.
- protein_interaction: Query protein-protein interaction networks.
- expression_correlate: Correlate gene/protein expression patterns across conditions.
- molecular_dock: Legacy docking tool (compound name + protein name via AutoDock Vina).
- predict_structure: Predict protein 3D structure from amino acid sequence (methods: esmfold, alphafold, chai, boltz). Args: protein_sequence, method.
- dock_compound: Dock a compound (SMILES) against a protein target (methods: autodock_vina, diffdock, gnina). Args: compound_smiles, protein_name, method.
- predict_properties: Predict molecular properties (solubility, thermostability, immunogenicity). Args: sequence_or_smiles, properties.
- batch_screen: Screen multiple compounds against a target and return top hits. Args: compounds, protein_target, method, top_n.
- generate_protocol: Generate an experimental protocol for wet-lab validation.

Recommended tool order for this hypothesis type ({hypothesis_type}): {strategy}

Respond with a JSON object containing:
- "tool_name": the name of the tool to call
- "arguments": a dict of arguments to pass to the tool
- "reasoning": why you chose this tool

Only use tools from the available list. Consider prior results when choosing the next tool."""


def _build_hypothesis_context(hypothesis: ABCHypothesis, hypothesis_type: str) -> str:
	"""Build a text description of the hypothesis for Claude."""
	return (
		f"Hypothesis type: {hypothesis_type}\n"
		f"Entity A: {hypothesis.a_name} ({hypothesis.a_type}, ID: {hypothesis.a_id})\n"
		f"Entity B (intermediary): {hypothesis.b_name} ({hypothesis.b_type}, ID: {hypothesis.b_id})\n"
		f"Entity C: {hypothesis.c_name} ({hypothesis.c_type}, ID: {hypothesis.c_id})\n"
		f"A-B relationship: {hypothesis.ab_relationship}\n"
		f"B-C relationship: {hypothesis.bc_relationship}\n"
		f"Path count: {hypothesis.path_count}\n"
		f"Novelty score: {hypothesis.novelty_score:.2f}\n"
		f"Path strength: {hypothesis.path_strength:.2f}"
	)


def _build_prior_results_context(tool_results: list[dict]) -> str:
	"""Build a summary of prior tool results for Claude."""
	if not tool_results:
		return "No prior tool results."
	lines = []
	for i, result in enumerate(tool_results, 1):
		lines.append(
			f"{i}. {result['tool_name']}: status={result['status']}, "
			f"evidence={result['evidence_type']}, "
			f"confidence_delta={result['confidence_delta']}, "
			f"summary={result['summary']}"
		)
	return "Prior results:\n" + "\n".join(lines)


def _parse_tool_decision(response_text: str) -> dict:
	"""Parse Claude's response to extract tool name and arguments."""
	# Try to extract JSON from the response
	text = response_text.strip()

	# Handle markdown code blocks
	if "```json" in text:
		start = text.index("```json") + 7
		end = text.index("```", start)
		text = text[start:end].strip()
	elif "```" in text:
		start = text.index("```") + 3
		end = text.index("```", start)
		text = text[start:end].strip()

	try:
		return json.loads(text)
	except json.JSONDecodeError:
		# Try to find JSON object in the text
		brace_start = text.find("{")
		brace_end = text.rfind("}")
		if brace_start != -1 and brace_end != -1:
			try:
				return json.loads(text[brace_start:brace_end + 1])
			except json.JSONDecodeError:
				pass
		return {}


async def run_validation_agent(
	hypothesis: ABCHypothesis,
	hypothesis_type: str,
	session_id: str,
	hypothesis_id: str,
	harness: Harness,
	event_store: EventStore,
) -> dict:
	"""Run the validation agent loop for a hypothesis.

	Returns {"verdict": str, "confidence": float, "tool_results": list[dict], "reasoning": str}
	"""
	if not settings.anthropic_api_key:
		return {
			"verdict": "inconclusive",
			"confidence": 0.0,
			"tool_results": [],
			"reasoning": "No API key",
		}

	import anthropic

	client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

	confidence = 0.0
	tool_results: list[dict] = []
	supporting_count = 0
	strategy = TOOL_STRATEGIES.get(hypothesis_type, ["literature_validate"])
	hypothesis_context = _build_hypothesis_context(hypothesis, hypothesis_type)

	while harness.can_continue(hypothesis_id):
		# Check if we have enough supporting evidence
		if supporting_count >= 2:
			break

		available_tools = harness.get_available_tools(TOOL_REGISTRY)
		if not available_tools:
			break

		tool_names = list(available_tools.keys())
		system_prompt = SYSTEM_PROMPT.format(
			tools=", ".join(tool_names),
			hypothesis_type=hypothesis_type,
			strategy=" -> ".join(strategy),
		)

		prior_context = _build_prior_results_context(tool_results)
		user_message = f"{hypothesis_context}\n\n{prior_context}\n\nWhich tool should I call next?"

		try:
			response = await client.messages.create(
				model="claude-sonnet-4-20250514",
				max_tokens=1024,
				system=system_prompt,
				messages=[{"role": "user", "content": user_message}],
			)
		except Exception:
			break

		response_text = response.content[0].text if response.content else ""
		decision = _parse_tool_decision(response_text)

		tool_name = decision.get("tool_name", "")
		arguments = decision.get("arguments", {})

		if not tool_name or tool_name not in available_tools:
			break

		# Execute the tool
		tool_func = available_tools[tool_name]
		try:
			tool_response: ToolResponse = await tool_func(**arguments)
		except Exception as exc:
			tool_response = ToolResponse(
				status="error",
				confidence_delta=0.0,
				evidence_type="neutral",
				summary=f"Tool execution failed: {exc}",
				raw_data={"error": str(exc)},
			)

		# Update confidence
		confidence = max(-1.0, min(1.0, confidence + tool_response.confidence_delta))

		# Track supporting evidence
		if tool_response.evidence_type == "supporting":
			supporting_count += 1

		result_dict = {
			"tool_name": tool_name,
			"status": tool_response.status,
			"confidence_delta": tool_response.confidence_delta,
			"evidence_type": tool_response.evidence_type,
			"summary": tool_response.summary,
			"raw_data": tool_response.raw_data,
		}
		tool_results.append(result_dict)

		# Record via harness
		harness.record_tool_call(
			session_id=session_id,
			hypothesis_id=hypothesis_id,
			tool_name=tool_name,
			input_data=arguments,
			output_data=result_dict,
			confidence=confidence,
		)

	# Render verdict
	if supporting_count >= 2:
		verdict = "validated"
	elif confidence < -0.3:
		verdict = "refuted"
	else:
		verdict = "inconclusive"

	# Record verdict event
	verdict_event = Event(
		event_id=str(uuid.uuid4()),
		session_id=session_id,
		event_type="verdict",
		hypothesis_id=hypothesis_id,
		output_data={"verdict": verdict, "confidence": confidence},
		confidence_snapshot=confidence,
		timestamp=datetime.now(timezone.utc).isoformat(),
	)
	event_store.add(verdict_event)

	reasoning_parts = [f"Ran {len(tool_results)} tool(s)."]
	if supporting_count >= 2:
		reasoning_parts.append(f"Found {supporting_count} supporting results.")
	elif confidence < -0.3:
		reasoning_parts.append(f"Confidence dropped to {confidence:.2f}.")
	else:
		reasoning_parts.append("Insufficient evidence to reach a conclusion.")

	return {
		"verdict": verdict,
		"confidence": confidence,
		"tool_results": tool_results,
		"reasoning": " ".join(reasoning_parts),
	}
