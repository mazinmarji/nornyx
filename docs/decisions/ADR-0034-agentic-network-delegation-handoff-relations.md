# ADR-0034 — Static Delegation, Handoff, and Network-Relation Governance (AN-002)

- Status: Proposed (implementation authorized by the owner's AN-completion goal;
  human review remains the final closure authority)
- Date: 2026-07-19
- Decision owner: human repository owner

## Context

AN-001 (ADR-0033) deliberately deferred delegation, handoff, and network graph
relations. The `agentic_capabilities_v1` schema pins `delegable: false` and the
fixed check `agentic_network_foundation.v1` rejects any other value with
`AN_DELEGATION_FORBIDDEN`. AN-002 must add static, deterministic, fail-closed
governance for delegation policies and grants, handoff contracts, and a closed
set of network relations without adding stable-core concepts, runtime behavior,
or transport.

## Decision

Evolve the reusable module `agentic_network_governance` from 0.1.0 to 0.2.0.
The module keeps its three governance blocks and gains no new top-level block.
All AN-002 records are closed additive optional arrays inside the existing
profile-owned `agentic_network` block:

- `agentic_network.delegations` — bounded delegation grants;
- `agentic_network.handoffs` — bounded responsibility handoffs;
- `agentic_network.relations` — declared semantic relations.

The bundled block schemas keep their `$id`s and document discriminators
(`nornyx.agentic_network.v1`); the additions are optional, so every valid
AN-001 contract remains valid byte-for-byte. `agentic_capabilities_v1` changes
`delegable` from `const false` to `boolean` and adds the optional bounded
`max_delegation_depth` (integer, 1–8). The module registers a second fixed
structural check, `agentic_network_delegation.v1`, implemented in bounded
Python. The AN-001 check keeps its identity and scope;
`AN_DELEGATION_FORBIDDEN` now fires only when a delegable capability appears
while the composed governance does not include `agentic_network_delegation.v1`
(fail-closed for stale or partial compositions).

### Owned schemas

- `agentic_network_v1.schema.json` (additive: `delegations`, `handoffs`,
  `relations`, and two new revocation target kinds `delegation`, `handoff`).
- `agentic_capabilities_v1.schema.json` (additive: boolean `delegable`,
  optional `max_delegation_depth`).
- `agent_identities_v1.schema.json` is unchanged.

### Owned fixed checks

- `agentic_network_foundation.v1` (existing; delegation-gate behavior above).
- `agentic_network_delegation.v1` (new; delegation, handoff, and relation
  semantics; emits stable `AN_*` diagnostics listed in the module).

### Allowed values

- Delegation `status`: `active`, `suspended`, `revoked`, `expired`.
- Delegation `onward_delegation`: `denied`, `allowed_with_policy`.
- Handoff `status`: `initiated`, `accepted`, `completed`, `rejected`,
  `expired`, `revoked`, `superseded`.
- Relation `type` (closed): `identifies`, `owns`, `advertises_capability`,
  `delegates_to`, `hands_off_to`, `communicates_with`, `crosses_trust_zone`,
  `shares_with`, `requires_approval_from`, `revokes`, `observed_by`.
- Relation endpoint kinds (closed): `agent_identity`, `capability`,
  `trust_zone`, `membership`, `protocol_target`, `delegation`, `handoff`,
  `approval`, `revocation`, `human_role`.
- `max_delegation_depth` and delegation `max_depth`: integers 1–8;
  `current_depth`: 0–8.

### Delegation semantics (validated fail-closed)

Delegator and delegate identities exist, are distinct, active, unexpired, and
unrevoked at `as_of`; the capability exists, is `delegable`, and is possessed
by the delegator through identity and an authorized membership; the delegate is
eligible (membership in the declared target zone); delegated scope is a subset
of the capability scope; purpose is mandatory; validity interval is finite and
consistent; `current_depth < max_depth <= capability.max_delegation_depth`;
onward delegation is explicit, and a delegation whose `parent_delegation_ref`
names a parent requires the parent to allow onward delegation, be active, and
have `current_depth` exactly one less; delegation chains must not cycle;
cross-zone delegation requires a governing gate covering the `delegate` action
class plus human approval; high/critical-risk capability delegation requires
the module approval and contract-review evidence references; sensitive
categories (`secrets`, `credentials`, `tokens`, `private_memory`) never appear
in delegation scopes or shared context.

