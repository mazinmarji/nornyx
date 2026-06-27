# GOAL-027 Evidence — Agent Requirement Discovery Workflow

## Summary

Adds a local workflow that allows Codex, Claude, and other agents to record new gaps discovered during implementation as triage candidates.

## Added

```text
docs/decisions/ADR-0019-agent-requirement-discovery-workflow.md
docs/37_AGENT_REQUIREMENT_DISCOVERY_WORKFLOW.md
docs/templates/triage-candidate-template.yaml
docs/templates/agent-triage-instruction-snippet.md
docs/backlog/triage-candidates/.gitkeep
docs/backlog/triage-candidates/TC-EXAMPLE-001-non-blocking-example.yaml
schemas/triage_candidate.schema.json
nornyx/triage_candidates.py
scripts/dev/check_triage_candidates.py
tests/test_triage_candidates.py
docs/goals/goal-027-agent-requirement-discovery-workflow.md
```

## Safety

Local validation and documentation only.

No LLM calls, live hooks, connectors, credentials, GitHub writes, deployments, approvals, or autonomous actions.

## Validation

```powershell
python -m pytest -q tests/test_triage_candidates.py
python scripts\dev\check_triage_candidates.py
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence note

Triage candidates now require a stable `concept` key. The candidate checker
loads the Requirement Triage Matrix and rejects classification mismatches when
the concept already exists in the matrix. Unknown concepts remain proposed
candidates for human/architect review.

## Risk note

Risk is medium. This workflow lets agents record discoveries, so weak checks
could encourage scope creep. Implementation risk is low because this remains
local candidate validation, docs, templates, and tests only.

## Approval requirement

Human approval is required before merge, release, public syntax change,
dependency addition, connector enablement, automatic file mutation beyond
candidate files, GitHub writes, automatic approvals, LLM hooks, or
implementation of newly discovered scope.
