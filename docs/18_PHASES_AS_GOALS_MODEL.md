# Phases as Goals Model

## Core decision

Every Nornyx development phase should be represented as an executable **goal packet**.

This aligns the roadmap with how AI execution tools actually work: bounded goals, explicit scope, validation gates, evidence, stop rules, and human approval.

## Why phases should be goals

A phase is too vague for Codex, Claude Code, Cursor, Copilot, or humans unless it is decomposed into goal packets.

Bad:

```text
Build Nornyx v0.2.
```

Good:

```text
GOAL-002: Strengthen parser/checker diagnostics for v0.1 core blocks.
Scope: nornyx/parser.py, nornyx/checker.py, tests/
Validation: pytest, nornyx check examples/*.nyx
Evidence: docs/qa/evidence/GOAL-002/
Stop: grammar ambiguity, unsafe execution, public contract drift.
```

## Goal packet fields

Each phase goal should include:

```yaml
goal:
  id: GOAL-XXX
  phase: v0.1 | v0.2 | v0.3 | v0.5 | v1.0 | future
  title: clear short title
  goal: explicit outcome
  non_goals: what must not be done
  scope: files/modules allowed
  denied_scope: files/modules forbidden
  model_routing: risk and reasoning profile
  validation: deterministic commands
  evidence: evidence path
  approval: required approvals
  stop_rules: when the agent must stop
```

## Branching rule

Use one branch per coherent phase goal or milestone:

```text
goal/G001-spec-freeze
goal/G002-parser-checker
goal/G003-generator-artifacts
goal/G004-harness-runtime
```

Avoid tiny PR spam. Use coherent commits under the goal branch, then one evidence-backed PR.

## Nornyx command

```bash
nornyx goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
```

This generates:

```text
generated/nornyx_goal_plan/goals.yaml
generated/nornyx_goal_plan/GOAL_PLAN.md
```
