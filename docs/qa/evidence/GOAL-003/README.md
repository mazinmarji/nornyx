# GOAL-003 Evidence — Artifact Generator Hardening

## Summary

GOAL-003 hardens generated compatibility artifacts from `.nyx` source. The
generator now writes bounded task packets for roadmap goals, records a
deterministic generation manifest with artifact hashes, and exposes the
documented `goal-plan` CLI path.

## Changed files

```text
docs/pmo/status/current_status.json
docs/qa/evidence/GOAL-003/README.md
nornyx/cli.py
nornyx/generator.py
tests/test_generator_hardening.py
```

## Validation

```powershell
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli generate examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
```

Final validation on 2026-05-31:

```text
python -m pytest -q
103 passed in 3.26s

python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
Nornyx check passed

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
Nornyx check passed

python -m nornyx.cli generate examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
Generated 23 artifacts in generated\nornyx_goal_plan

python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
Generated 2 goal-plan artifacts in generated\nornyx_goal_plan
```

## Risk

Low to medium. The generator writes additional local artifacts and manifest
metadata, but it does not execute generated content, enable external
connectors, add dependencies, bypass approvals, or change runtime behavior.

## Approval

No external approval is required for this local-only scoped hardening patch.
Human approval is still required before any merge/release/public syntax change,
dependency addition, connector enablement, or security-model change.
