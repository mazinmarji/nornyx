# GOAL-048: v1.0.1 release hygiene and adoption polish

## Phase

v1.0.1 hygiene

## Goal

Align release/status wording after the `v1.0.0` GitHub source release and add
concise public positioning plus a 5-minute local adoption path.

## Non-goals

- Do not publish a Python package.
- Do not deploy software.
- Do not enable live connectors.
- Do not call models.
- Do not grant automatic approvals.
- Do not add autonomous runtime behavior.
- Do not unlock GOAL-100.
- Do not change Nornyx into a general-purpose programming language.

## Scope

- `README.md`
- `docs/releases/RELEASE_NOTES_v1_0.md`
- `docs/pmo/status/current_status.json`
- `docs/48_NORNYX_POSITIONING.md`
- `docs/49_NORNYX_5_MINUTE_ADOPTION.md`
- `manifest.json`
- `docs/qa/evidence/GOAL-048/`

## Result

Completed locally:

- aligned release notes with the existing `v1.0.0` GitHub source release;
- updated PMO freshness date;
- added concise positioning guidance;
- added 5-minute local adoption guide;
- linked positioning, adoption, and release record from README;
- kept GOAL-100 locked.

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check --approved
python scripts/release/check_stable_language.py --approved
python scripts/dev/audit_pmo_status.py
git diff --check
```

## Evidence

`docs/qa/evidence/GOAL-048/`
