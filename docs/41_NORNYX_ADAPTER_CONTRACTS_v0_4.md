# Nornyx v0.4 Adapter Contracts

## Status

Local v0.4 adapter contract surface. Adapters are contract bridges between
Nornyx and external ecosystems. They are not live connector runtimes, production
deployment systems, model callers, credential loaders, or automatic approval
mechanisms.

## Adapter contracts

The initial v0.4 contracts cover:

```text
governed_delivery_control_plane
agentic_development_harness
governance_adapter
telecom_ops
business_ops
```

Each adapter contract declares:

- `execution_mode: contract_only`;
- `live_connector_execution: false`;
- connector manifest references;
- policy references;
- eval references;
- evidence references;
- MCP/A2A connector conformance constraints;
- explicit non-goals for live execution, production deployment, unrestricted
  execution, credential loading, network calls, and automatic approvals.

The schema is `schemas/adapter_contract.schema.json`.

## Connector conformance

MCP and A2A connector manifests remain governed by
`schemas/connector_manifest.schema.json` and the local `connector-plan` report.

For v0.4 adapter contracts:

- connector protocols must be `mcp` or `a2a`;
- default mode must be safe, normally `contract_only`;
- approval must be required;
- endpoint and command targets remain blocked live targets;
- A2A manifests must deny sensitive sharing categories;
- connector reports must show `connectors_enabled: false`,
  `adapters_executed: false`, `network_used: false`,
  `commands_executed: false`, and `credentials_loaded: false`.

## Example

`examples/nornyx_v04_adapter_contracts.nyx` defines the five adapter contracts,
safe MCP/A2A connector manifests, policy/eval/evidence bindings, graph nodes,
and a generic `AdapterBridgeContract`.

Useful checks:

```bash
python -m nornyx.cli check examples/nornyx_v04_adapter_contracts.nyx
python -m nornyx.cli connector-plan examples/nornyx_v04_adapter_contracts.nyx
```

## Non-goals

v0.4 does not enable:

- live connector execution;
- unrestricted adapter execution;
- production deployment;
- credential loading;
- network calls;
- LLM/model calls;
- automatic approvals;
- self-modification.

v0.7 is reserved for deeper adapter and connector-contract hardening after the
v0.5 graph and v0.6 profile conformance bands.
