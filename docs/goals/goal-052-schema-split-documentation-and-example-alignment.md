# GOAL-052 - Schema Split Documentation and Example Alignment

## Status

Completed locally and prepared for GitHub merge.

## Goal

Align public docs and example guidance with the implemented schema version registry.

## Scope

- Add a concise schema targets and examples guide.
- Update language spec wording to reference the implemented schema registry.
- Update roadmap wording to remove stale future-split language.
- Link the new guide from README.
- Add a regression check for the guide.
- Update PMO and evidence.

## Non-Goals

- No parser changes.
- No checker changes.
- No schema routing changes.
- No new schema semantics.
- No runtime execution.
- No live connector execution.
- No package publication or deployment.
- No GOAL-100 promotion.

## Validation

- `python -m pytest -q`
- `python -m nornyx.cli schema`
- `python -m nornyx.cli schema --version 0.2`
- `python -m nornyx.cli schema --version 1.0`
- `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx`
- `python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx`
- `python -m nornyx.cli check examples/nornyx_graph_demo.nyx`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md`
- `docs/qa/evidence/GOAL-052/README.md`
- `docs/qa/evidence/GOAL-052/test_output.txt`

## Approval

Required before changing schema routing behavior, changing checker behavior, publishing, deploying, enabling live connectors, or unlocking GOAL-100.
