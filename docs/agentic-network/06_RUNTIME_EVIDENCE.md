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

Per-event `evidence_artifact.path` values resolve relative to the events
file's own directory and must stay inside it; escapes, symlinks, and hash
mismatches fail closed.

It does **not** solve distributed causality, cannot prove events across
systems happened in the claimed order, and never claims complete causal
truth. A runtime can omit or fabricate events; validation proves conformance
of what was supplied against the exact contract revision, nothing more. Hash
validity (including per-event `evidence_artifact` SHA-256 binding) proves
content binding, not event truth. These limitations are embedded in every
report.

## Runtime-events 1.1 occurrence modes

The schema id remains `nornyx.agentic_runtime_events.v1`. The lock selects an
exact schema version:

- **1.0** is the published Nornyx 1.9.0 shape and behavior.
- **1.1 legacy** adds `occurrence_mode: legacy` to the envelope while retaining
  the old event shape and mission-scoped transition/replay behavior. Existing
  `EvidenceRecorder` calls use this mode with a newly generated 1.1 lock.
- **1.1 explicit** adds `occurrence_mode: explicit` and requires every event to
  carry `occurrence.operation_id`, `occurrence.occurrence_id`, and a contiguous
  one-based `occurrence.attempt`.

The event schema version must match the validated network lock. Historical 1.0
locks remain verifiable; a legacy stream is never silently upgraded.

In explicit mode, a mission represents the complete governed run. An operation
is the stable governed surface, an occurrence is one scheduled execution or
loop/parallel visit, and an attempt is one retry within that occurrence.
Authorization allowances and transition state are attempt-scoped. A successful
occurrence cannot be retried; intentional repeated work uses a new occurrence.

Replay fingerprints ignore only transport restamping (`event_id`, `sequence`,
and `timestamp`) and include the explicit occurrence identity plus every other
substantive field. Identical semantic evidence inside one attempt is replay;
identical work in a new occurrence or retry attempt is not.

## Recording and continuation

Use `EvidenceRecorder.for_occurrences(...)` with a 1.1 lock, then pass a frozen
`RuntimeOccurrence` to `record_occurrence_decision(...)` and
`record_occurrence_observation(...)`. Existing constructor and recording calls
remain available and retain legacy behavior.

`EvidenceRecorder.resume(...)` validates and deeply copies a complete prior
stream, restores mission sequence and occurrence-attempt state, and continues
to return cumulative evidence. The producer, contract, lock, schema/mode, and
subject revision must match, and the resumed evaluation time cannot precede
any recorded event. Differential chunks and multi-producer merging are not
supported.
