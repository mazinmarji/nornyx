# RFC-0002: Formal Grammar and Schema Model

## Status

Accepted for GOAL-004 as a v0.2 model layer over the YAML-compatible v0.1
source format.

## Problem

Nornyx v0.1 intentionally uses YAML-compatible `.nyx` documents. That keeps the
starter language approachable, but the checker and future tooling still need a
stable grammar and schema target.

## Decision

Nornyx defines a formal model in two compatible layers:

- an EBNF-style grammar summary for the top-level document shape;
- a JSON Schema document for structural validation and tooling integration.

The YAML-compatible parser remains the v0.1 migration path. GOAL-004 does not
replace the parser, add a native compiler, or change runtime behavior.

## Grammar

```ebnf
nornyx_document ::= yaml_mapping
yaml_mapping ::= version_block project_block core_block*
version_block ::= "nornyx" ":" "0.1"
project_block ::= "project" ":" mapping_with_name
core_block ::= constitution_block | intents_block | contexts_block | skills_block
             | policies_block | agents_block | harnesses_block | traces_block
             | evals_block | evidence_block | approvals_block | budgets_block
             | goals_block | deferred_extension_block
named_list_block ::= block_name ":" list(named_mapping)
goal_entry ::= mapping(id, phase, goal, scope, non_goals, validation, evidence, approval, stop_rules)
deferred_extension_block ::= experimental | connectors | guardrails | capabilities
                           | incidents | containment | supply_chain
```

## Schema

The schema is stored at `schemas/nornyx_v0_1.schema.json`. It mirrors the
frozen GOAL-001 block surface and the hardened GOAL-002 goal packet contract.

## Migration

Existing YAML-compatible v0.1 documents remain valid inputs. The formal model
is descriptive and testable; it does not require users to rewrite `.nyx`
documents into a new syntax.

## Non-goals

- No production deployment behavior.
- No secret handling.
- No approval bypass.
- No external connector enablement.
- No native parser replacement in this goal.
