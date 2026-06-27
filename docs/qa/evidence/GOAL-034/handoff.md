# Handoff

## Completed

- `graph:` is recognized as a mapping with `nodes:` and `edges:`.
- Graph nodes require `id` and `kind`.
- Graph edges require `from` and `to`, and unresolved node references are
  errors.
- `contracts:` is recognized as a list of named contract mappings.
- Contracts can reference graph nodes plus declared approval and budget names.
- Unknown contract graph, approval, and budget references are errors.
- `nornyx: "0.2"` is accepted by the checker for graph contract documents.
- Schema and grammar summaries include graph and contract structures.
- The schema summary now identifies the schema as a `0.1`/`0.2`
  compatibility schema.
- Known core graph node refs are checked when `ref` is supplied; custom/domain
  kinds remain optional and are not promoted into core.

## Next

Recommended next goal: GOAL-035 — v0.3 Domain Profiles.

Recommended reasoning level: High.

## Guardrails

Do not start domain profiles until GOAL-034 is reviewed and approved. Keep
domain profiles declarative and do not introduce adapters, runtime execution,
live connectors, automatic approvals, self-modification, or production
deployment.
