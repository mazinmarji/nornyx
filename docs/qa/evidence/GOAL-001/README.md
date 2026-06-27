# GOAL-001 Evidence — Core Block Spec Freeze

## Summary

GOAL-001 freezes the Nornyx v0.1 core block surface as the current
YAML-compatible control-plane model. The freeze records canonical top-level
block names in the language spec and checker tests without adding runtime
execution, connector behavior, secret handling, or a dedicated parser.

## Changed files

```text
docs/01_LANGUAGE_SPEC_v0_1.md
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-001/README.md
nornyx/checker.py
tests/test_parser_checker.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

Result on 2026-05-31:

```text
python -m pytest -q
97 passed in 1.60s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed
```

## Risk

Low to medium. This freezes and tests the existing v0.1 block surface. It does
not change execution semantics, approvals, policy enforcement, external
connectors, dependencies, or generated artifact formats.

## Approval

Human approval is required before merge by the GOAL-001 packet. The user
requested GOAL-001 execution with merge-and-clear cadence; no separate approval
is required unless this scope expands into public syntax change, release,
dependency addition, connector enablement, or security-model change.
