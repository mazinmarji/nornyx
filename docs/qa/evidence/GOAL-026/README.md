# GOAL-026 Evidence — Requirement Triage Matrix

## Summary

Adds a requirement triage matrix that classifies Nornyx concepts into core, near-core, extension backlog, profile-specific, outside, and rejected.

## Added

```text
docs/decisions/ADR-0018-requirement-triage-matrix.md
docs/36_NORNYX_REQUIREMENT_TRIAGE_MATRIX.md
docs/backlog/nornyx-requirement-triage-matrix.yaml
schemas/requirement_triage_matrix.schema.json
nornyx/requirement_triage.py
scripts/dev/check_requirement_triage.py
tests/test_requirement_triage_matrix.py
docs/goals/goal-026-requirement-triage-matrix.md
```

## Safety

Local validation and documentation only.

No LLM calls, connectors, credentials, GitHub writes, deployment, approvals, or autonomous actions.

## Validation

```powershell
python -m pytest -q tests/test_requirement_triage_matrix.py
python scripts\dev\check_requirement_triage.py
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence note

The real machine-readable triage matrix validates with zero errors. Category
actions are locked so `extension_backlog`, `profile_specific`,
`outside_nornyx`, and `rejected` concepts cannot silently become implementation
scope by changing action strings.

## Risk note

Risk is medium. The matrix is governance data, but weak classification would
allow scope creep. Implementation risk is low because this patch is local
validation and tests only.

## Approval requirement

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, category/action semantic changes,
or promotion of backlog/profile-specific/outside/rejected concepts into core.
