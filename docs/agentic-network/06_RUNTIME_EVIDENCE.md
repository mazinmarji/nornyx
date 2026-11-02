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

Every event's `producer` must also equal the events file's own `producer`
(`AN_EVT_PRODUCER_MISMATCH`), in every runtime-events schema version. A file
names one producer; merging events from several producers into one file is not
supported. This is internal consistency of the supplied file only: Nornyx does
not authenticate the producer, and a file can name any producer as long as it
names the same one throughout. A missing or non-object per-event `producer` is
reported only by the schema check; an object-shaped but malformed one that
differs from the envelope's (always the case when the envelope's is valid) is
reported by both, and the mismatch diagnostic is the one that names the event.
A file that merges producers should be split into one file per producer.

## What the ordering validator can and cannot prove

Per mission id, the validator proves **local sequence consistency of the
supplied stream**: unique contiguous sequence numbers starting at 1,
non-decreasing timestamps, dependency events present with lower sequence
numbers, and paired transitions (completion requires initiation, acceptance
requires request, grant requires request, tool invocation requires a prior
allowance). It rejects duplicates and content replays.

`sequence` and `occurrence.attempt` are JSON Schema integers, and JSON Schema
also accepts a whole-number float such as `2.0` there. Every check above treats
such a value as the integer it equals, so `2.0` gets the verdict of `2`.
Values the schema rejects are not converted: booleans, fractions, non-finite
numbers, and numbers outside 1 to 1,000,000 still fail as schema-invalid.
`EvidenceRecorder.resume(...)` stores an accepted whole-number float in a
prior stream as that integer.

Per-event `evidence_artifact.path` values resolve relative to the events
file's own directory and must stay inside it; escapes, symlinks, and hash
mismatches fail closed.

It does **not** solve distributed causality, cannot prove events across
systems happened in the claimed order, and never claims complete causal
truth. A runtime can omit or fabricate events; validation proves conformance
of what was supplied against the exact contract revision, nothing more. Hash
validity (including per-event `evidence_artifact` SHA-256 binding) proves
content binding, not event truth. These limitations are embedded in every
report. Event timestamps are producer-asserted; see "Recording and
continuation" below.

## Runtime-events 1.1 occurrence modes

The schema id remains `nornyx.agentic_runtime_events.v1`. The lock selects an
exact schema version:

- **1.0** is the published Nornyx 1.9.0 shape. 1.0 streams are validated as in
  1.9.0 plus later version-independent consistency rules
  (`AN_EVT_PRODUCER_MISMATCH`).
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
remain available and retain legacy behavior on legacy recorders. An explicit
recorder refuses the legacy `record_decision(...)` and
`record_observation(...)` calls with `ValueError` before recording anything,
because an explicit stream cannot mix modes.

The recorder stamps each event's `event_id`, `event_type`, `mission_id`,
`sequence`, `timestamp`, `producer`, network id, digests, and subject revision.
Decision-intent or observation fields that name one of those keys, or name
`occurrence`, are refused with `ValueError` before anything is recorded
(`None`-valued fields are dropped, as for any field); only the occurrence
methods attach an occurrence. This is a recorder guarantee, not a validation
one: the validator compares a per-event `producer` only with the file's own
envelope `producer` (see "Every event binds") and does not compare
`timestamp` or `event_id` with any recorder, so a hand-built stream can name
any producer consistently and carry timestamps and event ids that no recorder
stamped. `resume(...)` refuses a prior stream whose events name a different
`producer` or carry a timestamp that is unparseable or later than the new
`decision_at`; it does not otherwise compare their `timestamp` or `event_id`
with the recorder.

Nornyx 1.11.0 tolerated a stamped key among the fields and let it silently
replace the stamped value. That was never a documented use, and since #108 it
raises even when the value matches what the recorder would stamp (see
`docs/VERSIONING.md` rule 7, Nornyx-owned fields). To migrate, remove the
argument; the recorded event is unchanged. Do not rename it instead: an
unknown field fails the closed event schema (`AN_EVT_SCHEMA_INVALID`).

```python
# Before: accepted by 1.11.0, now raises ValueError
recorder.record_observation(
    "tool_invoked",
    mission_id="GOAL-001",
    actor_ref="identity.researcher.local",
    capability_ref="read_governed_context",
    subject_revision=authorizer.subject_revision,
)

# After: the recorder stamps subject_revision itself
recorder.record_observation(
    "tool_invoked",
    mission_id="GOAL-001",
    actor_ref="identity.researcher.local",
    capability_ref="read_governed_context",
)
```

Event timestamps are producer-asserted. The validator evaluates identity,
membership, and delegation validity windows, and revocation `effective_at`
times, against each event's own `timestamp`. The only cross-event timing rule
it enforces is that timestamps do not decrease along a mission's sequence (the
schema separately requires each `timestamp` to be shaped like an RFC 3339
date-time with an offset), and it never compares them with the time of validation. Nornyx
cannot establish whether a timestamp reflects when the event actually
happened. A hand-built or `external_runtime` stream that dates an event inside
a delegation's validity window validates `pass` (structural conformance only)
even if the work happened after the delegation's `expires_at`, and likewise
for an event dated before a revocation's `effective_at`. The recorder stamps
every event it builds, including post-action observations, with the bound
context's `decision_at`. That value is supplied by whoever constructs the
`EvaluationContext`, not read from a clock, and per-call fields cannot
override it. A recorder-built stream therefore carries the supplied decision
time, not an observed execution time. For any other stream, a window verdict
is only as trustworthy as the producer's own timestamps.

`EvidenceRecorder.resume(...)` validates and deeply copies a complete prior
stream, restores mission sequence and occurrence-attempt state, and continues
to return cumulative evidence. The producer, contract, lock, schema/mode, and
subject revision must match, and the resumed evaluation time cannot precede
any recorded event. Differential chunks and multi-producer merging are not
supported.
