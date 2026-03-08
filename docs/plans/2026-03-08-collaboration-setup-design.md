# Collaboration Setup Design

**Date:** 2026-03-08
**Context:** Hackathon with 3 parallel collaborators using Claude Code agents

## Problem

Multiple people need to work on different parts of Nexus simultaneously without
stepping on each other. Each person uses their own Claude Code agent.

## Approach

- Each collaborator clones the repo and works on a dedicated domain branch
- Danny (integrator) merges domain branches into `dev`
- A project CLAUDE.md provides agents with domain boundaries and conventions
- Worktrees available for any collaborator's agent to do parallel work locally

## Domain Split

| Domain | Branch | Owner | Primary Modules |
|--------|--------|-------|-----------------|
| Protocol/Formatting | `domain/protocol` | Collaborator A | `cloudlab/`, `tools/generate_protocol.py`, `tools/schema.py` |
| Research Graph/Swanson | `domain/graph` | Collaborator B | `graph/`, `agents/literature/`, `agents/reasoning_agent.py` |
| Architecture/Integration | `dev` | Danny | `pipeline/`, `harness/`, `db/`, `checkpoint/`, `learning/`, `heartbeat/`, `config.py` |

Ownership is advisory, not restrictive. Anyone can touch any file when needed.
Shared files (`db/models.py`, `tools/schema.py`, `config.py`, `pyproject.toml`)
require a heads-up in group chat.

## Deliverables

1. **CLAUDE.md** — Project conventions + domain ownership map
2. **scripts/setup.sh** — One-command bootstrap
3. **.gitignore** — Worktree and Claude state directories
4. **Domain branches** — `domain/protocol` and `domain/graph` off `dev` HEAD
