# Expanded Nornyx Graph Demo

`examples/nornyx_graph_demo_expanded.nyx` is a product-facing static graph demo for Nornyx.

It shows Nornyx as a generalized agentic contract/control-plane language for governed AI/software delivery. The graph is a declared contract. It is not a graph runtime.

## What It Demonstrates

The expanded demo declares nodes for:

- intent
- context
- agent
- skill
- policy
- eval
- approval
- evidence
- budget
- trace
- goal
- artifact
- module

It also declares product-readable control-plane relations:

- `uses_context`
- `has_skill`
- `governed_by`
- `validated_by`
- `gated_by`
- `bounded_by`
- `produces_evidence`
- `records_trace`
- `satisfies_intent`
- `produces_artifact`

These relations make the graph understandable to external readers: agents use context and skills, work is governed by policy, goals are validated and gated, budgets bound the work, evidence and traces make the work reviewable, and artifacts satisfy the declared intent.

## How To Validate

```bash
python -m nornyx.cli check examples/nornyx_graph_demo_expanded.nyx
python -m nornyx.cli schema --version 0.2
python -m nornyx.cli schema --version 1.0
python -m pytest -q
```

Expected result: no blocking diagnostics.

## Mission Control / Agentic Development Harness Fit

The expanded graph is a static contract shape that Governed Delivery Control Plane or Agentic Development Harness can read as source-of-truth guidance. It can describe intent, context, agents, policies, evals, approvals, evidence, budgets, traces, goals, and artifacts without executing those concepts.

## Safety Boundary

This demo does not:

- execute graph nodes or edges
- call tools
- call models
- enable live MCP/A2A connectors
- publish packages
- deploy software
- grant automatic approvals
- modify itself
- unlock GOAL-100

Graph edges are semantic, audit, and control relationships. They are not executable transitions.
