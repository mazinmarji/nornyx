# GOAL-033: v0.1.1 cleanup and contract hardening

## Phase

v0.1.1

## Goal

Finish the v0.1.1 cleanup patch: enforce frozen mapping block contracts, align
stale metadata, and make the corrected roadmap visible in PMO.

## Non-goals

- Do not implement Nornyx Graph.
- Do not add runtime execution.
- Do not add live connectors, LLM hooks, automatic approvals, or production deployment.

## Scope

- `nornyx/checker.py`
- `tests/test_parser_checker.py`
- `docs/`
- `examples/nornyx_roadmap_goals.nyx`
- `docs/pmo/status/current_status.json`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence

`docs/qa/evidence/GOAL-033/`

## Approval

Human approval is required before GitHub push, merge, release, or public claim.

## Stop rules

Stop on v0.2 scope creep, runtime execution, connector enablement, or ambiguous
roadmap semantics.
