# Final Language Target

Nornyx final target is a full LLM-native engineering language, but it must arrive through disciplined stages.

GOAL-013 records the future language research map in
`docs/RFCs/RFC-0003-full-language-evolution-research.md`. That RFC is
research-only and does not promote syntax, parser/checker behavior, runtime
execution, native backends, connectors, or release actions without a later goal
and human approval.

## Final core

Nornyx should eventually support:

- normal code modules;
- typed data models;
- services;
- functions;
- effect/capability system;
- agents;
- skills;
- tools;
- connectors;
- context graphs;
- memory policies;
- harnesses;
- evals;
- guardrails;
- policies;
- traces;
- evidence;
- approvals;
- incidents;
- self-healing;
- improvement loops;
- extension packages.

## Final product family

- Nornyx Language
- Nornyx CLI
- Nornyx Compiler/Checker
- Nornyx Harness Runtime
- Nornyx Context Builder
- Nornyx Evidence Engine
- Nornyx Connector Runtime
- Nornyx LSP
- Nornyx Registry
- Nornyx Studio

## Final acceptance test

A mature Nornyx system should allow:

```bash
nornyx harness run DevHarness --task TASK-017
```

and produce:

- loaded authoritative context;
- bounded agent execution;
- tool calls under capabilities;
- policy and guardrail decisions;
- tests and evals;
- repair attempts within limit;
- approval requests;
- trace events;
- evidence pack;
- patch/release artifacts.
