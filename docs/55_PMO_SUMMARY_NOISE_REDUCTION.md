# PMO Summary Noise Reduction

GOAL-056 keeps the PMO portal readable after the v1.0.1 hygiene sequence.

The top-level PMO `summary` should describe current state, next focus, risk level, and compact roadmap posture. It should not repeat the full completed-goal chain. Detailed history belongs in the `blocks` ledger and the goal evidence packs.

## Current Summary Rule

- Keep `summary.overall_status` short and current.
- Keep `summary.next_recommended_goal` actionable and include the recommended model level.
- Keep roadmap entries compact.
- Put long completion history in completed goal blocks and evidence packs.
- Keep GOAL-100 locked unless a future explicit approval unlocks it.

## Non-Goals

This cleanup does not change checker behavior, schema behavior, package publication, deployment, runtime execution, live connector execution, automatic approval, self-modification, or GOAL-100 status.
