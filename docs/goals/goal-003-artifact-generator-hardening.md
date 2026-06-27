# GOAL-003: Artifact generator hardening

## Phase

v0.1

## Goal

Generate AGENTS.md, skills, harness, policy, eval, trace, evidence contract, and goal ledger from .nyx source.

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

`docs/qa/evidence/GOAL-003/`

## Approval

Human approval is required before merge, release, public syntax change, dependency addition, connector enablement, or security-model change.

## Stop rules

Stop if requirements are ambiguous, validation failures exceed 3 scoped attempts, or the change affects security/capability semantics without explicit approval.
