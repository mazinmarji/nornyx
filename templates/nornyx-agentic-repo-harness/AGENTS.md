# AGENTS.md — Nornyx Harness Overlay

## Project stance

Nornyx is a context-native agentic engineering language for governed AI software systems.

The current repo is a safe v0.1 scaffold. Do not treat it as a production autonomous runtime.

## Agent operating rules

1. Work from a goal packet in `docs/goals/` or `examples/nornyx_roadmap_goals.nyx`.
2. Use a task/goal branch; do not edit `main` directly.
3. Keep changes small and coherent.
4. Run validation gates before reporting success.
5. Update evidence under `docs/qa/evidence/<GOAL-ID>/`.
6. Stop on security ambiguity, dependency changes, connector enablement, or public syntax changes without approval.
7. Never commit secrets, `.env`, credentials, tokens, or customer data.

## Required return format

```markdown
# Goal Result

## Summary
## Goal ID
## Files changed
## Commands run
## Validation result
## Evidence path
## Risks / blockers
## Approval required?
## Next recommended step
```
