# Nornyx Clean Replacement Baseline

This repository package is intended to replace the local pre-development repo before starting core implementation.

## What was cleaned

```text
removed stale root patch/diff files
removed old React/Vite PMO portal folder
removed node_modules
removed generated runtime output
removed nornyx.egg-info
removed __pycache__ folders
removed stale PMO integration snippets for the old portal
```

## What was kept

```text
Nornyx source package
tests
examples
schemas
docs
active lightweight Developer PMO Portal under apps/nornyx-dev-pmo-portal
zero-friction adoption pack
KPI/evidence scoring helpers
requirement triage and triage-candidate workflow
authoring assistant roadmap
evergreen/pattern lifecycle docs and validators
```

## Active portal

```text
apps/nornyx-dev-pmo-portal/
```

The old `apps/dev-pmo-portal/` was removed to avoid confusing Codex/Claude.

## Validate after extraction

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

python -m pytest -q
python scripts\dev\run_quality.py --profile standard
python -m nornyx.cli profiles
python -m nornyx.cli adopt status --repo .
```

## First implementation focus

```text
GOAL-000 — Green Baseline Stabilization
GOAL-001 — Core Block Spec Freeze
GOAL-002 — Parser/Checker Hardening
GOAL-003 — Artifact Generator Hardening
```
