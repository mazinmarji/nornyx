# GOAL-031 Evidence — KPI Measurement and Quality Scoring Pack

## Summary

Adds deterministic local KPI measurement and evidence scoring.

## Added

```text
docs/metrics/NORNYX_KPI_MODEL.md
docs/templates/kpi-result-template.json
nornyx/kpi_metrics.py
nornyx/dev_quality.py
scripts/dev/run_quality.py
scripts/dev/score_evidence.py
scripts/dev/run_kpi_benchmark.py
scripts/dev/check_kpi_measurement.py
tests/test_kpi_metrics.py
tests/fixtures/kpi/evidence_complete/
tests/fixtures/kpi/evidence_incomplete/
docs/goals/goal-031-kpi-measurement-quality-scoring.md
docs/qa/evidence/GOAL-031/patch.diff
docs/qa/evidence/GOAL-031/changed_files.txt
docs/qa/evidence/GOAL-031/test_output.txt
docs/qa/evidence/GOAL-031/risk_note.md
docs/qa/evidence/GOAL-031/handoff.md
docs/qa/evidence/GOAL-031/kpi_validation.json
```

## Safety

Local deterministic checks only.

No LLM calls, connectors, external telemetry, GitHub API calls, remote benchmark service, deployments, or production monitoring.

## Validation

```powershell
python -m pytest -q tests/test_kpi_metrics.py
python scripts\dev\check_kpi_measurement.py
python scripts\dev\run_kpi_benchmark.py --no-write
python scripts\dev\score_evidence.py docs\qa\evidence\GOAL-031
```

## Evidence status

This directory is now scored as a real implementation packet. The local KPI
gate requires GOAL-031 evidence to be reviewable or complete before the PMO
block can be marked complete.

## Evidence note

The KPI benchmark has now been used in a real Codex goal session. GOAL-031 adds
a deterministic validation gate that checks repo readiness and evidence
reviewability without granting approval or writing remote state.

## Risk note

Risk is medium because KPI scores can become false authority if treated as
approval. The implementation keeps KPI scoring local, deterministic,
read-only-by-default, and advisory: it can flag weak evidence, but it cannot
approve, merge, publish, call remote services, or execute work.

## Approval requirement

Human approval is required before GitHub push/PR, merge, release, publication,
external telemetry, remote benchmark services, production monitoring, LLM calls,
or using KPI scores as automatic approval.
