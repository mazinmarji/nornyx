# GOAL-016 — Safe Development Acceleration Tooling

## Goal

Add safe tooling that accelerates Nornyx development without introducing live agent execution, external connectors, credentials, or production actions.

## Scope

Add:

```text
safe local quality runner
goal packet scaffolder
PMO status auditor
handoff generator
VS Code tasks
manual CI workflow
developer templates
tests
```

## Non-goals

Do not add:

```text
live LLM calls
MCP/A2A runtime connectors
shell-executing harness runtime
production deployment
credential handling
automatic GitHub writes
autonomous self-modification
```

## Acceptance criteria

```text
python -m pytest -q tests/test_dev_acceleration_overlay.py
python scripts/dev/audit_pmo_status.py
python scripts/dev/scaffold_goal.py GOAL-099 "Example goal" --dry-run
python scripts/dev/export_handoff.py --dry-run
```

## Evidence

```text
docs/qa/evidence/GOAL-016/README.md
tests/test_dev_acceleration_overlay.py
```

## PMO status recommendation

After applying this overlay, add or update a PMO block:

```text
GOAL-016 — Safe Development Acceleration Tooling
status: partial or completed depending on validation
```
