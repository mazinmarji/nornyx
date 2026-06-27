# GOAL-032 — Zero-Friction Adoption Pack

## Goal

Reduce Nornyx first-use overhead so developers can get value in minutes instead of needing to understand the full governance model upfront.

## Scope

Add:

```text
ADR
adoption guide
roadmap YAML
local adoption helper module
CLI adopt status/init-lite commands
adoption check script
tests
evidence note
```

## Non-goals

Do not add:

```text
live LLM calls
portal wizard implementation
fine-tuned model pipeline
automatic remote Git writes
automatic approval
production enforcement
```

## Acceptance

```powershell
python -m pytest -q tests/test_zero_friction_adoption.py
python scripts\dev\check_adoption_pack.py
python -m nornyx.cli adopt status --repo .
```

## User promise

```text
Run one command, get a minimal .nyx draft, and start safer AI-assisted development without adopting the full Nornyx process immediately.
```
