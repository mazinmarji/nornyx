# GOAL-039: v0.7 adapter conformance and connector-contract hardening

## Phase

v0.7

## Goal

Add adapter test harnesses, connector contract schemas, MCP/A2A contract
validation, and adapter evidence reports while keeping live connector execution
disabled by default.

## Result

Completed locally as static adapter conformance reports, connector-contract
conformance schemas, MCP/A2A validation decisions, and local adapter evidence
report helpers.

## Non-goals

- Do not enable live MCP/A2A connectors by default.
- Do not load credentials.
- Do not execute external adapters.
- Do not open networks, run commands, grant approvals, or deploy software.

## Scope

- `schemas/`
- `docs/`
- `tests/`
- `examples/`

## Validation

```bash
python -m pytest -q
python -m nornyx.cli connector-plan examples/nornyx_v04_adapter_contracts.nyx
```

## Evidence

`docs/qa/evidence/GOAL-039/`

## Approval

Mandatory before any connector or adapter behavior moves beyond contract
validation.

## Stop rules

Stop on egress risk, credential risk, endpoint ambiguity, or live connector
execution.
