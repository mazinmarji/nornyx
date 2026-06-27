# GOAL-031 — KPI Measurement and Quality Scoring Pack

## Goal

Add local KPI measurement and evidence scoring so Nornyx development can be evaluated by measurable signals instead of only subjective judgment.

## Scope

Add:

```text
KPI model documentation
evidence scoring helper
repo KPI benchmark helper
run_quality profile support
local scripts
fixtures
tests
evidence note
```

## Non-goals

Do not add:

```text
LLM calls
external telemetry
GitHub API calls
remote benchmark service
production monitoring
BI dashboard
agent auto-execution
```

## Acceptance

```powershell
python -m pytest -q tests/test_kpi_metrics.py
python scripts\dev\run_kpi_benchmark.py --no-write
python scripts\dev\score_evidence.py docs\qa\evidence\GOAL-031
```

## KPI intent

Improve future delivery by measuring:

```text
repo readiness
evidence completeness
quality gate reliability
reviewability
agentic development discipline
```
