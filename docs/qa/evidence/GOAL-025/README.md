# GOAL-025 Evidence — Decision Boundary and Evidence Quality

## Summary

Adds regulated-system design candidate support for decision boundaries and evidence quality.

## Added

```text
docs/decisions/ADR-0017-decision-boundary-and-evidence-quality.md
docs/35_DECISION_BOUNDARY_AND_EVIDENCE_QUALITY.md
docs/goals/goal-025-decision-boundary-evidence-quality.md
docs/backlog/nornyx-decision-boundary-evidence-quality.yaml
schemas/decision_boundary.schema.json
schemas/evidence_quality.schema.json
nornyx/regulated_controls.py
scripts/dev/check_regulated_controls.py
examples/nornyx_decision_boundary_evidence_quality.nyx
tests/test_decision_boundary_evidence_quality.py
```

## Safety

Local validation and documentation only.

No LLM calls, connectors, credentials, production writes, approvals, deployments, identity systems, audit databases, or autonomous actions.

## Validation

```powershell
python -m pytest -q tests/test_decision_boundary_evidence_quality.py
python scripts/dev/check_regulated_controls.py
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence note

The machine-readable regulated control pack validates with zero errors. It
links approval-required decision evidence to an evidence-quality contract and
keeps decision boundaries and evidence quality as regulated/enterprise
candidates, not v0.1 core runtime enforcement.

## Risk note

Risk is high conceptually because regulated decision boundaries can affect
human authority and audit expectations. Implementation risk is low because this
patch is local validation, docs, data, and tests only.

## Approval requirement

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, decision-boundary/evidence-quality
promotion into the core, automatic approvals, identity-provider integration,
audit database integration, production writes, deployment behavior, or
security-model change.
