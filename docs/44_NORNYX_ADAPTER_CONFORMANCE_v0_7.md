# Nornyx v0.7 Adapter Conformance

## Status

Local v0.7 adapter and connector-contract hardening surface. This layer adds
static adapter conformance reports and MCP/A2A connector-contract schemas while
keeping live connector execution disabled by default.

## Conformance report

`nornyx.connector_runtime.build_adapter_conformance_report()` produces:

- `schema: nornyx.adapter_conformance.v0.7`;
- static adapter decisions;
- embedded connector manifest report;
- policy, eval, evidence, and connector reference checks;
- MCP/A2A connector conformance checks;
- shared adapter non-goal checks;
- safety flags proving no connector or adapter was executed.

The matching schema is `schemas/adapter_conformance_report.schema.json`.

## Connector contract hardening

`schemas/connector_contract_conformance.schema.json` defines the v0.7 connector
contract baseline:

- protocols are limited to `mcp` and `a2a`;
- default mode must be safe;
- approval is required;
- live targets are not allowed;
- sensitive sharing is not allowed.

This complements `schemas/connector_manifest.schema.json`, which still defines
the basic connector manifest shape.

## Adapter requirements

Each adapter contract must:

- use `execution_mode: contract_only`;
- set `live_connector_execution: false`;
- reference declared connectors;
- reference declared policies;
- reference declared evals;
- reference declared evidence artifacts;
- require approval in connector conformance;
- include non-goals for live connector execution, production deployment,
  unrestricted adapter execution, credential loading, network calls, and
  automatic approvals.

## Evidence report

Adapter evidence is a JSON report. It is written locally by
`write_adapter_conformance_report()` and does not open networks, load
credentials, execute commands, call models, execute adapters, or grant
approvals.

## Non-goals

v0.7 does not:

- enable live MCP/A2A connectors;
- load credentials;
- open networks;
- execute external adapters;
- grant automatic approvals;
- deploy software;
- promote adapter behavior beyond contract validation.

Any future live enablement requires a later approved goal with explicit
capability, sandbox, approval, trace, and evidence gates.
