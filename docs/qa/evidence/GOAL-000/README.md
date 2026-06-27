# GOAL-000 Evidence — Green Baseline Stabilization

## Summary

This replacement repository is prepared as the clean baseline before core Nornyx development starts.

## Cleaned

```text
removed stale root patch/diff handoff files
removed generated runtime output
removed package egg-info
removed node_modules from bundled app
removed __pycache__ folders
normalized PMO status contract
restored CLI compatibility commands
restored Developer PMO Portal helper functions
selected apps/nornyx-dev-pmo-portal as the active portal
```

## Validation

Run locally after extracting. Revalidated on 2026-05-31 from the git
baseline on `codex/goal-000-green-baseline-stabilization`:

```powershell
python -m pytest -q
python scripts\dev\run_quality.py --profile fast
python -m nornyx.cli profiles
python -m nornyx.cli adopt status --repo .
```

Result:

```text
python -m pytest -q
95 passed in 2.82s

python scripts\dev\run_quality.py --profile fast
95 passed in 2.35s
Quality gates passed.

python -m nornyx.cli profiles
minimal
standard
ai_coding
regulated
legacy_upgrade
nornyx_language

python -m nornyx.cli adopt status --repo .
returned valid adoption status JSON with has_git=true
```

## Decision

Use this as the full replacement baseline before starting GOAL-001.
GOAL-000 is complete.
