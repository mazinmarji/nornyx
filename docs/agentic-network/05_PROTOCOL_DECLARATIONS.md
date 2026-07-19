# Protocol Declarations (A2A-compatible, MCP-compatible)

`nornyx agentic-network generate` emits `a2a_declaration.json` and
`mcp_capability_declaration.json`. These are **declarations, not runtimes**:
Nornyx is not an A2A runtime or an MCP server, opens no connections, and
claims no protocol certification.

## What declarations contain

- static identity labels and capability labels with scopes;
- expected message classes (derived from declared capability actions);
- contract, schema, and version-label identifiers;
- required approvals and evidence expectations;
- trust-zone restrictions and denied sensitive categories
  (`credentials`, `private_memory`, `secrets`, `tokens`);
- the mandatory pair:

  ```yaml
  execution_mode: contract_only
  live_connector_execution: false
  ```

## What declarations can never contain

URLs, IP addresses, hostnames, ports, commands, executable code,
credentials, tokens, keys, secrets, active sessions, runtime-discovery data,
transport activation, deployment instructions, or approval-granting fields.
Generation fails closed (`AN_ARTIFACT_FORBIDDEN_FIELD` /
`AN_ARTIFACT_FORBIDDEN_VALUE`) if any such material would be emitted, and the
source schema already rejects protocol targets carrying it.

## Source of truth

Declarations derive from the contract's `agentic_network.protocol_targets`
records, which the `agentic_network_foundation.v1` check validates: closed
protocol labels (`a2a`, `mcp`), declared identities/memberships/capabilities,
zone-crossing gates, human approval for external boundaries, and sensitive
never-share categories.
