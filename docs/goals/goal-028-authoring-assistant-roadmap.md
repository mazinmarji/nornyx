# GOAL-028 — Nornyx Authoring Assistant Roadmap

## Goal

Capture the roadmap for making `.nyx` source easy to create through guided CLI/UI/LLM-assisted authoring while preserving checker and human approval authority.

## Scope

Add ADR, roadmap document, roadmap YAML, schema, validator, check script, tests, and evidence note.

## Non-goals

Do not add live LLM calls, fine-tuning pipeline, model hosting, full portal implementation, automatic approval, automatic repo writes, or production integration.

## Acceptance

```powershell
python -m pytest -q tests/test_authoring_assistant_roadmap.py
python scripts\dev\check_authoring_assistant_roadmap.py
```

## Promotion rule

Implement this only after GOAL-001/GOAL-002 make `.nyx` core semantics and checker behavior stable enough to support guided authoring.
