# GOAL-050 - Schema Version Split Planning

## Status

Completed locally and prepared for GitHub merge.

## Goal

Freeze the migration plan for splitting the current compatibility schema into explicit v0.1, v0.2, and v1.0 schema files.

## Scope

- Document current compatibility schema state.
- Define target schema file names and roles.
- Define migration sequence and acceptance criteria.
- Add a regression check that keeps the planning artifact explicit.
- Update PMO and evidence.

## Non-Goals

- No new schema files in this goal.
- No schema registry implementation.
- No CLI behavior changes.
- No checker behavior changes.
- No runtime execution.
- No live connector execution.
- No package publication or deployment.
- No GOAL-100 promotion.

## Validation

- `python -m pytest -q`
- `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx`
- `python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx`
- `python -m nornyx.cli check examples/nornyx_graph_demo.nyx`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/51_SCHEMA_VERSION_SPLIT_PLAN.md`
- `docs/qa/evidence/GOAL-050/README.md`
- `docs/qa/evidence/GOAL-050/test_output.txt`

## Approval

Required before implementing schema split behavior, changing default schema routing, or removing compatibility support.
