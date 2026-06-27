# Schema Version Split Plan

GOAL-050 freezes the plan for splitting the historical compatibility schema into explicit versioned schema files.

This is a planning artifact only. It does not create new schema files, change the checker, alter CLI behavior, or break compatibility.

## Current State

The active Nornyx document schema is:

- `schemas/nornyx_v0_1.schema.json`

That file is intentionally marked as a compatibility schema and currently declares support for both:

- `0.1`
- `0.2`

This kept early tooling stable while v0.2 graph/contract support matured, but the filename is now confusing for v1.0 public positioning.

## Target Schema Files

The future split should add:

- `schemas/nornyx_v0_1.schema.json`
- `schemas/nornyx_v0_2.schema.json`
- `schemas/nornyx_v1_0.schema.json`

Recommended meaning:

| File | Role | Compatibility |
|---|---|---|
| `schemas/nornyx_v0_1.schema.json` | Historical v0.1 scaffold/core schema | Keeps existing imports and docs stable |
| `schemas/nornyx_v0_2.schema.json` | Static graph and generic contract schema | Supports `graph:` and `contracts:` explicitly |
| `schemas/nornyx_v1_0.schema.json` | Stable generalized contract-language schema | Aggregates stable v0.1-v1.0 contract surface |

The old path must not disappear during the first implementation goal. It should either remain a compatibility file or become a narrow v0.1 schema with an explicit migration note and registry alias.

## Schema Registry Target

The future implementation should add a registry concept in `nornyx/schema_model.py`:

```text
0.1 -> schemas/nornyx_v0_1.schema.json
0.2 -> schemas/nornyx_v0_2.schema.json
1.0 -> schemas/nornyx_v1_0.schema.json
compat -> current default schema path during migration
```

The CLI should remain backward compatible:

```bash
python -m nornyx.cli schema
```

Future optional flags can be added after the registry exists:

```bash
python -m nornyx.cli schema --version 0.1
python -m nornyx.cli schema --version 0.2
python -m nornyx.cli schema --version 1.0
```

## Migration Sequence

1. Add the versioned schema files without deleting the compatibility path.
2. Add a schema registry and tests for version-to-file routing.
3. Keep default CLI schema output compatible until docs and examples are updated.
4. Update docs to distinguish v0.1 core, v0.2 graph/contract, and v1.0 stable surfaces.
5. Add validation tests that representative v0.1, v0.2, and v1.0 examples resolve through the registry.
6. Only after a separate approval, decide whether the historical compatibility path remains an alias or becomes v0.1-only.

## Acceptance Criteria For Implementation

- Existing `python -m nornyx.cli schema` behavior remains usable.
- Existing examples still pass checker validation.
- `schemas/nornyx_v0_1.schema.json` remains present.
- `schemas/nornyx_v0_2.schema.json` is present and declares graph/contract support.
- `schemas/nornyx_v1_0.schema.json` is present and names the stable generalized contract surface.
- Tests verify schema registry routing.
- Release/stable-language checks still report no warnings and no blockers.
- PMO status records the schema split without unlocking GOAL-100.

## Non-Goals

GOAL-050 and the future schema split must not:

- enable runtime execution
- execute graph edges
- enable live MCP/A2A connectors
- call models
- publish a package
- deploy software
- grant automatic approvals
- add self-modification
- unlock GOAL-100
- turn Nornyx into a general-purpose programming language

## Recommended Next Goal

GOAL-051 - Schema Version Split Implementation.

Recommended model/reasoning level: high. The implementation will touch schema contracts, CLI expectations, tests, public docs, and compatibility behavior.
