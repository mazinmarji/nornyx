# GOAL-028 Evidence — Nornyx Authoring Assistant Roadmap

## Summary

Adds the roadmap/backlog layer for easy `.nyx` source creation through CLI/UI/LLM-assisted authoring.

## Added

```text
docs/decisions/ADR-0020-nornyx-authoring-assistant-roadmap.md
docs/38_NORNYX_AUTHORING_ASSISTANT_ROADMAP.md
docs/backlog/nornyx-authoring-assistant-roadmap.yaml
schemas/authoring_assistant_roadmap.schema.json
nornyx/authoring_assistant.py
scripts/dev/check_authoring_assistant_roadmap.py
tests/test_authoring_assistant_roadmap.py
docs/goals/goal-028-authoring-assistant-roadmap.md
```

## Safety

Roadmap and local validation only.

No live LLM calls, fine-tuning pipeline, model hosting, portal implementation, credentials, production writes, approvals, or autonomous actions.

The roadmap now records explicit promotion gates and blocked action IDs so
future implementation cannot quietly bypass checker, capability, evidence, or
human approval boundaries.

## Validation

```powershell
python -m pytest -q tests/test_authoring_assistant_roadmap.py
python scripts\dev\check_authoring_assistant_roadmap.py
```

## Evidence note

The validator checks the real roadmap YAML, required capabilities, authority
rules, non-goals, promotion gates, and blocked actions. GOAL-028 remains a
roadmap/backlog package only.

## Risk note

Risk is medium because authoring assistance can otherwise become an unchecked
drafting or repair loop. Implementation risk is low because this patch is local
documentation, YAML, schema, validation, and tests only.

## Approval requirement

Human approval is required before merge, release, live LLM calls, model
training/hosting, portal implementation, connector/tool calls, automatic repo
writes, production config writes, automatic approval, or making authored drafts
authoritative.
