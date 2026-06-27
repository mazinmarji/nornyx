# GOAL-038: v0.6 domain-profile conformance

## Phase

v0.6

## Goal

Harden the v0.3 profile packs into stable conformance rules. This goal starts
after the reusable profile packs exist and should focus on cross-profile
compatibility matrices, conflict detection, migration checks, and stability
criteria.

## Result

Completed locally as static profile conformance metadata, compatibility matrix,
migration guidance, and v1 readiness decisions.

## Non-goals

- Do not implement adapters.
- Do not add runtime execution.
- Do not make profiles override core contract safety rules.
- Do not repeat the v0.3 starter-pack implementation.
- Do not make domain profiles mandatory core language syntax.

## Scope

- `profiles/`
- `schemas/`
- `tests/`
- `docs/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli init --profile ai_coding --name Demo --out generated/profile_conformance_probe.nyx --force
python -m nornyx.cli check generated/profile_conformance_probe.nyx
```

## Evidence

`docs/qa/evidence/GOAL-038/`

## Approval

Required before profile packs are treated as stable.

## Stop rules

Stop if profile-specific rules conflict with generic graph, policy, evidence, or
approval semantics.
