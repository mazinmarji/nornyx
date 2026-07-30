# ADR-0041 — EvidenceRecorder Integrity and Serialization

- Status: Accepted (design + implementation; execution is a separate,
  owner-authorized milestone)
- Date: 2026-07-26
- Decision owner: human repository owner
- Relates to: ADR-0036 (agentic runtime event evidence), ADR-0037 (reference
  adapters — cooperative enforcement boundary), ADR-0039 (agentic integration
  SDK, frozen `EvidenceRecorder` construction/consistency-binding contract),
  ADR-0040 (governance assurance tiers)

## Context

`EvidenceRecorder` (`nornyx/agentic/authz.py`) turns decision-event intents
(from the trusted `Authorizer`) and adapter-supplied post-action observations
into a schema-valid `nornyx.agentic_runtime_events.v1` stream. Two classes of
caller-controlled input reach it directly:

1. **Adapter-supplied scalars and field values** — `mission_id`, `event_type`,
   `producer_id`, `producer_version`, `producer_type`,
   `EvaluationContext.decision_at`,
   `EvaluationContext.observed_subject_revision`, and the `**fields` passed to
   `record_observation`. Adapters are third-party, framework-specific code
   (ADR-0037); their inputs are untrusted by construction.
2. **Directly-constructed `Decision`/`DecisionEventIntent` objects** — nothing
   in the public API prevents a caller from building these dataclasses by hand
   and passing them to `record_decision`, bypassing the `Authorizer` entirely.
   `DecisionEventIntent.fields` is typed as `Mapping[str, Any]`, which is not
   runtime-enforced.

Prior to this ADR, none of these inputs were type-validated before use.
`mission_id` was used directly as a dictionary key
(`self._sequences[mission_id]`) and interpolated into `event_id`; unknown
`event_type`/`producer_type` values were reported via `!r` (which calls
`repr()`) without first confirming the value was a genuine `str`. A caller —
or a compromised/misbehaving adapter — could pass a `str` subclass (or a
non-`str` mapping key) whose `__hash__`, `__eq__`, `__format__`, `__str__`, or
`__repr__` runs attacker-controlled code the moment the recorder touches it.
Because `EvidenceRecorder` was not internally synchronized, this risk also
extended to lost updates and duplicate sequence numbers if a single instance
were ever shared across threads — a real deployment shape once an adapter runs
concurrent tool invocations.

## Decision

`EvidenceRecorder` becomes internally locked and validates every
caller-controlled scalar and field value **before** it can influence recorder
state. Supported builtin subclasses are immediately canonicalized to exact
plain builtins through explicitly invoked base-type operations that do not
dispatch to subclass overrides. Only canonical exact values enter recorder
state.

### 1. Callback-safe scalar canonicalization

`mission_id`, `event_type`, `producer_id`, `producer_version`, `producer_type`,
`EvaluationContext.decision_at`, and
`EvaluationContext.observed_subject_revision` accept exact `str` values and
`str` subclasses, matching their published annotations. Exact strings pass
through unchanged. A subclass is
converted with the explicitly invoked base operation `str.__str__(value)`,
and the result must have `type(result) is str`. The recorder does not call
`str(value)`, `value.__str__()`, `repr`, `format`, `hash`, or equality on the
source value. Non-string input raises a static `TypeError` that does not render
the caller value. Value-domain errors may include the already-canonical exact
string (for example, an unrecognized `producer_type`), which cannot dispatch
to a caller override.

- `producer_id`/`producer_version`/`producer_type` are validated in
  `EvidenceRecorder.__init__`, before the producer mapping is stored.
- Both `EvaluationContext` strings are canonicalized during recorder
  construction before revision comparison or storage. The recorder constructs
  and retains a fresh `EvaluationContext` containing exact builtin strings; it
  does not retain the caller-provided context object. Hostile equality and
  inequality overrides therefore cannot execute during revision binding, and
  internal and emitted timestamps contain exact builtin strings.
- `mission_id` and `event_type` are validated in `record_decision` and
  `record_observation`, before the internal lock is acquired and before
  `mission_id` is ever used as a dictionary key.

### 2. Intent fields and Mapping callback boundary

