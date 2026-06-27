# GOAL-037: v0.5 graph validation and semantic consistency

## Phase

v0.5

## Goal

Mature graph validation with relationship consistency checks,
unresolved-reference detection, cross-block semantic checks, and graph evidence
completeness checks.

## Result

Completed locally as static graph diagnostics for relation consistency,
duplicate/self-edge warnings, expanded ref targets, and contract auditability
warnings. No graph execution was added.

## Non-goals

- Do not implement broad execution.
- Do not add live connectors.
- Do not treat validation as automatic approval.
- Do not execute graph edges or infer runtime actions from graph relationships.

## Scope

- `nornyx/`
- `schemas/`
- `tests/`
- `docs/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
```

## Evidence

`docs/qa/evidence/GOAL-037/`

## Approval

Required before semantic consistency rules become release gates.

## Stop rules

Stop if graph validation implies hidden runtime action, self-modification, or
automatic approval.
