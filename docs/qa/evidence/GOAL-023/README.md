# GOAL-023 Evidence — Handover and Ambiguity Controls

## Summary

Adds near-core candidate support for lifecycle handover contracts and ambiguity controls.

## Added

```text
docs/decisions/ADR-0016-handover-and-ambiguity-controls.md
docs/34_HANDOVER_AND_AMBIGUITY_CONTROLS.md
docs/goals/goal-023-handover-and-ambiguity-controls.md
docs/backlog/nornyx-handover-and-ambiguity-controls.yaml
schemas/handover_contract.schema.json
schemas/ambiguity_control.schema.json
nornyx/handover.py
scripts/dev/check_handover_controls.py
examples/nornyx_handover_and_ambiguity.nyx
tests/test_handover_contracts.py
```

## Safety

Local validation and documentation only.

No LLM calls, connectors, shell execution, credentials, production writes, approvals, deployments, or autonomous actions.

## Validation

```powershell
python -m pytest -q tests/test_handover_contracts.py
python scripts/dev/check_handover_controls.py
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence note

The machine-readable handover pack validates with zero errors. The validator
checks local handover contract shape, ambiguity-control shape, and cross-links
from `blocking_open_questions` to declared `open_question` controls.

## Risk note

Risk is medium because handover and ambiguity controls are near-core candidates.
Implementation risk is low because this remains local validation, schema/docs,
and tests only. The patch does not promote new v0.1 core syntax or add runtime
automation.

## Approval requirement

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, handover promotion into the core,
automatic approvals, ticketing integration, deployment behavior, or
security-model change.
