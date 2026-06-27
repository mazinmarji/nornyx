# Nornyx KPI Measurement Model

## Purpose

This model turns Nornyx development from opinion-based improvement into measurable improvement.

It measures whether Nornyx and its agentic development workflow are becoming:

```text
faster
safer
more repeatable
more reviewable
better evidenced
less prone to scope drift
```

## KPI groups

| KPI group | Example metrics |
|---|---|
| Delivery | goal cycle time, blocked tasks, handoff readiness |
| Agent control | denied-path touches, wrong-context edits, repair loops |
| Quality | test pass rate, regression count, generated drift |
| Evidence | evidence score, missing artifacts, reviewability |
| Governance | approval coverage, risk notes, triage candidates |
| Operations | runbook/rollback/support evidence where applicable |

## Evidence score

The default evidence score is deterministic:

| Artifact | Points |
|---|---:|
| `patch.diff` | 20 |
| `changed_files.txt` | 15 |
| `test_output.txt` | 20 |
| `risk_note.md` | 15 |
| `handoff.md` | 10 |
| `README.md` | 10 |
| any `*.json` report | 10 |

Interpretation:

| Score | Status |
|---:|---|
| 90–100 | complete |
| 75–89 | reviewable |
| 50–74 | weak |
| 0–49 | incomplete |

## Repo readiness score

The repo-level benchmark checks local signals:

```text
goals exist
evidence folders exist
triage candidate directory exists
.nyx examples exist
tests exist
dev check scripts exist
run_quality.py exists
```

This is not a business KPI. It is an agentic-development readiness KPI.

## Command

```powershell
python scripts\dev\run_kpi_benchmark.py
python scripts\dev\check_kpi_measurement.py
python scripts\dev\score_evidence.py docs\qa\evidence\GOAL-031
```

## Reviewability gate

GOAL-031 uses the KPI model as a local quality gate:

```text
repo readiness must be strong
evidence score must be reviewable or complete
KPI results must remain deterministic and local
KPI results must not become automatic approval
```

This means KPI scoring can block weak evidence, but it cannot approve a change,
merge a branch, publish a release, or replace human review.

## Boundary

These KPIs are local and deterministic.

They do not call LLMs, external systems, GitHub APIs, deployments, or production services.
