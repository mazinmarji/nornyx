# Nornyx Safe Development Acceleration Overlay

## Purpose

This overlay adds safe developer-productivity scaffolds for the Nornyx language repo.

It is designed to speed up development without introducing risky runtime behavior.

## What it adds

```text
safe local quality runner
goal packet scaffolder
PMO status consistency auditor
handoff generator
VS Code tasks
manual GitHub Actions workflow
templates for goals, handoffs, and release readiness
tests for the acceleration helpers
```

## Safety boundaries

This overlay does **not** add:

```text
live LLM calls
MCP/A2A runtime connectors
shell-executing agent loops
production deployment actions
credential or secret handling
automatic GitHub writes
autonomous self-repair execution
```

## New commands

Run safe quality checks:

```powershell
python scripts/dev/run_quality.py
```

Audit PMO status consistency:

```powershell
python scripts/dev/audit_pmo_status.py
```

Scaffold a new goal packet:

```powershell
python scripts/dev/scaffold_goal.py GOAL-016 "Development acceleration tooling" --dry-run
python scripts/dev/scaffold_goal.py GOAL-016 "Development acceleration tooling" --write
```

Export a handoff from the current PMO status:

```powershell
python scripts/dev/export_handoff.py --out docs/handoff/NORNYX_HANDOFF.md
```

## Recommended use

Use this overlay after the current safe-source scaffold overlay.

Recommended validation:

```powershell
python -m pytest -q
python scripts/dev/run_quality.py
python scripts/dev/audit_pmo_status.py
```

## Why this helps

Nornyx needs to become easy to learn, install, adapt, integrate, and govern. These helpers accelerate the development loop around that goal:

```text
goal planning
status consistency
evidence discipline
local quality gates
handoff continuity
developer ergonomics
```
