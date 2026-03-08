from __future__ import annotations

import uuid
from datetime import datetime, timezone

from nexus.agents.reasoning_agent import generate_quick_summaries
from nexus.db.models import SessionRequest
from nexus.harness.event_store import EventStore
from nexus.harness.harness import Harness
from nexus.harness.models import Event, HarnessConfig
from nexus.harness.validation_agent import run_validation_agent
from nexus.learning.writer import write_session_log
from nexus.pipeline.orchestrator import run_pipeline


async def run_research_session(
	session_id: str,
	request: SessionRequest,
	event_store: EventStore,
) -> dict:
	"""Run a complete research session through the adaptive pipeline.

	Returns {"session_id": str, "hypotheses": list, "pivot_count": int, "events_count": int}
	"""
	# 1. Emit session_created event
	event_store.add(Event(
		event_id=str(uuid.uuid4()),
		session_id=session_id,
		event_type="session_created",
		timestamp=datetime.now(timezone.utc).isoformat(),
	))

	# 2. Run the adaptive pipeline with an on_event callback
	async def on_event(event_type: str, data: dict) -> None:
		event_store.add(Event(
			event_id=str(uuid.uuid4()),
			session_id=session_id,
			event_type=event_type,
			output_data=data,
			timestamp=datetime.now(timezone.utc).isoformat(),
		))

	pipeline_result = await run_pipeline(
		query=request.query,
		start_entity=request.start_entity,
		start_type=request.start_type,
		target_types=request.target_types,
		max_hypotheses=request.max_hypotheses,
		max_pivots=request.max_pivots,
		on_event=on_event,
	)

	# 3. Run validation agent on each hypothesis
	harness = Harness(HarnessConfig(), event_store)
	validated_hypotheses: list[dict] = []

	for i, scored in enumerate(pipeline_result.scored_hypotheses):
		hypothesis_id = str(uuid.uuid4())
		# Find the matching ABCHypothesis object
		abc = pipeline_result.hypotheses[i] if i < len(pipeline_result.hypotheses) else None
		if abc is None:
			validated_hypotheses.append(scored)
			continue

		hypothesis_type = scored.get("hypothesis_type", "connection")
		validation_result = await run_validation_agent(
			hypothesis=abc,
			hypothesis_type=hypothesis_type,
			session_id=session_id,
			hypothesis_id=hypothesis_id,
			harness=harness,
			event_store=event_store,
		)
		scored["validation_result"] = validation_result
		validated_hypotheses.append(scored)

	# 4. Run experiment design + execution for top validated hypotheses
	from nexus.lab.tools import design_experiment, interpret_results, validate_and_execute_protocol

	for scored in validated_hypotheses:
		validation = scored.get("validation_result", {})
		if validation.get("verdict") != "validated":
			continue

		try:
			experiment_spec = await design_experiment(scored, budget_tier="minimal")
			exec_result = await validate_and_execute_protocol(experiment_spec, backend="simulator")

			sim_data = exec_result.get("simulated_results", exec_result.get("cloud_lab_results", {}))
			if sim_data:
				interpretation = await interpret_results(experiment_spec, sim_data)
				exec_result["interpretation"] = interpretation

			scored["experiment"] = exec_result
			pipeline_result.experiment_results.append(exec_result)

			exp_verdict = exec_result.get("interpretation", {}).get("verdict", "")

			# 4a. Update graph edge status based on experiment verdict
			abc_path = scored.get("abc_path", {})
			a_name = abc_path.get("a", {}).get("name", "")
			c_name = abc_path.get("c", {}).get("name", "")
			if a_name and c_name and exp_verdict in ("validated", "refuted"):
				try:
					from nexus.pipeline.orchestrator import _update_graph_edge_status
					await _update_graph_edge_status(
						a_name, c_name, exp_verdict,
						exec_result.get("interpretation", {}).get("confidence", 0),
					)
				except Exception:
					pass  # Graph may not be connected in all environments

			event_store.add(Event(
				event_id=str(uuid.uuid4()),
				session_id=session_id,
				event_type="experiment_complete",
				output_data={
					"hypothesis_title": scored.get("title", ""),
					"status": exec_result.get("status", ""),
					"verdict": exp_verdict,
				},
				timestamp=datetime.now(timezone.utc).isoformat(),
			))

			# 4b. If refuted, try redesign with next budget tier
			if exp_verdict == "refuted" and scored.get("budget_tier_used") != "standard":
				scored["budget_tier_used"] = "standard"
				retry_spec = await design_experiment(scored, budget_tier="standard")
				retry_result = await validate_and_execute_protocol(retry_spec, backend="simulator")
				retry_data = retry_result.get("simulated_results", retry_result.get("cloud_lab_results", {}))
				if retry_data:
					retry_interp = await interpret_results(retry_spec, retry_data)
					retry_result["interpretation"] = retry_interp
				scored["experiment_retry"] = retry_result
				pipeline_result.experiment_results.append(retry_result)

				event_store.add(Event(
					event_id=str(uuid.uuid4()),
					session_id=session_id,
					event_type="experiment_retry",
					output_data={
						"hypothesis_title": scored.get("title", ""),
						"status": retry_result.get("status", ""),
						"verdict": retry_result.get("interpretation", {}).get("verdict", ""),
						"reason": "Redesigned with wider concentration range after refutation",
					},
					timestamp=datetime.now(timezone.utc).isoformat(),
				))
		except Exception as exc:
			scored["experiment"] = {"status": "error", "error": str(exc)}

	# 5. Run reasoning agent on validated hypotheses
	triples = pipeline_result.literature_result.triples if pipeline_result.literature_result else []
	summaries = await generate_quick_summaries(
		hypotheses=pipeline_result.hypotheses,
		triples=triples,
	)
	for i, summary in enumerate(summaries):
		if i < len(validated_hypotheses):
			validated_hypotheses[i]["summary"] = summary

	# 6. Write session learning log
	entities_explored = [pipeline_result.start_entity]
	for pivot in pipeline_result.pivots:
		entities_explored.append(pivot.get("to_entity", ""))

	pivot_log = [
		{"from": p.get("from_entity", ""), "to": p.get("to_entity", ""), "reason": p.get("reason", "")}
		for p in pipeline_result.pivots
	]
	hyp_log = [
		{"a_name": h.a_name, "b_name": h.b_name, "c_name": h.c_name, "novelty_score": h.novelty_score}
		for h in pipeline_result.hypotheses[:10]
	]
	learnings = [f"Explored {len(pipeline_result.hypotheses)} hypotheses with {len(pipeline_result.pivots)} pivots"]

	# Include experiment outcomes in learnings
	for scored in validated_hypotheses:
		exp = scored.get("experiment", {})
		interp = exp.get("interpretation", {})
		if interp.get("verdict"):
			title = scored.get("title", "Unknown")
			learnings.append(
				f"Experiment for '{title}': {interp['verdict']} "
				f"(confidence: {interp.get('confidence', 'N/A')})"
			)
			# Also log concerns/next steps for the playbook
			for concern in interp.get("concerns", []):
				learnings.append(f"  Concern: {concern}")

	write_session_log(
		session_id=session_id,
		query=request.query,
		entities_explored=entities_explored,
		pivots=pivot_log,
		hypotheses=hyp_log,
		learnings=learnings,
	)

	# Update domain playbook with experiment patterns
	from nexus.learning.writer import update_domain_playbook

	disease_area = request.query
	experiment_patterns = []
	for scored in validated_hypotheses:
		exp = scored.get("experiment", {})
		interp = exp.get("interpretation", {})
		verdict = interp.get("verdict", "")
		if verdict:
			compound = scored.get("abc_path", {}).get("c", {}).get("name", "?")
			assay = exp.get("simulated_results", {}).get("analysis", {}).get("summary", "")
			if not assay:
				assay = scored.get("hypothesis_type", "")
			experiment_patterns.append(f"{compound}: {verdict} ({assay[:80]})")
	if experiment_patterns:
		update_domain_playbook(disease_area, experiment_patterns)

	# 7. Emit session_completed event
	event_store.add(Event(
		event_id=str(uuid.uuid4()),
		session_id=session_id,
		event_type="session_completed",
		output_data={
			"hypotheses_count": len(validated_hypotheses),
			"pivot_count": len(pipeline_result.pivots),
		},
		timestamp=datetime.now(timezone.utc).isoformat(),
	))

	# 8. Return results
	return {
		"session_id": session_id,
		"hypotheses": validated_hypotheses,
		"pivot_count": len(pipeline_result.pivots),
		"events_count": len(event_store.get_by_session(session_id)),
	}
