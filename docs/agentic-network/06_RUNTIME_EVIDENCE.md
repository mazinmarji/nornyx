# Runtime-Event Evidence

`nornyx agentic-network evidence-validate` ingests one supplied local events
file (`nornyx.agentic_runtime_events.v1`) and validates it against the exact
contract, resolved composition, network lock, and subject revision.

```text
nornyx agentic-network evidence-validate CONTRACT --events events.json --lock nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z --strict
```

Nornyx does not operate agents, intercept live messages, call models, invoke
tools, open connectors, listen on networks, load credentials, grant
approvals, or continuously monitor production. There is no daemon, listener,
webhook, queue consumer, or telemetry collector — inputs are local files.

## The closed event set

`agent_invoked`, `capability_requested`, `capability_allowed`,
`capability_denied`, `delegation_requested`, `delegation_accepted`,
`delegation_rejected`, `handoff_initiated`, `handoff_completed`,
`trust_zone_crossed`, `data_shared`, `approval_requested`,
`approval_granted`, `approval_rejected`, `tool_invoked`, `policy_violation`,
`identity_revoked`, `runtime_failed`. Anything else requires a reviewed
schema revision.

## Every event binds

`network_id`, `contract_digest`, `network_lock_digest`, and
`subject_revision`. Evidence from another contract, lock, network, or
revision fails closed (`AN_EVT_CONTRACT_MISMATCH`, `AN_EVT_LOCK_MISMATCH`,
`AN_EVT_NETWORK_MISMATCH`, `AN_EVT_REVISION_MISMATCH`), as does evidence
validated against a lock that no longer matches the contract
(`AN_EVT_LOCK_STALE`).

## What the ordering validator can and cannot prove

Per mission id, the validator proves **local sequence consistency of the
supplied stream**: unique contiguous sequence numbers starting at 1,
non-decreasing timestamps, dependency events present with lower sequence
numbers, and paired transitions (completion requires initiation, acceptance
requires request, grant requires request, tool invocation requires a prior
allowance). It rejects duplicates and content replays.

It does **not** solve distributed causality, cannot prove events across
systems happened in the claimed order, and never claims complete causal
truth. A runtime can omit or fabricate events; validation proves conformance
of what was supplied against the exact contract revision, nothing more. Hash
validity (including per-event `evidence_artifact` SHA-256 binding) proves
content binding, not event truth. These limitations are embedded in every
report.
