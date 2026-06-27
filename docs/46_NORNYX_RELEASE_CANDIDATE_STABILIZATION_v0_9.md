# Nornyx v0.9 Release-Candidate Stabilization

## Status

Local v0.9 release-candidate stabilization surface. This is a readiness and
evidence layer only. It does not publish, tag, push, change package versions,
announce release readiness, or unlock regulated/enterprise GOAL-100 work.

## Stabilization Report

`nornyx.release_readiness.build_release_candidate_stabilization_report()`
combines the existing release-readiness report with v0.3-v0.8 maturity-band
checks.

It verifies:

- required release docs, schemas, and examples exist;
- GOAL-033 through GOAL-040 are complete in PMO status;
- GOAL-033 through GOAL-040 evidence directories exist;
- GOAL-042 is locked or locally completed with evidence;
- GOAL-100 remains locked;
- validation commands are declared;
- human release-candidate approval is still required.

The matching schema is
`schemas/release_candidate_stabilization.schema.json`.

## Required Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli release-check --out generated/release_readiness_v0_9.json
python scripts/dev/audit_pmo_status.py
python scripts/release/check_rc_stabilization.py
```

## No-Go Conditions

- failing validation;
- inconsistent PMO status;
- missing maturity-band evidence;
- missing human approval;
- package version change without approval;
- release tag creation without approval;
- publish or public announcement without approval;
- live connector execution;
- production deployment behavior;
- credential exposure.

## Boundary

GOAL-041 prepares release-candidate evidence. After GOAL-042 is separately
approved and completed, v0.9 checks continue to verify that the release boundary
is preserved and GOAL-100 remains locked.
