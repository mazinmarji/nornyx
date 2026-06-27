# GOAL-036: v0.4 adapters and ecosystem bridges

## Phase

v0.4

## Goal

Define adapter contracts for Governed Delivery Control Plane, Agentic Development Harness, GovernanceAdapter,
telecom ops, and business ops, plus MCP/A2A connector contract conformance and
policy/eval/evidence integration tests.

## Result

Completed locally as contract-only adapter bridge metadata, schema, example, and
tests. The v0.4 surface does not enable live connector execution.

## Non-goals

- Do not enable live connector execution by default.
- Do not add production deployments.
- Do not add unrestricted adapter execution.
- Do not load credentials, open networks, call models, or grant approvals.

## Scope

- `docs/`
- `schemas/`
- `examples/`
- `tests/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli connector-plan examples/nornyx_v04_adapter_contracts.nyx
```

## Evidence

`docs/qa/evidence/GOAL-036/`

## Approval

Required before adapter contracts are promoted as stable.

## Stop rules

Stop on credential risk, egress ambiguity, live connector execution, or adapter
behavior outside contract-only scope.
