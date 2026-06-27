# GOAL-041: v0.9 release-candidate stabilization

## Phase

v0.9

## Goal

Freeze documentation, complete compatibility review, run migration checks, run
quality gates, prepare release-readiness evidence, and require human approval
before release.

## Result

Completed locally as release-candidate stabilization reports, schema, docs,
quality gates, and evidence. No publish, tag, push, package version change, or
release claim was made.

## Non-goals

- Do not publish.
- Do not create a release tag.
- Do not make production-readiness claims without approval.
- Do not unlock GOAL-042 or GOAL-100.

## Scope

- `docs/`
- `schemas/`
- `examples/`
- `tests/`
- `scripts/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python scripts/release/check_rc_stabilization.py
```

## Evidence

`docs/qa/evidence/GOAL-041/`

## Approval

Human approval is mandatory before release, tag, package version change, or
public announcement.

## Stop rules

Stop on failing validation, incomplete migration evidence, release ambiguity, or
missing human approval.
