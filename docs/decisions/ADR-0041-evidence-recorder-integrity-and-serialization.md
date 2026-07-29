# ADR-0041 — EvidenceRecorder Integrity and Serialization

- Status: Proposed (design + implementation; execution is a separate,
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
   `producer_id`, `producer_version`, `producer_type`, and the `**fields`
   passed to `record_observation`. Adapters are third-party, framework-specific
   code (ADR-0037); their inputs are untrusted by construction.
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
state, using exact-type checks that never invoke a caller-defined method.

### 1. Exact-type scalar validation

`mission_id`, `event_type`, `producer_id`, `producer_version`, and
`producer_type` must satisfy `type(value) is str` — not `isinstance`, which
would admit subclasses. The check is a plain object-header comparison; it
never calls `__hash__`, `__eq__`, `__format__`, `__str__`, `__repr__`, or any
other method on the rejected value. Violations raise `TypeError` (wrong type)
or `ValueError` (right type, disallowed value — e.g. an unrecognized
`producer_type`). Type-rejection errors do not interpolate or expose the
rejected value. Value-domain errors may include an already validated exact
builtin string (e.g. the unrecognized `producer_type` itself) — safe because
by that point the value's exact type has already been confirmed, so `!r` on
it invokes only `str`'s own, non-overridable `__repr__`.

- `producer_id`/`producer_version`/`producer_type` are validated in
  `EvidenceRecorder.__init__`, before the producer mapping is stored.
- `mission_id` and `event_type` are validated in `record_decision` and
  `record_observation`, before the internal lock is acquired and before
  `mission_id` is ever used as a dictionary key.

### 2. Intent field keys

`record_decision` materializes each intent's field mapping outside the lock,
requires every key to satisfy `type(key) is str`, and detaches every non-`None`
value through the restricted copier (below) — all before any recorder mutation
for that decision. A malformed mapping, or any single malformed key, anywhere
in a decision's intents aborts the whole call: nothing already validated is
partially committed.

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

### 4. Restricted exact-type copier (`_detach_plain`)

Field values are copied through a recursive, exact-type-only copier before
they can enter recorder state. The permitted set is exactly: `None`; exact
`bool`; exact `int`; exact, finite `float` (`NaN`/`Infinity` are rejected —
the runtime-events schema is JSON, which cannot represent them); exact `str`;
exact `dict` with exact `str` keys; exact `list`; exact `tuple`, **normalized
to `list`** in the copy (JSON has no separate tuple concept, so both sequence
literals collapse to the one array shape the schema actually validates).
`set`/`frozenset` are **rejected outright, never normalized** — silently
choosing an iteration order for an unordered collection would be a silent
behavior decision this recorder does not make on the caller's behalf.
Everything else — including subclasses of any accepted type, which could
override `__iter__`, `keys`, `__deepcopy__`, `__reduce__`, `__reduce_ex__`,
`__getstate__`, or `__hash__`/`__eq__` (as a dict key) — is rejected with a
`TypeError` naming the allowed-type contract, never the rejected value. This
error does **not** include a structural field path (e.g. `payload.items[2]`)
— the implementation does not thread one through the recursive calls; only
the generic allowed-type contract is reported. Recursion is bounded by a depth
limit of 8; a self-referential container fails closed with `ValueError` once
the limit is exceeded, rather than recursing without bound.

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
- A hostile or buggy adapter cannot use a crafted `str` subclass, a
  non-`str` mapping key, or an unsupported field-value type to execute
  code inside the recorder, corrupt recorder state, or partially commit a
  malformed decision.
- A caller holding a returned `stream()` payload — or the original container
  it passed in as a field value — cannot corrupt recorder state or a later
  read by mutating either one after the fact; each is an independent copy.
- Well-formed single-threaded callers observe byte-identical event output:
  the validation and detachment steps are no-ops in content for inputs that
  were already builtin `str` scalars and plain `dict`/`str`/`int`/`float`/
  `bool`/`None` field values — the only inputs any existing adapter, test, or
  example in this repository ever supplies. (A caller passing a `tuple` field
  value would now see it returned as a `list`; no such caller exists today.)
- This ADR does not change `SPI_VERSION`, the runtime-events schema (still
  v1/1.0), `AN_EVT_REPLAY` semantics, or any adapter-observable public
  surface beyond stricter (fail-closed) input validation on
  `EvidenceRecorder`.

## Non-goals

- No change to occurrence semantics, the runtime-event schema, or
  `nornyx.agentic`'s public exports beyond what `EvidenceRecorder` already
  exposed.
- No M2-C (LangGraph) work.
- No package-version changes.

## Revision note (independent-audit correction pass)

An initial implementation pass of this ADR shipped with four defects, found
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
