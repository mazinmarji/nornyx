# ADR-0033 — Optional Agentic Network Governance Profile

- Status: Proposed
- Date: 2026-07-17
- Decision owner: human repository owner
- Implementation authority: the explicit AN-000/AN-001 request supplied on
  2026-07-17 authorizes this bounded candidate implementation. It does not
  accept this ADR or authorize merge, release, publication, deployment,
  runtime operation, or autonomous approval.

## Context

Nornyx already provides a stable twelve-concept contract language and a local,
data-only profile/module governance architecture. Agentic networks need a
bounded way to declare identities, capabilities, memberships, trust zones,
gates, protocol contracts, revocation, evidence, and human authority. Promoting
those concepts into stable core would overfit the language; implementing a
runtime would violate the control-plane boundary.

## Decision

Add the optional v1-only profile `agentic_network` version `0.1.0`. It directly
requires only the reusable `agentic_network_governance` module version `0.1.0`.
That module directly depends only on `human_approval`; the existing transitive
dependency supplies evidence integrity.

The module owns three reviewed, bundled, closed schemas:

- `agentic_network`: trust zones, memberships, contract-only protocol targets,
  gates, and revocations;
- `agent_identities`: non-human identity declarations, role bindings, bounded
  framework labels, validity, and revocation references;
- `capabilities`: static action classes, scopes, risk, and required governance
  references.

`agent` remains the role/behavior declaration. `agent_identity` is a profile
extension that binds a non-human subject to an existing role and a bounded set
of capabilities; it is not authentication, identity issuance, or a credential.
Capabilities are static permission classes, not runtime tokens or authority
grants.

The fixed check `agentic_network_foundation.v1` validates uniqueness,
references, capability subsets, explicit validity, effective revocation,
high-risk gates, non-human/non-approving identities, and sensitive sharing
boundaries at an explicit `as_of`. It is deterministic and performs no source
analysis, network, process, credential, model, tool, connector, or framework
operation.

Protocol targets are declarations only. AN-001 allows the closed labels `a2a`
and `mcp`, requires `execution_mode: contract_only`, and requires
`live_connector_execution: false`. Endpoints, commands, credentials, token/key
material, inline/remote schemas, expressions, scripts, and approval-granting
fields are prohibited.

Delegation, handoff, network graph relations, export generation, a network lock,
runtime-event evidence ingestion, CrewAI/LangGraph adapters, authentication,
service discovery, and transport are deferred beyond AN-001 and require their
own reviewed decisions. None is implied by this profile.

The stable top-level schema, stable public exports, existing profile-to-module
mappings, and legacy v0.3 projections do not change. The catalog change is
additive: thirteen profiles and seven modules.

## Safety and Authority

Every agent identity has `authority: non_human` and `can_approve: false`.
Contract acceptance remains with named human roles, exact-revision evidence,
invalidation, and expiry. External and contract-only boundaries must deny
sharing secrets, credentials, tokens, and private memory. These controls are
non-exceptable.

## Consequences

Projects can describe and validate a static agentic-network governance contract
using existing local registry, composition, lock, CLI, evidence, and approval
surfaces. Nornyx does not operate the described network or attest that a runtime
obeyed the contract. Hashes bind reviewed bytes, not producer identity or truth.

The implementation requires compatibility evidence, installed-wheel resource
checks, no-network observation, Windows path coverage, Linux real-symlink
coverage, exact-head CI, and independent audit before merge readiness can be
treated as unconditional.

## Rejected Alternatives

- Stable-core identity/capability/network blocks: rejected as premature and
  domain-specific.
- A profile-only rule without a module: rejected because reviewed schema and
  structural enforcement must compose through the governance engine.
- A general agent runtime or framework adapter: rejected as execution scope.
- Inline or remote schemas and arbitrary expressions: rejected as unsafe and
  non-deterministic extension mechanisms.
- Automatic or agent-granted approval: rejected because high-impact authority
  remains human.
