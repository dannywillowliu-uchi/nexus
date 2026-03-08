from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from nexus.checkpoint.models import CheckpointContext, CheckpointDecision, CheckpointResult
from nexus.config import settings

logger = logging.getLogger(__name__)

LEARNING_DIR = Path(__file__).parent.parent.parent.parent / "learning"

CHECKPOINT_PROMPT = """You are a biological discovery checkpoint agent. Your job is to decide whether
the current investigation should CONTINUE on the same path, PIVOT to a different entity, or BRANCH
to explore a parallel thread.

## Current State
- Stage: {stage}
- Original query: {query}
- Current entity: {entity} ({entity_type})
- Pivot count: {pivot_count}/{max_pivots}

## Results So Far
{results_block}

## Pivot Rules
{pivot_rules}

## Domain Playbook
{playbook}

Based on the above, respond with a JSON object:
{{
  "decision": "continue" | "pivot" | "branch",
  "reason": "brief explanation",
  "pivot_entity": "entity name if pivoting/branching, else null",
  "pivot_entity_type": "entity type if pivoting/branching, else null",
  "confidence": 0.0-1.0
}}

Return ONLY the JSON object, no other text."""


def _build_results_block(ctx: CheckpointContext) -> str:
	"""Build a text block summarizing results from the checkpoint context."""
	parts: list[str] = []
	if ctx.triples:
		parts.append(f"### Triples ({len(ctx.triples)} found)")
		for t in ctx.triples[:10]:
			subj = t.get("subject", "?")
			pred = t.get("predicate", "?")
			obj = t.get("object", "?")
			parts.append(f"- {subj} --{pred}--> {obj}")
	if ctx.hypotheses:
		parts.append(f"\n### Hypotheses ({len(ctx.hypotheses)} found)")
		for h in ctx.hypotheses[:10]:
			parts.append(f"- {h.get('a_name', '?')} -> {h.get('b_name', '?')} -> {h.get('c_name', '?')} "
				f"(novelty: {h.get('novelty_score', '?')})")
	if ctx.validation_results:
		parts.append(f"\n### Validation Results ({len(ctx.validation_results)} found)")
		for v in ctx.validation_results[:10]:
			parts.append(f"- {v.get('tool', '?')}: {v.get('result', '?')}")
	if ctx.experiment_results:
		parts.append(f"\n### Experiment Results ({len(ctx.experiment_results)} found)")
		for e in ctx.experiment_results[:10]:
			parts.append(f"- {e.get('experiment', '?')}: {e.get('outcome', '?')}")
	return "\n".join(parts) if parts else "No results yet."


def _load_pivot_rules() -> str:
	"""Load pivot rules from the learning directory."""
	rules_path = LEARNING_DIR / "pivot-rules.md"
	if rules_path.exists():
		return rules_path.read_text()
	return "No pivot rules defined."


def _load_playbook(ctx: CheckpointContext) -> str:
	"""Load a domain playbook matching the current entity type or query."""
	playbooks_dir = LEARNING_DIR / "playbooks"
	if not playbooks_dir.exists():
		return "No domain playbook available."

	# Try matching by entity type, then by keywords in query
	for candidate in [ctx.current_entity_type.lower(), ctx.current_entity.lower()]:
		safe_name = candidate.replace(" ", "-").replace("/", "-")
		playbook_path = playbooks_dir / f"{safe_name}.md"
		if playbook_path.exists():
			return playbook_path.read_text()

	return "No domain playbook available."


async def run_checkpoint(ctx: CheckpointContext) -> CheckpointResult:
	"""Evaluate whether the discovery pipeline should continue, pivot, or branch."""
	# Budget exhausted: always continue
	if ctx.pivot_count >= ctx.max_pivots:
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="Pivot budget exhausted, continuing on current path.",
			confidence=1.0,
		)

	# No API key: default continue
	if not settings.anthropic_api_key:
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="No API key configured, defaulting to continue.",
			confidence=0.5,
		)

	results_block = _build_results_block(ctx)
	pivot_rules = _load_pivot_rules()
	playbook = _load_playbook(ctx)

	prompt = CHECKPOINT_PROMPT.format(
		stage=ctx.stage,
		query=ctx.original_query,
		entity=ctx.current_entity,
		entity_type=ctx.current_entity_type,
		pivot_count=ctx.pivot_count,
		max_pivots=ctx.max_pivots,
		results_block=results_block,
		pivot_rules=pivot_rules,
		playbook=playbook,
	)

	try:
		client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
		message = await client.messages.create(
			model="claude-haiku-4-5-20251001",
			max_tokens=1024,
			messages=[{"role": "user", "content": prompt}],
		)

		response_text = message.content[0].text.strip()
		# Handle markdown fences
		if response_text.startswith("```"):
			lines = response_text.split("\n")
			lines = [line for line in lines[1:] if line.strip() != "```"]
			response_text = "\n".join(lines)

		data = json.loads(response_text)
		decision = CheckpointDecision(data["decision"])

		return CheckpointResult(
			decision=decision,
			reason=data.get("reason", ""),
			pivot_entity=data.get("pivot_entity"),
			pivot_entity_type=data.get("pivot_entity_type"),
			confidence=float(data.get("confidence", 0.0)),
			branch_entities=data.get("branch_entities"),
		)

	except Exception:
		logger.exception("Checkpoint evaluation failed, defaulting to continue")
		return CheckpointResult(
			decision=CheckpointDecision.CONTINUE,
			reason="Checkpoint evaluation failed, defaulting to continue.",
			confidence=0.0,
		)