`record_decision` materializes each intent's field mapping outside the lock,
canonicalizes each string or string-subclass key to exact `str`, and detaches
every non-`None` value through the restricted canonicalizer (below) — all
before any recorder mutation for that decision. Two distinct source keys that
canonicalize to the same exact string fail closed rather than silently
overwriting one another. A malformed mapping, or any single malformed key,
anywhere in a decision's intents aborts the whole call: nothing already
validated is partially committed.

For an exact `dict` or `dict` subclass, the recorder invokes
`dict.items(value)` and never a caller override. `DecisionEventIntent.fields`
is publicly annotated `Mapping[str, Any]`, so another `Mapping`
implementation remains an intentional callback boundary: consuming it cannot
be callback-free. Its mapping interface is invoked once outside the lock to
produce a detached snapshot. The source mapping is never retained or
revisited, every yielded key/value is canonicalized before mutation, and an
exception from the mapping leaves recorder state unchanged.

Python itself may hash or validate keys while expanding `**fields` before
`record_observation` is entered. Those language-level callbacks precede the
recorder boundary and cannot be prevented by `EvidenceRecorder`; once inside
the method, canonicalization follows the callback-safe rules above.

### 3. `_stamp` compatibility (record_observation vs. record_decision)

- `record_observation` validates `event_type` and `mission_id`, then delegates
  to the private `_stamp` method, which detaches fields (via the restricted
  copier) outside the lock and performs one atomic build/append/counter-update
  inside the lock.
- `record_decision` does **not** call `_stamp`. A decision's intents commit as
  one transactional batch under a single lock acquisition — a guarantee
  `_stamp`'s single-event locking cannot provide, and one that must hold for
  every intent in the decision together, not each independently.
- Consequence: a private subclass overriding `_stamp` continues to observe
  every call on the `record_observation` path, but no longer intercepts
  decision-intent commits. `_stamp` remains private; this ADR does not make it
  part of the public surface.

### 4. Restricted builtin canonicalizer (`_detach_plain`)

Field values are copied through a recursive builtin canonicalizer before they
can enter recorder state. The permitted set is: `None`; `bool`; `int`; finite
`float` (`NaN`/`Infinity` are rejected — the runtime-events schema is JSON,
which cannot represent them); `str`; `dict` with string keys; `list`; and
`tuple`, **normalized to exact `list`** in the copy (JSON has no separate tuple
concept, so both sequence literals collapse to the one array shape the schema
actually validates). Exact values pass through or are rebuilt with exact
containers. Supported subclasses are read only through unbound base
operations: `str.__str__`, `int.__int__`, `float.__float__`, `dict.items`,
`list.__iter__`, and `tuple.__iter__`. Each scalar result is defensively
required to have the exact expected builtin type; every container is rebuilt,
recursively, as an exact `dict` or `list`.

`set`/`frozenset` are **rejected outright, never normalized** — silently
choosing an iteration order for an unordered collection would be a silent
behavior decision this recorder does not make on the caller's behalf.
Arbitrary unsupported objects are rejected with a `TypeError` naming the
allowed-type contract, never the rejected value. The recorder never invokes
builtin-subclass overrides such as `items`, `keys`, `__iter__`, `__getitem__`,
`__reduce__`, `__reduce_ex__`, `__getstate__`, or `__deepcopy__`. Recursion is
bounded by a depth limit of 8; a self-referential container fails closed with
`ValueError` once the limit is exceeded, rather than recursing without bound.

### 5. Locking

`EvidenceRecorder` holds a `threading.Lock`. The lock protects only the
mutation of `self._events` and `self._sequences`; all validation and
detachment of caller-controlled input happens before acquisition, so the
locked section only ever touches already-verified, plain builtin values —
never a caller-controlled callback.

### 6. Deep, independent snapshots on read (`stream()` / `validate()`)

