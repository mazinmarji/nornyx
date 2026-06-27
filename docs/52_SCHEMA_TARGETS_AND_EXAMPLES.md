# Schema Targets and Examples

Nornyx now exposes explicit schema targets while keeping the historical compatibility default.

## Schema Targets

| Target | Command | Schema file | Use |
|---|---|---|---|
| `compat` | `python -m nornyx.cli schema` | `schemas/nornyx_v0_1.schema.json` | Default compatibility view for existing tooling |
| `0.1` | `python -m nornyx.cli schema --version 0.1` | `schemas/nornyx_v0_1.schema.json` | Historical scaffold/core compatibility path |
| `0.2` | `python -m nornyx.cli schema --version 0.2` | `schemas/nornyx_v0_2.schema.json` | Static graph and generic contract schema |
| `1.0` | `python -m nornyx.cli schema --version 1.0` | `schemas/nornyx_v1_0.schema.json` | Stable generalized contract-language schema |

The default remains `compat` so existing docs, tests, and integrations that call `python -m nornyx.cli schema` keep working.

## Example Alignment

Use these local checks when orienting examples:

| Example | Document version | Recommended schema target | Check command |
|---|---|---|---|
| `examples/governed_delivery_control_plane.nyx` | `0.1` | `compat` or `0.1` | `python -m nornyx.cli check examples/governed_delivery_control_plane.nyx` |
| `examples/nornyx_roadmap_goals.nyx` | `0.1` | `compat` or `0.1` | `python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx` |
| `examples/nornyx_graph_demo.nyx` | `0.2` | `0.2` or `1.0` | `python -m nornyx.cli check examples/nornyx_graph_demo.nyx` |
| `examples/nornyx_v04_adapter_contracts.nyx` | `0.2` | `0.2` or `1.0` | `python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx` |

The schema command inspects schema metadata. The check command validates `.nyx` documents through the Nornyx checker.

## Safety Boundary

Schema targets do not:

- execute graph edges
- execute agents, tools, or adapters
- enable live MCP/A2A connectors
- call models
- publish packages
- deploy software
- grant automatic approvals
- unlock GOAL-100
- turn Nornyx into a general-purpose programming language

The schema split is adoption and clarity polish around the stable source-release surface.
