# ADR-0036 — Runtime-Event Evidence Ingestion and Contract Conformance (AN-004)

- Status: Proposed (implementation authorized by the owner's AN-completion goal;
  human review remains the final closure authority)
- Date: 2026-07-19
- Decision owner: human repository owner

## Context

External agent runtimes (or synthetic harnesses) produce local event evidence.
Nornyx must validate that supplied evidence conforms to the exact `.nyx`
contract, the resolved governance composition, the exact agentic-network lock,
and the exact subject revision — without operating agents, intercepting
messages, listening on networks, loading credentials, or granting approvals.

## Decision

Add the bounded validator `nornyx/agentic_evidence.py` (not a stable public
export) and the CLI subcommand `nornyx agentic-network evidence-validate`.
Inputs are local files only: the contract, the network lock, and one JSON
events file. Output is a deterministic conformance report; `--strict` exits
nonzero on failure.

### Owned schema

`agentic_runtime_events_v1.schema.json` (bundled and root copies), schema id
`nornyx.agentic_runtime_events.v1`: a closed envelope with bounded fields —
schema identity/version, event id, network id, mission id, sequence number,
event type, actor/target identity refs, capability/delegation/handoff refs,
trust-zone source/destination, policy decision (`allow`/`deny`), approval ref,
contract digest, network-lock digest, subject revision, input/output digests,
event timestamp, producer (type/id/version), evidence artifact path +
sha256, optional structural signature reference, and dependency event ids.
A signature reference is validated structurally only; Nornyx does not claim
cryptographic identity verification.

### Closed event types

`agent_invoked`, `capability_requested`, `capability_allowed`,
`capability_denied`, `delegation_requested`, `delegation_accepted`,
`delegation_rejected`, `handoff_initiated`, `handoff_completed`,
`trust_zone_crossed`, `data_shared`, `approval_requested`,
`approval_granted`, `approval_rejected`, `tool_invoked`, `policy_violation`,
`identity_revoked`, `runtime_failed`. Any other type requires a reviewed
schema revision.

### Conformance validation (fail closed)

Unknown identity or target; undeclared capability; actor lacking the
capability through identity + authorized membership; invalid delegation or
chain; capability escalation; excessive depth; expired or revoked delegation,
actor, or target; forbidden onward delegation; unauthorized or ungoverned
trust-zone crossing; missing crossing approval; sensitive-category sharing;
missing or stale approval; non-human approval producer where human authority
is required; contract digest mismatch; lock digest mismatch; subject-revision
mismatch; evidence from another network; malformed envelope; unsupported
schema; incorrect or missing evidence artifact hash; duplicate event id or
sequence number; replay; timestamp outside the declared validity window;
impossible ordering; missing dependency event; completion without initiation;
acceptance without request; allow/deny contradiction; tool invocation without
prior capability allowance; approval grant without a prior approval request.

### Ordering model (bounded, documented)

Per mission id: sequence numbers are unique and dependency events must have
lower sequence numbers within the same mission; pairwise transition rules bind
completion/acceptance/grant events to their initiating events; event
timestamps must be non-decreasing along sequence order and inside the
identity/delegation validity intervals in force. The validator proves local
sequence consistency of supplied evidence only; it does not solve distributed
causality and never claims complete causal truth across systems. Hash validity
proves content binding, not event truth.

## Rejected alternatives

- A daemon/listener/webhook/queue consumer — rejected: runtime scope.
- Accepting arbitrary event types with a passthrough — rejected: open sets
  cannot fail closed.
- Vector clocks or general causal inference — rejected: unbounded and
  unfalsifiable from local files; explicit sequence + dependency fields are
  deterministic.
- Cryptographic signature verification — rejected for this phase: no key
  management exists and pretending verification would overclaim.

## Compatibility effect

Purely additive. No existing evidence format (`nornyx.governance_evidence.v1`)
changes; the runtime-events schema is a separate input format.

## Security boundaries

Local files only through existing path/symlink protections; bounded file
sizes; no producer execution; no network; no subprocess; no credentials; the
validator can reject but never approve.

## Public API / CLI / packaging effect

CLI: one subcommand in the `agentic-network` group. No stable public Python
export. Packaging: one new bundled schema (plus root copy).

## Determinism requirements

The report is a deterministic function of (contract, composition, lock,
events file, explicit `as_of`); diagnostics sorted; no wall-clock reads.

## Human authority

Approval-granted events must reference the human approval authority declared
in the contract; producers typed as AI/tool/execution surfaces cannot satisfy
human-approval requirements.

## Non-goals

Operating agents, live interception, model/tool invocation, connectors,
network listeners, credential loading, approval granting, continuous
monitoring, truth attestation.

## Test obligations

Positive stream; single-event mutation matrix; duplicate/replay/gap/ordering
cases; missing dependency; stale revision; wrong lock; cross-network; forged
artifact hash; expired delegation; revoked actor; unauthorized crossing;
sensitive sharing; missing/stale approval; deterministic-report equality;
large bounded file; malformed JSON; installed wheel; no-network; no-process.

## Migration implications

None; additive schema and validator.

## Residual risks

Evidence is supplied, not observed: a runtime can omit or fabricate events;
validation proves conformance of what was supplied against the exact contract
revision, nothing more. This limitation is stated in the report itself.
