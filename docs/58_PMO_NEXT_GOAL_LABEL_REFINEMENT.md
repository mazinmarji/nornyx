# PMO Next-Goal Label Refinement

GOAL-059 replaces generic recent PMO `next_goal` labels with concrete goal names after those follow-up goals have been defined.

The PMO portal should make the delivery chain readable without requiring the user to infer whether a generic follow-up was later clarified.

## Label Rule

- Use generic `Next v1.0.1 hygiene follow-up` only for the current forward-looking placeholder.
- Once a follow-up goal is defined, update the previous goal's `next_goal` label to the concrete title.
- Preserve completed goal blocks and evidence history.

## Non-Goals

This refinement does not change CLI behavior, checker behavior, schema behavior, package publication, deployment, runtime execution, live connector execution, automatic approval, self-modification, or GOAL-100 status.
