# Nornyx Goal Packet Template

## Goal ID

`GOAL-XXX`

## Phase

`v0.1 | v0.2 | v0.3 | v0.5 | v1.0 | future`

## Goal

Clear engineering outcome.

## Non-goals

What this goal must not do.

## Scope

Allowed files/directories.

## Denied scope

Files/directories that must not be modified.

## Model routing

```yaml
model_routing:
  task_class: parser | checker | generator | docs | security | runtime | connector | lsp
  risk_level: low | medium | high | critical
  uncertainty_level: low | medium | high
  reasoning_effort: low | medium | high | maximum
  codex_profile: standard | elevated | maximum | blocked
  claude_review: none | optional | required | opus_required
  human_approval: none | recommended | required | mandatory
```

## Validation commands

```bash
python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
```

## Evidence path

`docs/qa/evidence/GOAL-XXX/`

## Approval gates

Human approval required before syntax changes, security model changes, dependency additions, external connectors, release tags, merge, or public launch.

## Stop rules

Stop after 3 failed scoped attempts or when requirements are ambiguous.
