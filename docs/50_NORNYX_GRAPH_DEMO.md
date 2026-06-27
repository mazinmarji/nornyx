# Nornyx Graph Demo

`examples/nornyx_graph_demo.nyx` is a static, validation-first demo of the Nornyx Graph contract surface.

It shows how a `.nyx` file can declare governed AI/software delivery as graph relationships between core language concepts:

- Intent
- Context
- Agent
- Policy
- Eval
- Approval
- Evidence
- Budget
- Goal
- Graph

## What It Demonstrates

The demo declares graph nodes for:

- repository context
- contract-only policy
- planner and reviewer agents
- graph contract eval
- human release approval
- bounded graph demo budget
- graph demo evidence
- GOAL-049

It then declares semantic edges such as:

- context authorizes agents
- policy governs agents and the goal
- eval validates the goal
- approval gates the goal
- budget bounds the goal
- the goal requires evidence
- the planner must produce evidence

The contract block lists the graph nodes that belong to the static demo contract and names the required approval and budget.

## How To Check It

```bash
python -m nornyx.cli check examples/nornyx_graph_demo.nyx
```

Expected result:

```text
No blocking diagnostics.
```

The regression suite also checks the demo:

```bash
python -m pytest -q
```

## Non-Goals

This demo does not:

- execute graph nodes
- call tools
- call models
- connect to MCP/A2A services
- deploy software
- grant automatic approval
- modify itself
- unlock GOAL-100
- turn Nornyx into a general-purpose programming language

## Current Meaning

For v1.0.1, the graph demo is documentation, example source, and checker coverage. It is a source-of-truth contract that can be reviewed and validated locally. It is not a live runtime or connector execution system.
