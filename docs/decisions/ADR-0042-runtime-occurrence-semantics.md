# ADR-0042 — Framework-neutral runtime occurrence semantics

- Status: Accepted (implementation candidate; release remains owner-controlled)
- Date: 2026-07-30
- Decision owner: human repository owner
- Relates to: ADR-0036, ADR-0039, ADR-0040, ADR-0041

## Context

Runtime-events schema 1.0 identifies a mission and a mission-local sequence,
but it cannot identify repeated execution inside that mission. The validator
therefore treats authorization state as mission-wide and fingerprints repeated
events without an execution identity. This makes a legitimate loop visit,
framework retry, parallel node execution, or resumed node indistinguishable
from replay. The CrewAI benchmark exposed this as finding O2 and worked around
it by minting a mission for each invocation, losing whole-run mission meaning.

The model must remain framework-neutral. LangGraph 1.2.2 is an important
consumer because its public `Runtime.execution_info` exposes stable task and
attempt metadata, but no LangGraph type or identifier is part of the core
contract.

## Decision

### Vocabulary and scope

- A **mission** is the complete governed run or business goal. It owns network
  bindings, event-id uniqueness, contiguous serialization sequence, timestamp
  order, and dependency edges. It remains stable across retries and resume.
- A **logical operation** is the stable governed surface that may execute more
  than once, such as a node or tool binding. It owns the registry of its
  occurrences but shares no authorization allowance between them.
- An **occurrence** is one scheduled execution, loop visit, or parallel branch
  instance. Its identifier is immutable within a mission and maps to exactly
  one logical operation.
- An **attempt** is a one-based, contiguous try within one occurrence. Requests,
  decisions, allowances, approvals, delegation/handoff transitions, and
  terminal outcome are attempt-scoped.

The same operation with a new occurrence and attempt 1 is legitimate
repetition. The same occurrence with the next attempt after failure, denial,
rejection, or an incomplete/interrupted prefix is retry. A successful terminal
observation closes the occurrence; further work requires a new occurrence.

Mission sequence is recorder serialization order, not a claim that parallel
work executed serially. `depends_on` remains the explicit, backward-pointing
causal relation.

### Runtime-events schema

The permanent schema id remains `nornyx.agentic_runtime_events.v1`. Schema
version 1.1 has two exact modes:

- `occurrence_mode: legacy` preserves 1.0 event shape and validation semantics.
- `occurrence_mode: explicit` requires every event to contain a closed
  `occurrence` object with `operation_id`, `occurrence_id`, and integer
  `attempt`.

Schema 1.0 remains an exact validation branch and does not admit
`occurrence_mode` or occurrence fields. A stream cannot mix modes. Operation
and occurrence identifiers allow common trace/task punctuation, including
hyphen and slash, without loosening any existing 1.0 identifier field.

No event types are added. Successful terminal observations are
`agent_invoked`, `tool_invoked`, `handoff_completed`, `trust_zone_crossed`,
`data_shared`, and `identity_revoked`. Failure outcomes include explicit deny
or rejection events, `policy_violation`, and `runtime_failed`. An incomplete
attempt is a valid resumable prefix.

### Replay and transition validation

Legacy replay behavior is unchanged. In explicit mode a replay fingerprint
contains every substantive field, including occurrence and dependency data,
but excludes the transport-only `event_id`, `sequence`, and `timestamp`.
Restamping the same semantic evidence within an attempt is therefore replay;
the same evidence in another occurrence or attempt is not.

Occurrence ids cannot move between operations, attempts cannot decrease or
contain gaps, and an attempt after successful completion fails validation.
All decision and transition state is keyed by operation, occurrence, and
attempt, preventing an earlier allowance from authorizing a retry or loop
visit.

These checks remain cooperative Tier 2. A producer may falsely claim a new
occurrence just as it may falsely claim a mission today; validation proves the
structure and binding of supplied evidence, not runtime truth.

### Recorder and SPI

SPI major remains 1 and `SPI_VERSION` advances to `1.1`. The existing
`EvidenceRecorder` constructor and `record_decision`, `record_observation`,
`stream`, and `validate` call forms remain unchanged.

The additive surface is:

- frozen `RuntimeOccurrence`;
- `EvidenceRecorder.for_occurrences(...)`;
- `record_occurrence_decision(...)`;
- `record_occurrence_observation(...)`;
- `max_recorded_attempt(...)`;
- `EvidenceRecorder.resume(...)`.

Legacy construction follows the runtime schema version declared by its lock:
1.0 locks emit 1.0 streams; 1.1 locks emit 1.1 legacy streams. Explicit
recording requires a 1.1 lock and never infers identity from call order.

### Continuation

`EvidenceRecorder.resume` accepts one cumulative prior stream. It validates
the complete prefix against the exact contract and lock before mutation,
requires the same producer, schema version, and mode, rejects clock regression,
deeply detaches the prefix, and restores mission sequence state. It always
returns cumulative evidence. A legacy stream cannot be upgraded in place.

Suffix-only streams, branch merging, cross-producer continuation, storage
protocols, and cryptographic segment chains are outside this decision.

### Locks and compatibility

New locks default to runtime-events 1.1. Lock format stays 1.0 and the runtime
schema id stays v1. Verification reconstructs generated artifacts with the
runtime schema version declared by a supported historical lock, so 1.0 locks
and their artifact hashes remain valid. Evidence schema id/version must equal
the value in the validated lock.

### Core and adapter boundary

Core owns vocabulary, schema, replay rules, state validation, recorder APIs,
continuation, and historical compatibility. Adapters own the mapping from
public framework execution metadata, control-flow exception classification,
and supported framework versions.

For LangGraph 1.2.2, a governed surface is the operation, public `task_id` is
the occurrence, and public `node_attempt` is the native attempt. Because
`node_attempt` restarts at one after checkpoint resume, the adapter offsets it
using the maximum attempt in the validated recorder prefix. Interrupt control
flow is an incomplete attempt, not `runtime_failed`.

## Rejected alternatives

- Runtime-events v2: unnecessary because no 1.0 meaning is rewritten.
- Mission-per-invocation: loses mission-wide evidence and dependency meaning.
- Implicit occurrence inference: ambiguous across frameworks and unsafe under
  concurrency or process restart.
- Framework fields in core: violates ADR-0039 and would couple evidence to one
  executor.
- Multi-producer/chunk merge in this milestone: substantially larger integrity
  and ordering protocol than M2-C requires.

## Consequences and non-goals

Occurrence-aware callers must opt in and supply truthful metadata. Existing
callers continue unchanged with legacy semantics. This ADR does not add a
general-purpose runtime, execute framework actions, attest event truth, change
CrewAI hooks, support async LangGraph execution, or authorize releases.

The required corpus covers 1.0 locks/streams, 1.1 legacy/explicit shape,
repetition, retry, replay, parallel interleaving, attempt-state isolation,
incomplete continuation, tamper/producer/clock rejection, and native LangGraph
retry, loop, parallel, interrupt, and resume behavior.
