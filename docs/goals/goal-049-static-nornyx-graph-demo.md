# GOAL-049 - Static Nornyx Graph Demo

## Status

Completed locally and prepared for GitHub merge.

## Goal

Add a concise static Nornyx Graph demo that shows the graph/contract model as a checkable contract for governed AI/software delivery.

## Scope

- Add a dedicated graph demo `.nyx` example.
- Add a short graph demo guide.
- Add regression coverage that checks the demo remains clean.
- Update PMO status and evidence.

## Non-Goals

- No runtime graph execution.
- No live connector execution.
- No model calls.
- No production deployment.
- No automatic approvals.
- No GOAL-100 promotion.
- No general-purpose programming language features.

## Validation

- `python -m nornyx.cli check examples/nornyx_graph_demo.nyx`
- `python -m pytest -q`
- `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx`
- `python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx`
- `python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx`
- `python -m nornyx.cli release-check --approved`
- `python scripts/release/check_stable_language.py --approved`
- `python scripts/dev/audit_pmo_status.py`
- `git diff --check`

## Evidence

- `docs/qa/evidence/GOAL-049/README.md`
- `docs/qa/evidence/GOAL-049/test_output.txt`
- `examples/nornyx_graph_demo.nyx`
- `docs/50_NORNYX_GRAPH_DEMO.md`

## Approval

Required before any claim that the graph demo performs runtime execution, live connector execution, deployment, or regulated/enterprise promotion.
