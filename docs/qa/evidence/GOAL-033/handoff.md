# Handoff

## Completed

- `constitution` and `evidence` now produce `INVALID_MAPPING_BLOCK` errors when
  supplied as lists or other non-mapping values.
- Valid `constitution` and `evidence` mappings pass the checker.
- Roadmap wording now reflects:
  - v0.2: Nornyx Graph + stronger generic contract model.
  - v0.3: Domain profiles.
  - v0.4: Adapters and ecosystem bridges.
  - v0.5-v0.9: maturity bands.
  - v1.0: stable generalized agentic contract language.
- PMO status now includes future work cards GOAL-034 through GOAL-042.

## Next

Recommended next goal: GOAL-034 — v0.2 Nornyx Graph and Generic Contract Model.

Recommended reasoning level: High.

## Guardrails

Do not start GOAL-034 until the v0.1.1 cleanup patch is reviewed and approved.
Do not add runtime execution, live connectors, LLM hooks, automatic approvals,
self-modification, production deployment, or enterprise GOAL-100 scope.
