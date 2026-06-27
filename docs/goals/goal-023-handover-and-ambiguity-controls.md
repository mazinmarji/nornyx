# GOAL-023 — Handover and Ambiguity Controls

## Goal

Add near-core design scaffolds for lifecycle handover contracts and ambiguity controls.

## Scope

Add:

```text
handover contract docs
ambiguity-control docs
schemas
local validator
illustrative example
tests
evidence note
```

## Non-goals

Do not add:

```text
product-management platform
operations automation
ticketing integration
LLM calls
connector calls
deployment actions
automatic approvals
```

## Acceptance

```powershell
python -m pytest -q tests/test_handover_contracts.py
```

## Promotion rule

`handover` is the first lifecycle concept to consider for promotion after GOAL-001 and GOAL-002.

`assumption`, `open_question`, and `decision_needed` remain near-core design candidates.
