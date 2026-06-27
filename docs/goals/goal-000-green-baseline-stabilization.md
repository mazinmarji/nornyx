# GOAL-000 — Green Baseline Stabilization

## Goal

Prepare a clean, green, low-noise repository baseline before starting GOAL-001 core language work.

## Scope

- Remove generated/runtime noise from the repository package.
- Restore CLI/test contract.
- Normalize PMO delivery state.
- Select `apps/nornyx-dev-pmo-portal/` as the active Developer PMO Portal.
- Keep advanced concepts as docs/backlog until core implementation starts.
- Provide Codex/Claude with a clear Fast Lane.

## Non-goals

- Do not expand the Nornyx language core.
- Do not add live LLM calls.
- Do not add deployment automation.
- Do not add GitHub write automation.
- Do not implement the future authoring portal/model.

## Validation

```powershell
python -m pytest -q
python scripts\dev\run_quality.py --profile fast
python -m nornyx.cli profiles
python -m nornyx.cli adopt status --repo .
```

## Evidence

```text
docs/qa/evidence/GOAL-000/
```

## Done definition

```text
repo package is clean
tests pass
PMO status contract passes
portal tests pass
Codex Fast Lane exists
GOAL-001 can start from a stable baseline
```
