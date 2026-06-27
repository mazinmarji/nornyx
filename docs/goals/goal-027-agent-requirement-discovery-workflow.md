# GOAL-027 — Agent Requirement Discovery Workflow

## Goal

Add a safe workflow for Codex, Claude, and other agents to record newly discovered requirements or gaps during implementation without expanding current scope.

## Scope

Add:

```text
ADR
workflow documentation
candidate template
agent instruction snippet
candidate directory
example candidate
JSON schema
local validator
check script
tests
evidence note
```

## Non-goals

Do not add:

```text
live agent hooks
automatic file mutation beyond candidate files
LLM calls
connector calls
GitHub writes
automatic approvals
runtime scope expansion
```

## Acceptance

```powershell
python -m pytest -q tests/test_triage_candidates.py
python scripts\dev\check_triage_candidates.py
```

## Operating rule

Agents may discover requirements.  
Agents may record candidates.  
Agents must not implement new scope unless explicitly approved.