### Handoff semantics

Handoff transfers responsibility, never authority: source and target
identities exist and are effective; purpose and mission reference are
mandatory; every `required_capability_ref` must already be held by the target
or granted through a referenced valid delegation to the target; a handoff
declares no capability mutation fields; cross-zone handoff is governed like a
zone crossing; sensitive context sharing is denied; terminal states behave
consistently (completion only from `initiated`/`accepted`).

### Relations

Relations are declarations only. Each relation names a closed type, typed
source and target endpoints that must exist, and optional `delegation_ref`
or `handoff_ref` whose endpoints must match the relation endpoints
(`delegates_to`, `hands_off_to` require them). Self-relations are rejected
except `identifies`/`owns` are never self-referential either — all
self-relations are rejected. Relations that imply undeclared authority
(`delegates_to` without a delegation record, `shares_with` across a boundary
whose zones forbid sharing, `requires_approval_from` targeting a non-human
endpoint) are rejected. Contradictory allow/deny (a relation referencing a
revoked or denied subject as if active) fails closed.

## Rejected alternatives

- New top-level blocks (`delegations`, ...) — rejected: expands the stable
  surface and the checker for no benefit; records are network-scoped.
- Reusing the stable `graph` block for relations — rejected: would silently
  change the meaning of an existing stable extension used by graph demos.
- New separate module — rejected: delegation is inseparable from the
  identities/capabilities the existing module owns; a second module would
  duplicate block ownership, which composition forbids.
- Schema `$id` bump to v2 — rejected: would invalidate every existing AN-001
  contract's `schema:` discriminator; additive optional evolution preserves
  byte compatibility.
- Rule-language expansion — rejected (ADR-0023/0029): fixed bounded Python
  checks remain the mechanism.

## Compatibility effect

Existing AN-001 contracts (all with `delegable: false` and no new arrays)
validate identically. Contracts that previously failed with
`AN_DELEGATION_FORBIDDEN` may now validate if fully governed — an intentional,
documented capability addition. Module version 0.1.0→0.2.0 and content hash
change; profile `agentic_network` 0.1.0→0.2.0 references the same module and
its starter is unchanged. No stable-core schema, no v0.3 projection, no public
API, and no existing profile changes.

## Security boundaries

No endpoints, credentials, commands, tokens, keys, executable content, or
runtime behavior. Delegation records cannot raise risk or widen scope; chains
are depth-bounded and acyclic; revocation and expiry are effective at explicit
`as_of`; approval authority remains human; sensitive categories remain
non-shareable and non-delegable; malformed, unknown, ambiguous, contradictory,
stale, expired, revoked, or duplicate input fails closed.

## Public API / CLI / packaging effect

No new stable public Python exports; no CLI change in AN-002 (validation flows
through the existing `nornyx check`/`governance` surfaces); packaging updates
the bundled schemas and module/profile YAML plus root schema copies.

## Determinism requirements

Diagnostics stay sorted and stable; validation depends only on document,
composition, and explicit `as_of`.

## Human authority

Delegation/handoff records grant nothing at runtime; contract acceptance and
cross-zone/high-risk approval remain with the human
`agentic_network_authority`. AI actors, tools, and execution surfaces cannot
approve.

## Non-goals

Executing delegation or handoff, runtime enforcement, authentication,
discovery, transport, credential handling, automatic approval.

## Test obligations

Positive minimal and multi-hop cases; every negative diagnostic; mutation,
ordering, normalization-collision, revocation-timing, expiry-boundary,
approval-contradiction cases; existing-profile non-regression; installed-wheel
resources; zero network and zero subprocess observation.

## Migration implications

Module/profile version bump recorded in the compatibility corpus; no golden
artifact changes; starter unchanged.

## Residual risks

Depth/uniqueness semantics rely on the bounded checker (not the schema alone);
relations describe expectations and cannot prove runtime behavior; static
subset checks cannot model runtime context beyond declared scopes.
