# GOAL-054 - README Command Consistency Audit

## Status

Completed locally and prepared for GitHub merge.

## Goal

Align README command examples with the local validation path and manifest command style.

## Scope

- Audit README command blocks.
- Prefer `python -m nornyx.cli ...` in README quick-start commands.
- Add a short command consistency audit note.
- Add regression coverage for README command consistency.
- Update PMO and evidence.

## Non-Goals

- No CLI behavior changes.
- No parser changes.
- No checker changes.
- No schema routing changes.
- No runtime execution.
- No package publication or deployment.
- No live connector execution.
- No GOAL-100 promotion.

## Validation

- `python -m pytest -q`
- `python -m nornyx.cli schema`
- `python -m nornyx.cli schema --version 1.0`
- `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx`
- `python -m nornyx.cli check examples/nornyx_graph_demo.nyx`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/53_README_COMMAND_CONSISTENCY_AUDIT.md`
- `docs/qa/evidence/GOAL-054/README.md`
- `docs/qa/evidence/GOAL-054/test_output.txt`

## Approval

Required before changing CLI behavior, publishing, deploying, enabling live connectors, or unlocking GOAL-100.
