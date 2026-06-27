# GOAL-004: Formal grammar and schema model

## Phase

v0.2

## Goal

Introduce a formal grammar/schema model while keeping YAML-compatible v0.1 migration support.

## Non-goals

- Do not introduce production deployment behavior.
- Do not add secret handling.
- Do not bypass evidence, approval, or validation gates.
- Do not expand scope beyond this goal without a new goal packet.

## Scope

- `nornyx/`
- `examples/`
- `tests/`
- `docs/`
- `generated/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence

`docs/qa/evidence/GOAL-004/`

## Approval

Human approval is required before merge, release, public syntax change, dependency addition, connector enablement, or security-model change.

## Stop rules

Stop if requirements are ambiguous, validation failures exceed 3 scoped attempts, or the change affects security/capability semantics without explicit approval.
