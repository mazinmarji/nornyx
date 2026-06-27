# GOAL-026 — Requirement Triage Matrix

## Goal

Add a controlled requirement triage matrix to prevent open-ended Nornyx scope expansion.

## Scope

Add:

```text
ADR
human-readable matrix
machine-readable YAML matrix
schema
local validator
check script
tests
evidence note
```

## Non-goals

Do not add:

```text
new runtime behavior
new language concepts beyond classification
connector calls
LLM calls
automatic backlog generation
project-management platform behavior
```

## Acceptance

```powershell
python -m pytest -q tests/test_requirement_triage_matrix.py
python scripts\dev\check_requirement_triage.py
```

## Next focus

Use this matrix to stop further broad gap discovery and return to:

```text
GOAL-001 — Core block spec freeze
GOAL-002 — Parser/checker hardening
GOAL-003 — Artifact generator hardening
```
