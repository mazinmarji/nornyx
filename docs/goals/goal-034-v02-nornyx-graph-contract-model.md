# GOAL-034: v0.2 Nornyx Graph and generic contract model

## Phase

v0.2

## Goal

Design and implement the Nornyx Graph contract model: declared nodes, edges,
generic contract blocks, stronger schemas, semantic checker maturity,
diagnostics, provenance/trust relationships, and approval/budget consistency.

## Non-goals

- Do not implement domain profiles.
- Do not implement adapters.
- Do not add runtime execution or live connector execution.

## Scope

- `docs/`
- `schemas/`
- `nornyx/`
- `tests/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
```

## Evidence

`docs/qa/evidence/GOAL-034/`

## Approval

Required before graph syntax or contract semantics become stable.

## Stop rules

Stop if graph semantics imply hidden runtime execution, automatic approvals, or
unbounded connector behavior.
