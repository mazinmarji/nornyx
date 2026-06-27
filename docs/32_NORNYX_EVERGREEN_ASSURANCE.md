# Nornyx Evergreen Assurance

## Purpose

Evergreen Assurance is the mechanism that keeps Nornyx current without letting it become chaotic.

Nornyx should not chase every new tool, model, prompt trick, or repo pattern directly.

Instead:

```text
new idea
→ pattern lifecycle
→ extension/adaptation contract
→ conformance tests
→ compatibility matrix
→ migration/deprecation rules
→ stable adoption
```

## Components

```text
stable kernel
extension registry
compatibility matrix
conformance tests
deprecation policy
security advisory model
maturity levels
vendor-neutral adapters
evidence-backed pattern promotion
```

## Stable kernel

Nornyx core should be slow-moving:

```text
project
goal
intent
context
agent
policy
harness
eval
evidence
approval
trace
budget
delivery_state
```

## Extension registry

Extensions describe fast-moving capabilities:

```yaml
name: MCP
status: candidate
version: "2025-06"
provides:
  - connector_manifest
  - tool_permission_contract
conformance:
  - schemas/connector_manifest.schema.json
  - tests/test_connector_manifest.py
security:
  requires_approval: true
  default_mode: read_only
```

## Compatibility matrix

A repo should declare what it supports:

```yaml
nornyx_version: "0.1"
python:
  supported: ["3.11", "3.12", "3.13"]
profiles:
  supported: ["minimal", "standard", "ai_coding", "regulated", "legacy_upgrade", "nornyx_language"]
extensions:
  mcp:
    status: manifest_validation_only
  a2a:
    status: contract_only
```

## Conformance tests

Every extension should provide:

```text
schema
example
tests
security notes
migration notes
```

## Maturity levels

| Level | Name | Meaning |
|---|---|---|
| 0 | Ad hoc | Manual prompts and tool rituals |
| 1 | Generated instructions | AGENTS.md, skills, portal/status generated |
| 2 | Checked contracts | context, policy, evidence, status consistency checked |
| 3 | Harness runtime | evals, traces, evidence packs, gates |
| 4 | Governed connectors | MCP/A2A/tools under capability and approval |
| 5 | Controlled self-improvement | self-healing/evolution under sandbox, rollback, evidence |

## Command direction

Future CLI commands should include:

```text
nornyx compat
nornyx conformance
nornyx deprecations
nornyx security audit
nornyx maturity
```

This overlay adds the local helper foundation, not full CLI wiring.

## Design rule

```text
Nornyx core remains stable.
New AI innovation enters through tested extensions, adapters, profiles, and evidence-backed patterns.
```
