# GOAL-035: v0.3 domain profiles

## Phase

v0.3

## Goal

Define domain profiles for ai_coding, agentic_repo_harness, telecom_ops,
business_ops, ai_governance, and finance_ops if needed.

## Result

Completed locally as optional v0.3 profile packs layered on the v0.2 static
graph/contract surface. The profile packs are metadata and starter-document
guidance only.

## Non-goals

- Do not implement adapters.
- Do not add domain-specific production runtimes.
- Do not weaken the generic contract model.
- Do not make telecom, business, governance, or finance concepts mandatory core
  language concepts.

## Scope

- `profiles/`
- `docs/`
- `schemas/`
- `tests/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli profiles
```

## Evidence

`docs/qa/evidence/GOAL-035/`

## Approval

Required before profile semantics are treated as stable.

## Stop rules

Stop if profiles bypass graph contracts, policy gates, evidence requirements, or
approval semantics.
