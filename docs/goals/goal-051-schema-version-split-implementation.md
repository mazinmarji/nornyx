# GOAL-051 - Schema Version Split Implementation

## Status

Completed locally and prepared for GitHub merge.

## Goal

Implement the additive schema version split planned in GOAL-050 while preserving compatibility with the existing default schema command.

## Scope

- Add explicit v0.2 and v1.0 schema files.
- Keep the historical v0.1 path as the default compatibility schema.
- Add schema registry routing in `nornyx/schema_model.py`.
- Add `nornyx schema --version` selection for `compat`, `0.1`, `0.2`, and `1.0`.
- Add regression coverage for registry routing and schema metadata.
- Update PMO and evidence.

## Non-Goals

- No checker behavior changes.
- No runtime execution.
- No graph edge execution.
- No live MCP/A2A connectors.
- No model calls.
- No package publication or deployment.
- No automatic approvals.
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

- `docs/qa/evidence/GOAL-051/README.md`
- `docs/qa/evidence/GOAL-051/test_output.txt`
- `schemas/nornyx_v0_2.schema.json`
- `schemas/nornyx_v1_0.schema.json`

## Approval

Required before removing compatibility aliases, changing the default schema route away from `compat`, publishing packages, deploying software, enabling live connectors, or unlocking GOAL-100.
