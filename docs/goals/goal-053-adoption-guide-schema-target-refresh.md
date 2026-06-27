# GOAL-053 - Adoption Guide Schema Target Refresh

## Status

Completed locally and prepared for GitHub merge.

## Goal

Refresh the 5-minute adoption guide and quick-start references so first-time users see the implemented schema target commands.

## Scope

- Add schema target inspection to the 5-minute adoption path.
- Keep the compatibility default explicit.
- Add README quick-start schema target coverage.
- Add a regression check for the adoption guide.
- Update PMO and evidence.

## Non-Goals

- No parser changes.
- No checker changes.
- No schema routing changes.
- No runtime execution.
- No live connector execution.
- No model calls.
- No package publication or deployment.
- No GOAL-100 promotion.

## Validation

- `python -m pytest -q`
- `python -m nornyx.cli schema`
- `python -m nornyx.cli schema --version 0.2`
- `python -m nornyx.cli schema --version 1.0`
- `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx`
- `python -m nornyx.cli check examples/nornyx_graph_demo.nyx`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/49_NORNYX_5_MINUTE_ADOPTION.md`
- `docs/qa/evidence/GOAL-053/README.md`
- `docs/qa/evidence/GOAL-053/test_output.txt`

## Approval

Required before changing schema routing behavior, adding runtime execution, enabling live connectors, publishing, deploying, or unlocking GOAL-100.
