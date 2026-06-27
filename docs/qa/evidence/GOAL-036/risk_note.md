# GOAL-036 Risk Note

Risk is medium. Adapter contracts sit close to external systems, connectors,
credentials, and runtime behavior. This goal intentionally keeps the surface
contract-only.

Mitigations:

- adapter contracts require `execution_mode: contract_only`;
- adapter contracts require `live_connector_execution: false`;
- connector-plan reports `connectors_enabled: false` and
  `adapters_executed: false`;
- MCP/A2A manifests require safe default modes and human approval;
- tests verify policy, eval, evidence, and connector references;
- docs state that live execution, network calls, credential loading, production
  deployment, model calls, and automatic approvals remain out of scope.

Approval is required before adapter contracts are promoted as stable or before
any future live connector enablement is considered.
