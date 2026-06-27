# GOAL-002 Evidence — Parser and Checker Hardening

## Summary

GOAL-002 strengthens v0.1 diagnostics for core block entries, harness context
references, and governed goal packets. The checker now emits more precise
machine-readable codes, paths, and hints for malformed block entries and
incomplete phase goals.

## Changed files

```text
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-002/README.md
nornyx/checker.py
nornyx/profiles.py
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
100 passed in 1.84s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed
```

## Risk

Low to medium. The checker is stricter for malformed goal packets and named
core block entries, so invalid starter documents now fail earlier. No runtime
execution, connector, dependency, approval bypass, or security-model behavior
was added.

## Approval

No external approval is required for this local-only scoped hardening patch.
Human approval is still required before any merge/release/public syntax change,
dependency addition, connector enablement, or security-model change.
