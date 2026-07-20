# Nornyx Positioning

## What Nornyx Is

Nornyx is a generalized agentic contract/control-plane language for governed
AI/software delivery. It defines checkable contracts for intent, context,
agents, skills, policies, evals, approvals, evidence, budgets, traces, graph
relationships, profiles, and adapter contracts.

Its practical role is to replace scattered control artifacts such as
`AGENTS.md`, skills folders, prompt packs, context packs, harness scripts, eval
configs, policy docs, evidence templates, and approval checklists with a single
`.nyx` source of truth.

## What Nornyx Is Not

Nornyx is not:

- a full autonomous runtime;
- a general-purpose programming language;
- a LangGraph, CrewAI, or LangChain replacement;
- a production execution engine;
- a live MCP/A2A connector runtime;
- automatic approval or self-modification;
- regulated/enterprise GOAL-100 promotion.

## Best Use Cases

- Declare governed AI/software delivery contracts.
- Check policy, eval, approval, budget, evidence, and trace relationships.
- Generate local control-plane artifacts from `.nyx` files.
- Model static Nornyx Graph relationships for review and evidence.
- Prepare optional profile and adapter contracts without enabling runtime
  execution.

## Release and Distribution

Nornyx publishes a Python package to PyPI (`pip install nornyx`) for the stable
generalized agentic contract/control-plane language on the 1.x line. The package
(distribution) version is independent of the Nornyx language/schema version — see
[VERSIONING.md](VERSIONING.md). Publishing the package does not deploy software,
enable live connectors, call models, grant automatic approvals, or unlock
GOAL-100. Nornyx remains an executable specification layer, not a runtime.

## Future Tracks

Future work may include schema splits, sharper adoption docs, static Nornyx
Graph demos, editor tooling, distributable framework adapters, and optional
connector/runtime research. Each track requires scoped goals, validation,
evidence, and explicit approval.
