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

## M7 versioned interoperability targets

The version field on a protocol target names the external protocol semantics a
project intends to map against. It does **not** make the generated declaration
a protocol-conformance certificate, and it does not import transport behavior
into Nornyx Core.

### MCP `2026-07-28`

MCP `2026-07-28` is an explicit M7 conformance target. The specification's
stateless request model, `Mcp-Method` / `Mcp-Name` routing headers, request-carried
protocol/client metadata, extensions framework, and authorization hardening are
external protocol/runtime semantics.

For Nornyx, the useful boundary is deterministic mapping of a governed
identity/capability/action and its approval/evidence requirements to the
method/tool identity exposed by an MCP enforcement surface. A header or method
name is **not** proof of Nornyx authorization, approval, caller identity, or
runtime truth. Nornyx does not become an MCP gateway and does not inspect live
MCP traffic.

A project may therefore set a protocol target's `version` to `2026-07-28` when
that is the external specification being targeted, while any concrete
method/tool/header projection remains outside Core and must preserve the exact
governed revision and evidence boundary.

### A2A `1.0`

A2A `1.0` is an explicit M7 conformance target. A2A v1.0 places protocol
version on each supported interface, defines version negotiation, adds tenant
scope, and supports cryptographically signed Agent Cards using JWS over
canonicalized card content.

Nornyx intentionally does not reproduce A2A `supportedInterfaces[]`, endpoint
URLs, transport negotiation, discovery, credentials, or tenant routing inside a
protocol declaration. Those are external runtime/discovery concerns. If a
governed design needs to distinguish more than one A2A version, separate
contract-only protocol-target records can carry the relevant version labels
without importing endpoint material.

A successfully verified Agent Card signature can be treated as **external
evidence about the integrity/authenticity of the signed card under the verified
key relationship**. It does not by itself establish Nornyx governing authority,
capability authorization, delegation, approval, trust-zone admission, or
permission to execute an action. Key ownership, issuer trust, and the verifier's
assurance remain external evidence claims unless separately established.

A2A tenant values likewise remain protocol/request context by default. They do
not automatically become a Nornyx identity, membership, trust zone, or authority
scope. A language/schema change is warranted only if a concrete governance use
case demonstrates that this context must become canonical governed semantics.

## Conformance boundary

For both targets, M7 prefers explicit semantic mapping and loss classification
over runtime ownership. A mapping must say whether a semantic is equivalent,
composite/lossy, unsupported, or external. No generated declaration may imply
that Nornyx verified transport execution, authenticated a remote peer, observed
runtime truth, or certified protocol conformance.
