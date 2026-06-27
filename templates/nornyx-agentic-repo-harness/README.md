# Nornyx Agentic Repo Harness Overlay

This is a Nornyx-customized copy of useful patterns from a generic agentic repo harness template.

It is not intended to replace that template. It converts the harness ideas into Nornyx-native scaffolds.

## What this overlay provides

- Nornyx-specific `AGENTS.md`
- Nornyx-specific `CLAUDE.md`
- Nornyx task/goal packet template
- validation-gate scripts
- local skills for parser/checker, generator, evidence, spec/RFC, and security review
- phase-as-goal roadmap model

## Use pattern

```bash
nornyx check examples/nornyx_roadmap_goals.nyx
nornyx goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
bash scripts/agent/run-nornyx-validation-gates.sh
```

## Core rule

Nornyx governs execution surfaces. It does not replace Codex, Claude Code, Cursor, Copilot, CI/CD, or human review.