`stream()` acquires the lock, builds a fully independent deep copy of the
producer metadata and every recorded event — each event's fields detached
individually, `{k: _detach_plain(v) for k, v in event.items()}`, not the whole
event dict passed through `_detach_plain` as one unit (an event is the
recorder's own envelope, not itself a caller-supplied nested value; detaching
it as one unit would silently consume one extra level of the depth budget for
every field, so a field value accepted at record time right at the depth
limit could spuriously fail on read) — and releases the lock before
returning. `validate()` calls `stream()` to build the payload and only then
calls `validate_runtime_events`, so that call never runs while the lock is
held. Mutating any part of a returned stream — a nested `approver`,
`evidence_artifact`, `share_categories`, `depends_on`, or `producer` value,
top-level or per-event — can never change what a later call to `stream()` or
`validate()` returns, and can never corrupt the recorder's internal state.

## Consequences

- `EvidenceRecorder` is now safe for concurrent use by multiple threads
  sharing one instance: sequence numbers are assigned without loss or
  duplication, a decision's intents commit as an indivisible batch, and a
  `stream()` snapshot taken mid-write is always internally consistent (never
  a torn view).
- A hostile or buggy adapter cannot use a crafted supported builtin subclass,
  a non-string mapping key, or an unsupported field-value type to execute a
  subclass override during recorder canonicalization, corrupt recorder state,
  or partially commit a malformed decision. A general non-`dict` Mapping is
  the documented callback boundary and is consumed only outside the lock and
  before mutation.
- A caller holding a returned `stream()` payload — or the original container
  it passed in as a field value — cannot corrupt recorder state or a later
  read by mutating either one after the fact; each is an independent copy.
- Well-formed exact-plain callers observe byte-identical event output.
  Annotation-compatible builtin-subclass callers also retain their underlying
  schema-valid values, but the emitted and stored types are exact builtins;
  tuple and tuple-subclass field values emit as lists, matching the runtime
  schema's array representation.
- This ADR does not change `SPI_VERSION`, the runtime-events schema (still
  v1/1.0), `AN_EVT_REPLAY` semantics, or any adapter-observable public
  signature or export.

## Non-goals

- No change to occurrence semantics, the runtime-event schema, or
  `nornyx.agentic`'s public exports beyond what `EvidenceRecorder` already
  exposed.
- No ADR-0041 Part B or M2-C (LangGraph) work.
- No package-version changes.

## Revision note (compatibility remediation before release)

The independent release-candidate audit found that the first exact-type
implementation rejected subclasses that satisfied the published builtin-type
annotations and had previously produced schema-valid evidence. Before the
1.9.0 release, that rejection was corrected to the callback-safe base-operation
canonicalization specified above. The remediation restores those supported
inputs without retaining caller objects, executing their overrides, changing
event content for exact-plain callers, or weakening the lock, transaction,
depth, serialization, and fail-closed guarantees. No compatibility mode,
deprecation cycle, public signature/export change, SPI bump, or schema change
is required.

## Revision note (independent-audit correction pass)

An initial implementation pass of this ADR was staged with four defects, found
and fixed before independent audit:

1. The restricted copier normalized `set`/`frozenset` to `frozenset` instead
   of rejecting them, normalized `tuple` to `tuple` instead of `list`, did not
   reject non-finite `float`, and used a depth limit of 20 instead of the
   approved 8.
2. `stream()` performed only a shallow, top-level `dict(event)` copy: a caller
   mutating a nested value in a returned stream (e.g. a returned `approver`
   dict) mutated the recorder's own internal event storage, corrupting all
   subsequent `stream()`/`validate()` results.
3. The initial fix for (2) detached each whole event dict as one unit, which
   silently added one extra level to every field's depth budget and could
   cause `stream()` to raise on a field value that had been accepted — and
   already recorded — at write time. Fixed by detaching each field
   individually, reproducing the exact budget used at record time.
4. Both `_stamp` and `record_decision`'s locked commit loop wrote to
   `self._sequences[mission_id]` *before* building the corresponding event
   (`self._build_event_unlocked`, renamed from `_build_event` to make its
   locking contract explicit). If the build step itself raised — not a
   validation/detachment failure, which already raises before the lock is
   acquired — the sequence counter was left advanced with no corresponding
   event appended, and for a multi-intent `record_decision` batch, an earlier
   intent in the same batch could already have been appended before a later
   one failed, violating the batch's claimed all-or-nothing atomicity. Fixed
   by building every event in a batch into a local list first and writing to
   `self._sequences`/`self._events` only after every build in the batch has
   succeeded; `_stamp` was fixed the same way for its single event.
