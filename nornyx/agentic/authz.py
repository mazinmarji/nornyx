"""Framework-neutral core authorization engine for ``nornyx.agentic``.

Implements the SPI frozen by ADR-0039: a loaded, deeply-immutable, lock-verified
``Authorizer`` that evaluates discriminated authorization requests against Nornyx
contract semantics and returns typed ``Decision`` objects carrying *decision-event
intents only*. A separate ``EvidenceRecorder`` turns those intents (and
adapter-supplied post-action observations) into a schema-valid
``nornyx.agentic_runtime_events.v1`` stream bound to the contract, lock, and the
already-verified observed subject revision.

Boundaries (ADR-0039 / ADR-0040 Tier 2, cooperative):

- The engine authorizes *declared Nornyx concepts only*. It never parses raw
  shell commands, file paths, URLs, or tool arguments.
- It imports no agent framework, executes no tool, authenticates no approver,
  grants no approval, and asserts no runtime-event truth.
- It reads no wall-clock time. ``validation_as_of`` governs load-time document
  validation; ``EvaluationContext.decision_at`` governs *all* temporal action
  semantics (identity/membership/delegation/handoff/approval/revocation validity).
- The ``Authorizer`` is *deeply immutable*: its retained document, composition,
  lock, and all derived indexes are recursively frozen (mappings→read-only,
  lists/tuples→immutable sequences, sets→frozensets), detached from the
  caller's inputs. It is synchronous, deterministic, reusable, and safe for
  concurrent evaluation; per-mission sequencing state lives only in the
  ``EvidenceRecorder``.
"""

from __future__ import annotations

import math
import re
import threading
from collections.abc import Mapping as _AbcMapping
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ..agentic_artifacts import (
    RUNTIME_EVENTS_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_VERSION,
    agentic_network_lock_digest,
    contract_digest,
    load_agentic_network_lock,
    verify_agentic_network_lock,
)
from ..checker import check_document, has_errors
from ..governance import (
    CompositionResult,
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
)
from ..governance.agentic_network import (
    EXTERNAL_ZONE_CLASSIFICATIONS,
    SENSITIVE_CATEGORIES,
    _parse_duration,
    _parse_time,
    _revocation_target_key,
)
from ..parser import load_nyx

SPI_VERSION = "1.2"

# Canonical subject-revision syntax (ADR-0039): git 40/64 lowercase hex, or
# sha256 64 lowercase hex. No branch names, abbreviated SHAs, or aliases.
_REVISION_RE = re.compile(r"^(?:git:[0-9a-f]{40}|git:[0-9a-f]{64}|sha256:[0-9a-f]{64})$")
_RUNTIME_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")

# Runtime-event producer types permitted by nornyx.agentic_runtime_events.v1.
_PRODUCER_TYPES = frozenset({"framework_adapter", "synthetic_harness", "external_runtime"})


def _valid_revision(value: Any) -> bool:
    return isinstance(value, str) and bool(_REVISION_RE.match(value))


def _all_str(value: Any) -> bool:
    return isinstance(value, tuple) and all(isinstance(item, str) for item in value)


# Tuple-aware readers (the frozen snapshot uses tuples, not lists).
def _map_items(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _str_items(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


# --------------------------------------------------------- frozen retained containers
# The retained snapshot must be read-only *and* keep every public governance
# model (``CompositionResult`` and everything reachable from it) serializable.
# ``MappingProxyType`` satisfies only the first: ``copy.deepcopy`` pickles it and
# fails, and the governance serializers are built on ``deepcopy(dict(...))``. A
# frozen model wrapped in mappingproxy would therefore raise ``TypeError`` from
# its own ``to_dict``. These two containers are equally read-only but restore the
# exact container the source carried under ``copy.deepcopy`` — dict for a
# mapping, list for a list — so a frozen model serializes identically to the
# unfrozen model it was built from.
class _FrozenMap(_AbcMapping):
    """Read-only mapping that deep-copies back to an ordinary ``dict``."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_data", MappingProxyType(dict(data)))

    def __getitem__(self, key: Any) -> Any:
        return self._data[key]

    def __iter__(self) -> Any:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._data)!r})"

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("frozen mapping is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("frozen mapping is immutable")

    def __copy__(self) -> dict[Any, Any]:
        return dict(self._data)

    def __deepcopy__(self, memo: dict[int, Any]) -> dict[Any, Any]:
        copied: dict[Any, Any] = {}
        memo[id(self)] = copied
        for key, item in self._data.items():
            copied[deepcopy(key, memo)] = deepcopy(item, memo)
        return copied


class _FrozenList(tuple):
    """Immutable sequence that deep-copies back to an ordinary ``list``.

    Subclassing ``tuple`` keeps every tuple-aware reader in this module working
    unchanged while recording that the frozen value was a list, so detachment
    and ``copy.deepcopy`` can restore a list rather than a tuple.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({list(self)!r})"

    def __copy__(self) -> list[Any]:
        return list(self)

    def __deepcopy__(self, memo: dict[int, Any]) -> list[Any]:
        copied: list[Any] = []
        memo[id(self)] = copied
        copied.extend(deepcopy(item, memo) for item in tuple.__iter__(self))
        return copied


def _rebuild_dataclass(value: Any, transform: Any) -> Any:
    """Rebuild one dataclass instance field-by-field under an explicit contract.

    Field-by-field reconstruction is sound only for ordinary keyword-
    constructible dataclasses: every declared field must also be an ``__init__``
    parameter, and the constructor must accept the values the instance already
    holds. Every dataclass reachable from a :class:`CompositionResult` satisfies
    this, and ``tests/test_agentic_authorizer_state.py`` pins that closed set. A
    shape outside the contract fails deliberately here — naming the class — in
    preference to silently producing a partially-populated governance model.
    """
    cls = type(value)
    spec = fields(value)
    non_init = tuple(item.name for item in spec if not item.init)
    if non_init:
        raise TypeError(
            f"{cls.__name__} declares non-constructor field(s) "
            f"{', '.join(non_init)}; the Authorizer only retains "
            "keyword-constructible dataclasses."
        )
    rebuilt = {item.name: transform(getattr(value, item.name)) for item in spec}
    try:
        return cls(**rebuilt)
    except Exception as exc:  # noqa: BLE001 - deliberate shape rejection
        raise TypeError(
            f"{cls.__name__} cannot be rebuilt from its own declared fields; "
            "the Authorizer only retains keyword-constructible dataclasses."
        ) from exc


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze dataclasses and their complete retained object graph.

    Container copies are new, so the result shares no mutable reference with the
    input; scalars are shared but immutable. Freezing is idempotent, and the
    source container kind (mapping / list / tuple / set) is preserved so the
    snapshot can be detached back into exactly what was frozen.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return _rebuild_dataclass(value, _deep_freeze)
    if isinstance(value, Mapping):
        return _FrozenMap({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, (list, _FrozenList)):
        return _FrozenList(_deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    """Detached ordinary-container copy of a frozen snapshot (for validators)."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


def _detach_composition(value: Any) -> Any:
    """Copy a frozen governance model back into its original container kinds.

    Dataclasses are rebuilt, mappings become ordinary ``dict`` objects, values
    frozen from lists become lists again, declared tuple fields stay tuples, and
    frozensets stay frozensets rather than degrading to mutable sets. The result
    shares no container with the frozen snapshot, so mutating it cannot reach the
    Authorizer, and it satisfies every public :class:`CompositionResult`
    serializer contract.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return _rebuild_dataclass(value, _detach_composition)
    if isinstance(value, Mapping):
        return {key: _detach_composition(item) for key, item in value.items()}
    if isinstance(value, _FrozenList):
        return [_detach_composition(item) for item in tuple.__iter__(value)]
    if isinstance(value, tuple):
        return tuple(_detach_composition(item) for item in value)
    if isinstance(value, list):
        return [_detach_composition(item) for item in value]
    if isinstance(value, frozenset):
        return frozenset(_detach_composition(item) for item in value)
    if isinstance(value, set):
        return {_detach_composition(item) for item in value}
    return value


# ---------------------------------------------------- restricted builtin canonicalizer
# Evidence-recorder callers (adapters, and any caller constructing Decision /
# DecisionEventIntent objects directly) are untrusted. ADR-0041: field values
# and keys admitted into recorded evidence must become exact plain builtins
# before lock acquisition or state use. Supported builtin subclasses are read
# only through explicitly invoked base-type operations such as
# ``str.__str__(value)`` and ``list.__iter__(value)``. These bypass subclass
# overrides while preserving the underlying builtin value. Type-rejection
# errors never interpolate or expose caller input.
#
# The permitted set is: None; bool; int; finite float; str; dict with str keys;
# list; and tuple (normalized to list because the runtime-events schema has no
# separate tuple concept). Exact values and subclasses are accepted, but
# subclasses are never retained. set/frozenset remain rejected rather than
# receiving an arbitrary ordering.
_DETACH_PLAIN_MAX_DEPTH = 8


def _canonical_str(value: Any, field: str) -> str:
    """Return an exact builtin ``str`` without invoking subclass overrides.

    ``field`` is an internal static label. Rejection messages never render the
    caller value. The unbound base implementation bypasses overridden string,
    representation, formatting, hash, and equality methods.
    """
    if type(value) is str:
        return value
    if isinstance(value, str):
        canonical = str.__str__(value)
        if type(canonical) is str:
            return canonical
        raise TypeError(f"{field} could not be canonicalized to built-in str.")
    raise TypeError(f"{field} must be built-in str or a str subclass.")


def _detach_plain(value: Any, *, _depth: int = 0) -> Any:
    """Canonicalize a supported evidence value to exact plain builtins.

    Supported builtin subclasses are consumed only through unbound base-type
    operations. Tuple values normalize to exact lists. Mapping keys must be
    strings; string subclasses become exact strings, and canonical-key
    collisions fail closed instead of silently overwriting one source entry.
    Unsupported objects, unordered collections, non-finite floats, excessive
    nesting, and self-reference remain rejected without rendering caller data.

    This function serves two roles: (1) validating and detaching untrusted
    caller-supplied field values at record time (where rejection is a real,
    reachable outcome), and (2) producing an independent deep copy of
    already-recorded — and therefore already guaranteed-plain — recorder-owned
    data at read time (:meth:`EvidenceRecorder.stream`), where every branch
    below either matches or the data could never have been recorded in the
    first place.
    """
    if _depth > _DETACH_PLAIN_MAX_DEPTH:
        raise ValueError(f"evidence value exceeds the maximum nesting depth ({_DETACH_PLAIN_MAX_DEPTH}).")
    if value is None:
        return None
    kind = type(value)
    if kind is bool or kind is str or kind is int:
        return value
    if kind is float:
        if not math.isfinite(value):
            raise ValueError("evidence float values must be finite (NaN/Infinity are rejected).")
        return value
    if isinstance(value, str):
        canonical = str.__str__(value)
        if type(canonical) is not str:
            raise TypeError("evidence str subclass did not canonicalize to exact built-in str.")
        return canonical
    # Exact bool was handled above. ``bool`` cannot be subclassed, so it can
    # never reach this integer-subclass branch.
    if isinstance(value, int):
        canonical = int.__int__(value)
        if type(canonical) is not int:
            raise TypeError("evidence int subclass did not canonicalize to exact built-in int.")
        return canonical
    if isinstance(value, float):
        canonical = float.__float__(value)
        if type(canonical) is not float:
            raise TypeError("evidence float subclass did not canonicalize to exact built-in float.")
        if not math.isfinite(canonical):
            raise ValueError("evidence float values must be finite (NaN/Infinity are rejected).")
        return canonical
    if isinstance(value, dict):
        detached: dict[str, Any] = {}
        for key, item in dict.items(value):
            canonical_key = _canonical_str(key, "evidence mapping key")
            if canonical_key in detached:
                raise ValueError("evidence mapping keys collide after string canonicalization.")
            detached[canonical_key] = _detach_plain(item, _depth=_depth + 1)
        return detached
    if isinstance(value, list):
        return [
            _detach_plain(item, _depth=_depth + 1)
            for item in list.__iter__(value)
        ]
    if isinstance(value, tuple):
        return [
            _detach_plain(item, _depth=_depth + 1)
            for item in tuple.__iter__(value)
        ]
    raise TypeError(
        "unsupported evidence value type; only None and built-in "
        "bool/int/finite-float/str/dict(str-keys)/list/tuple, including "
        "their subclasses, are allowed (set/frozenset are rejected)."
    )


def _materialize_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Materialize one detached field snapshot before recorder mutation.

    A builtin ``dict`` or subclass is consumed through ``dict.items`` so its
    overrides never run. Any other ``Mapping`` is an explicit callback
    boundary: a general Mapping is executable Python behavior and cannot be
    consumed without invoking its protocol. That interface is invoked only
    here, outside the recorder lock and before current-call mutation. The
    source Mapping is traversed once, never retained or revisited, and every
    yielded key/value is canonicalized before it can enter recorder state.
    """
    if isinstance(fields, dict):
        items = dict.items(fields)
    elif isinstance(fields, _AbcMapping):
        items = fields.items()
    else:
        raise TypeError("intent.fields must be a mapping.")

    detached: dict[str, Any] = {}
    seen: set[str] = set()
    for key, value in items:
        canonical_key = _canonical_str(key, "evidence field key")
        if canonical_key in seen:
            raise ValueError("evidence field keys collide after string canonicalization.")
        seen.add(canonical_key)
        if value is not None:
            detached[canonical_key] = _detach_plain(value)
    return detached


# --------------------------------------------------------------------------- enums
class DecisionEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class AuthorizerLoadCode(Enum):
    CONTRACT_INVALID = "CONTRACT_INVALID"
    PROFILE_MISSING = "PROFILE_MISSING"
    LOCK_INVALID = "LOCK_INVALID"
    LOCK_STALE = "LOCK_STALE"


class IdentityResolutionCode(Enum):
    IDENTITY_UNKNOWN = "IDENTITY_UNKNOWN"
    IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"


class DecisionCode(Enum):
    ALLOWED = "ALLOWED"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    DELEGATION_UNKNOWN = "DELEGATION_UNKNOWN"
    DELEGATION_INACTIVE = "DELEGATION_INACTIVE"
    HANDOFF_UNKNOWN = "HANDOFF_UNKNOWN"
    HANDOFF_AUTHORITY = "HANDOFF_AUTHORITY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_NON_HUMAN = "APPROVAL_NON_HUMAN"
    APPROVAL_ROLE_INVALID = "APPROVAL_ROLE_INVALID"
    APPROVAL_NOT_GRANTED = "APPROVAL_NOT_GRANTED"
    APPROVAL_STALE = "APPROVAL_STALE"
    APPROVAL_REVISION_MISMATCH = "APPROVAL_REVISION_MISMATCH"
    # Added under ADR-0039 minor-compatibility (new decision-code members):
    APPROVAL_ACTION_MISMATCH = "APPROVAL_ACTION_MISMATCH"
    APPROVAL_EVIDENCE_MISSING = "APPROVAL_EVIDENCE_MISSING"
    PARTY_INEFFECTIVE = "PARTY_INEFFECTIVE"
    ZONE_CROSSING_DENIED = "ZONE_CROSSING_DENIED"
    CROSSING_APPROVAL_REQUIRED = "CROSSING_APPROVAL_REQUIRED"
    SENSITIVE_SHARING = "SENSITIVE_SHARING"
    SHARE_NOT_ALLOWED = "SHARE_NOT_ALLOWED"
    REVISION_MISMATCH = "REVISION_MISMATCH"
    REQUEST_MALFORMED = "REQUEST_MALFORMED"


# -------------------------------------------------------------------------- errors
class AuthorizerLoadError(RuntimeError):
    """Fail-closed load-time failure carrying an :class:`AuthorizerLoadCode`."""

    def __init__(self, code: AuthorizerLoadCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


class IdentityResolutionError(RuntimeError):
    """Raised by :meth:`Authorizer.resolve_identity`; not a policy decision."""

    def __init__(self, code: IdentityResolutionCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code


# ----------------------------------------------------------------- context + models
@dataclass(frozen=True)
class EvaluationContext:
    decision_at: str  # evaluation instant governing ALL temporal semantics
    observed_subject_revision: str  # MANDATORY; must equal the contract subject_revision


@dataclass(frozen=True)
class RuntimeOccurrence:
    """Framework-neutral identity for one logical execution attempt.

    ``operation_id`` is stable across loop visits, ``occurrence_id`` identifies
    one scheduled visit/branch execution, and ``attempt`` is its contiguous,
    one-based retry number. These values are producer assertions under the
    cooperative Tier-2 evidence boundary; the core validates their structure
    and stream transitions but does not attest their runtime truth.
    """

    operation_id: str
    occurrence_id: str
    attempt: int

    def __post_init__(self) -> None:
        operation_id = _canonical_str(self.operation_id, "operation_id")
        occurrence_id = _canonical_str(self.occurrence_id, "occurrence_id")
        if not _RUNTIME_ID_RE.fullmatch(operation_id):
            raise ValueError("operation_id is not a valid runtime identifier")
        if not _RUNTIME_ID_RE.fullmatch(occurrence_id):
            raise ValueError("occurrence_id is not a valid runtime identifier")
        if type(self.attempt) is not int or not 1 <= self.attempt <= 1_000_000:
            raise ValueError("attempt must be an integer from 1 through 1000000")
        object.__setattr__(self, "operation_id", operation_id)
        object.__setattr__(self, "occurrence_id", occurrence_id)


@dataclass(frozen=True)
class ApprovalAssertion:
    approval_ref: str
    claimed_approver_ref: str
    claimed_actor_type: str
    role: str
    granted: bool
    action_ref: str
    subject_revision: str
    issued_at: str | None = None
    expires_at: str | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityRequest:
    identity_ref: str
    capability_ref: str


@dataclass(frozen=True)
class DelegationRequest:
    delegation_id: str


@dataclass(frozen=True)
class HandoffRequest:
    handoff_id: str


@dataclass(frozen=True)
class ApprovalRequest:
    identity_ref: str
    approval: ApprovalAssertion


@dataclass(frozen=True)
class ZoneCrossingRequest:
    identity_ref: str
    source_zone: str
    target_zone: str
    approval: ApprovalAssertion | None = None


@dataclass(frozen=True)
class DataShareRequest:
    identity_ref: str
    target_ref: str
    categories: tuple[str, ...]
    source_zone: str
    target_zone: str


AuthorizationRequest = (
    CapabilityRequest
    | DelegationRequest
    | HandoffRequest
    | ApprovalRequest
    | ZoneCrossingRequest
    | DataShareRequest
)


@dataclass(frozen=True)
class DecisionBasis:
    kind: str  # membership|delegation|capability|approval|zone|gate|binding|share
    ref: str
    detail: str = ""


@dataclass(frozen=True)
class DecisionEventIntent:
    event_type: str  # a decision-phase event type only (see PHASE_INTENT)
    fields: Mapping[str, Any]  # no timestamp/sequence/producer/digests


@dataclass(frozen=True)
class Decision:
    effect: DecisionEffect
    code: DecisionCode
    reason: str = ""
    basis: tuple[DecisionBasis, ...] = ()
    event_intents: tuple[DecisionEventIntent, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.effect is DecisionEffect.ALLOW


# Frozen event phases (ADR-0039). Only intents may originate from ``evaluate``.
PHASE_INTENT = frozenset(
    {
        "capability_requested",
        "capability_allowed",
        "capability_denied",
        "delegation_requested",
        "delegation_accepted",
        "delegation_rejected",
        "approval_requested",
        "approval_granted",
        "approval_rejected",
        "policy_violation",
    }
)
PHASE_OBSERVATION = frozenset(
    {
        "agent_invoked",
        "tool_invoked",
        "handoff_initiated",
        "handoff_completed",
        "trust_zone_crossed",
        "data_shared",
        "identity_revoked",
        "runtime_failed",
    }
)


def _intent(event_type: str, **fields: Any) -> DecisionEventIntent:
    assert event_type in PHASE_INTENT, event_type
    return DecisionEventIntent(event_type=event_type, fields={k: v for k, v in fields.items() if v is not None})


def _deny(code: DecisionCode, reason: str, *, basis: tuple[DecisionBasis, ...] = (), intents: tuple[DecisionEventIntent, ...] = ()) -> Decision:
    return Decision(DecisionEffect.DENY, code, reason, basis=basis, event_intents=intents)


def _timestamp_ok(value: Any) -> bool:
    return value is None or (isinstance(value, str) and _parse_time(value) is not None)


def _approval_shape_ok(a: Any) -> bool:
    if not isinstance(a, ApprovalAssertion):
        return False
    strs = (a.approval_ref, a.claimed_approver_ref, a.claimed_actor_type, a.role, a.action_ref, a.subject_revision)
    if not all(isinstance(v, str) for v in strs):
        return False
    if not isinstance(a.granted, bool):
        return False
    # Temporal fields must be absent or valid, parseable timestamps (fail closed).
    if not _timestamp_ok(a.issued_at) or not _timestamp_ok(a.expires_at):
        return False
    return _all_str(a.evidence_refs)


# ---------------------------------------------------------------------- authorizer
@dataclass(frozen=True, slots=True, init=False)
class AuthorizerState:
    """The exact state retained by one :class:`Authorizer`.

    ``document`` and ``lock_payload`` return detached ordinary-container copies.
    ``composition`` returns a detached, fully serializer-compatible
    :class:`CompositionResult`.  Consumers may therefore use or mutate any
    returned compatibility view without changing this state or the Authorizer
    built from it.  The retained snapshots are recursively immutable and are
    never reconstructed from the filesystem.

    Assurance scope.  This state describes what the Authorizer retains — it does
    not by itself assert how that content was established.  Document validation,
    governance composition, and agentic-network lock verification are guaranteed
    **only when the Authorizer was obtained through :func:`load_authorizer`**,
    which is the sole path that runs those stages.  Direct
    ``Authorizer(document, composition, lock_payload)`` construction performs
    none of them: it faithfully retains whatever the caller supplied, and this
    state then describes exactly those caller-supplied inputs.
    """

    _document: Mapping[str, Any] = field(repr=False)
    _composition: CompositionResult = field(repr=False)
    _lock_payload: Mapping[str, Any] = field(repr=False)
    contract_digest: str
    network_lock_digest: str

    @classmethod
    def _from_authorizer_inputs(
        cls,
        document: Mapping[str, Any],
        composition: CompositionResult,
        lock_payload: Mapping[str, Any],
    ) -> AuthorizerState:
        instance = object.__new__(cls)
        frozen_document = _deep_freeze(document)
        frozen_composition = _deep_freeze(composition)
        frozen_lock_payload = _deep_freeze(lock_payload)
        object.__setattr__(instance, "_document", frozen_document)
        object.__setattr__(instance, "_composition", frozen_composition)
        object.__setattr__(instance, "_lock_payload", frozen_lock_payload)
        object.__setattr__(
            instance,
            "contract_digest",
            contract_digest(_thaw(frozen_document)),
        )
        object.__setattr__(
            instance,
            "network_lock_digest",
            agentic_network_lock_digest(_thaw(frozen_lock_payload)),
        )
        return instance

    @property
    def document(self) -> dict[str, Any]:
        """Return a detached plain-container copy of the validated contract."""

        return _thaw(self._document)

    @property
    def composition(self) -> CompositionResult:
        """Return a detached copy of the effective governance composition."""

        return _detach_composition(self._composition)

    @property
    def lock_payload(self) -> dict[str, Any]:
        """Return a detached plain-container copy of the verified network lock."""

        return _thaw(self._lock_payload)


class Authorizer:
    """One loaded, lock-verified contract. Deeply immutable and thread-safe."""

    def __init__(self, document: Mapping[str, Any], composition: Any, lock_payload: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_frozen", False)
        # One deep-frozen construction snapshot backs both Authorizer behavior
        # and the public state SPI. No later access reloads or recomposes it.
        self._state = AuthorizerState._from_authorizer_inputs(
            document,
            composition,
            lock_payload,
        )
        # Every retained attribute and every index below is derived exclusively
        # from that frozen snapshot. The caller keeps ownership of the objects it
        # passed in and may mutate them freely afterwards without reaching this
        # Authorizer, so the constructor parameters are dropped here: a later
        # read of one is a NameError rather than a silent state divergence.
        del document, composition, lock_payload
        self._document = self._state._document
        self._lock_payload = self._state._lock_payload
        self._composition = self._state._composition
        self.contract_digest = self._state.contract_digest
        self.network_lock_digest = self._state.network_lock_digest
        network = self._document.get("agentic_network")
        self._network: Mapping[str, Any] = network if isinstance(network, Mapping) else MappingProxyType({})
        self.network_id = str(self._network.get("id"))
        self.subject_revision = str(self._network.get("subject_revision"))

        self._identities = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._document.get("agent_identities")) if isinstance(item.get("id"), str)}
        )
        self._capabilities = MappingProxyType(
            {str(item["name"]): item for item in _map_items(self._document.get("capabilities")) if isinstance(item.get("name"), str)}
        )
        self._memberships = _map_items(self._network.get("memberships"))
        self._zones = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("trust_zones")) if isinstance(item.get("id"), str)}
        )
        self._gates = _map_items(self._network.get("network_gates"))
        self._delegations = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("delegations")) if isinstance(item.get("id"), str)}
        )
        self._handoffs = MappingProxyType(
            {str(item["id"]): item for item in _map_items(self._network.get("handoffs")) if isinstance(item.get("id"), str)}
        )
        self._revocations = _map_items(self._network.get("revocations"))
        self._approvals = MappingProxyType(
            {req.id: req for req in self._composition.approval_requirements}
        )
        object.__setattr__(self, "_frozen", True)

    # ---- structural immutability ----
    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(f"Authorizer is immutable; cannot set {name!r}")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Authorizer is immutable")

    @property
    def state(self) -> AuthorizerState:
        """Return the exact state this Authorizer retains.

        Validation, governance composition, and lock verification are guaranteed
        only for an Authorizer obtained through :func:`load_authorizer`, the sole
        path that runs those stages. Direct ``Authorizer(...)`` construction does
        not perform them, so for a directly constructed Authorizer this returns
        the caller's own construction inputs — retained faithfully, immutably,
        and detached, but not independently validated, composed, or verified.
        """

        return self._state

    # ---- identity resolution (separate from policy decisions) ----
    def resolve_identity(self, framework: str, agent_key: str) -> str:
        matches = [
            identity_id
            for identity_id, identity in sorted(self._identities.items())
            if any(binding.get("framework") == framework and binding.get("agent_key") == agent_key for binding in _map_items(identity.get("framework_bindings")))
        ]
        if not matches:
            raise IdentityResolutionError(IdentityResolutionCode.IDENTITY_UNKNOWN, f"Framework key {agent_key!r} maps to no declared {framework} identity.")
        if len(matches) > 1:
            raise IdentityResolutionError(IdentityResolutionCode.IDENTITY_AMBIGUOUS, f"Framework key {agent_key!r} maps to multiple declared {framework} identities.")
        return matches[0]

    # ---- temporal helpers (all evaluated at decision_at) ----
    @staticmethod
    def _interval_contains(item: Mapping[str, Any], ts: datetime | None) -> bool | None:
        valid_from = _parse_time(item.get("valid_from"))
        expires_at = _parse_time(item.get("expires_at"))
        if valid_from is None or expires_at is None or ts is None:
            return None
        return valid_from <= ts < expires_at

    def _revoked_at(self, kind: str, ref: str, ts: datetime | None) -> bool:
        if ts is None:
            return False
        for revocation in self._revocations:
            if _revocation_target_key(revocation.get("target")) != (kind, ref):
                continue
            effective = _parse_time(revocation.get("effective_at"))
            if effective is not None and ts >= effective:
                return True
        return False

    def _identity_effective(self, ref: str, ts: datetime | None) -> bool:
        identity = self._identities.get(ref)
        if identity is None or identity.get("status") != "active":
            return False
        return self._interval_contains(identity, ts) is True and not self._revoked_at("agent_identity", ref, ts)

    def _zone_member(self, actor: str, zone: str, ts: datetime | None) -> bool:
        for membership in self._memberships:
            if membership.get("identity_ref") != actor or membership.get("trust_zone_ref") != zone:
                continue
            if membership.get("status") != "authorized":
                continue
            if self._interval_contains(membership, ts) is not True:
                continue
            if self._revoked_at("membership", str(membership.get("id")), ts):
                continue
            return True
        return False

    def _holds_capability(self, actor: str, capability: str, ts: datetime | None) -> bool:
        identity = self._identities.get(actor)
        if identity is None or capability not in _str_items(identity.get("capability_refs")):
            return False
        for membership in self._memberships:
            if membership.get("identity_ref") != actor or membership.get("status") != "authorized":
                continue
            if self._interval_contains(membership, ts) is not True:
                continue
            if self._revoked_at("membership", str(membership.get("id")), ts):
                continue
            if capability in _str_items(membership.get("capability_refs")):
                return True
        return False

    def _delegated(self, actor: str, capability: str, ts: datetime | None) -> str | None:
        for delegation_id, delegation in sorted(self._delegations.items()):
            if (
                delegation.get("delegate_ref") == actor
                and delegation.get("capability_ref") == capability
                and delegation.get("status") == "active"
                and self._interval_contains(delegation, ts) is True
                and not self._revoked_at("delegation", delegation_id, ts)
            ):
                return delegation_id
        return None

    # ---- request-shape validation (fail closed before any dict/set access) ----
    @staticmethod
    def _shape_ok(request: AuthorizationRequest) -> bool:
        if isinstance(request, CapabilityRequest):
            return isinstance(request.identity_ref, str) and isinstance(request.capability_ref, str)
        if isinstance(request, DelegationRequest):
            return isinstance(request.delegation_id, str)
        if isinstance(request, HandoffRequest):
            return isinstance(request.handoff_id, str)
        if isinstance(request, ApprovalRequest):
            return isinstance(request.identity_ref, str) and _approval_shape_ok(request.approval)
        if isinstance(request, ZoneCrossingRequest):
            return (
                isinstance(request.identity_ref, str)
                and isinstance(request.source_zone, str)
                and isinstance(request.target_zone, str)
                and (request.approval is None or _approval_shape_ok(request.approval))
            )
        if isinstance(request, DataShareRequest):
            return (
                isinstance(request.identity_ref, str)
                and isinstance(request.target_ref, str)
                and isinstance(request.source_zone, str)
                and isinstance(request.target_zone, str)
                and _all_str(request.categories)
            )
        return False

    # ---- evaluation ----
    def evaluate(self, request: AuthorizationRequest, *, context: EvaluationContext) -> Decision:
        if not isinstance(context, EvaluationContext):
            return _deny(DecisionCode.REQUEST_MALFORMED, "context is not an EvaluationContext.")
        ts = _parse_time(context.decision_at)
        if ts is None or not _valid_revision(context.observed_subject_revision):
            return _deny(DecisionCode.REQUEST_MALFORMED, "Malformed evaluation context (decision_at or observed_subject_revision).")
        if not isinstance(request, AuthorizationRequest) or not self._shape_ok(request):
            return _deny(DecisionCode.REQUEST_MALFORMED, "Malformed authorization request.")
        if context.observed_subject_revision != self.subject_revision:
            actor = self._actor_of(request)
            intents = (_intent("policy_violation", actor_ref=actor),) if actor else ()
            return _deny(DecisionCode.REVISION_MISMATCH, "observed_subject_revision does not exactly match the contract subject_revision.", basis=(DecisionBasis("binding", self.subject_revision),), intents=intents)
        if isinstance(request, CapabilityRequest):
            return self._capability(request, ts)
        if isinstance(request, DelegationRequest):
            return self._delegation(request, ts)
        if isinstance(request, HandoffRequest):
            return self._handoff(request, ts)
        if isinstance(request, ApprovalRequest):
            return self._approval(request, ts)
        if isinstance(request, ZoneCrossingRequest):
            return self._zone_crossing(request, ts)
        if isinstance(request, DataShareRequest):
            return self._data_share(request, ts)
        return _deny(DecisionCode.REQUEST_MALFORMED, f"Unsupported request type {type(request).__name__!r}.")

    @staticmethod
    def _actor_of(request: AuthorizationRequest) -> str | None:
        return getattr(request, "identity_ref", None)

    def _known_effective(self, ref: str, ts: datetime | None) -> Decision | None:
        if ref not in self._identities:
            return _deny(DecisionCode.REQUEST_MALFORMED, f"Identity {ref!r} is not declared; resolve it first.")
        if not self._identity_effective(ref, ts):
            return _deny(
                DecisionCode.PARTY_INEFFECTIVE,
                f"Identity {ref!r} is inactive, outside its validity window, or revoked at decision_at.",
                basis=(DecisionBasis("binding", ref),),
                intents=(_intent("policy_violation", actor_ref=ref),),
            )
        return None

    def _capability(self, request: CapabilityRequest, ts: datetime | None) -> Decision:
        actor, capability = request.identity_ref, request.capability_ref
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        if capability not in self._capabilities:
            return _deny(DecisionCode.CAPABILITY_UNKNOWN, f"Capability {capability!r} is not declared in the contract.", intents=(_intent("policy_violation", actor_ref=actor),))
        requested = _intent("capability_requested", actor_ref=actor, capability_ref=capability)
        delegation_ref = None
        if not self._holds_capability(actor, capability, ts):
            delegation_ref = self._delegated(actor, capability, ts)
            if delegation_ref is None:
                return _deny(
                    DecisionCode.CAPABILITY_DENIED,
                    f"Identity {actor!r} neither holds nor validly receives {capability!r} at decision_at.",
                    basis=(DecisionBasis("capability", capability),),
                    intents=(requested, _intent("capability_denied", actor_ref=actor, capability_ref=capability, policy_decision="deny")),
                )
        basis = DecisionBasis("membership" if delegation_ref is None else "delegation", capability if delegation_ref is None else delegation_ref)
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(basis,),
            event_intents=(requested, _intent("capability_allowed", actor_ref=actor, capability_ref=capability, policy_decision="allow", delegation_ref=delegation_ref)),
        )

    def _delegation(self, request: DelegationRequest, ts: datetime | None) -> Decision:
        delegation = self._delegations.get(request.delegation_id)
        if delegation is None:
            return _deny(DecisionCode.DELEGATION_UNKNOWN, f"Delegation {request.delegation_id!r} is not declared.")
        delegator = str(delegation.get("delegator_ref"))
        delegate = str(delegation.get("delegate_ref"))
        for party in (delegator, delegate):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        requested = _intent("delegation_requested", actor_ref=delegator, target_ref=delegate, delegation_ref=request.delegation_id)
        active = delegation.get("status") == "active" and self._interval_contains(delegation, ts) is True and not self._revoked_at("delegation", request.delegation_id, ts)
        if not active:
            return _deny(
                DecisionCode.DELEGATION_INACTIVE,
                f"Delegation {request.delegation_id!r} is not active at decision_at.",
                basis=(DecisionBasis("delegation", request.delegation_id),),
                intents=(requested, _intent("delegation_rejected", actor_ref=delegate, delegation_ref=request.delegation_id)),
            )
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("delegation", request.delegation_id),),
            event_intents=(requested, _intent("delegation_accepted", actor_ref=delegate, delegation_ref=request.delegation_id)),
        )

    def _handoff(self, request: HandoffRequest, ts: datetime | None) -> Decision:
        handoff = self._handoffs.get(request.handoff_id)
        if handoff is None:
            return _deny(DecisionCode.HANDOFF_UNKNOWN, f"Handoff {request.handoff_id!r} is not declared.")
        source = str(handoff.get("from_identity_ref"))
        target = str(handoff.get("to_identity_ref"))
        for party in (source, target):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        for capability in _str_items(handoff.get("required_capability_refs")):
            if not self._holds_capability(target, capability, ts) and self._delegated(target, capability, ts) is None:
                return _deny(
                    DecisionCode.HANDOFF_AUTHORITY,
                    f"A handoff transfers responsibility, never authority: the target does not hold {capability!r}.",
                    basis=(DecisionBasis("capability", capability),),
                    intents=(_intent("policy_violation", actor_ref=source, target_ref=target, handoff_ref=request.handoff_id),),
                )
        # Authorized. handoff_initiated is a post-action OBSERVATION (adapter-emitted).
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("binding", request.handoff_id, "handoff authorized"),))

    def _approval(self, request: ApprovalRequest, ts: datetime | None, *, governed_actions: frozenset[str] | None = None) -> Decision:
        actor = request.identity_ref
        a = request.approval
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        requested = _intent("approval_requested", actor_ref=actor, approval_ref=a.approval_ref)
        effective = self._approvals.get(a.approval_ref)
        if effective is None:
            return _deny(DecisionCode.REQUEST_MALFORMED, f"Approval {a.approval_ref!r} is not a declared requirement.", intents=(requested,))

        def rejected(code: DecisionCode, reason: str) -> Decision:
            return _deny(code, reason, basis=(DecisionBasis("approval", a.approval_ref),), intents=(requested, _intent("approval_rejected", actor_ref=actor, approval_ref=a.approval_ref, approver={"role": a.role, "actor_type": a.claimed_actor_type})))

        # Universal context binding: the approval must be for the current subject
        # revision. Any governed change bumps subject_revision (and lock
        # verification rejects drift), so this enforces the invalidation
        # conditions that the assertion alone cannot otherwise establish.
        if a.subject_revision != self.subject_revision:
            return rejected(DecisionCode.APPROVAL_REVISION_MISMATCH, "Approval subject_revision does not match the contract subject_revision.")
        # A declared revision_binding is an additional, independent exact check.
        binding = effective.revision_binding
        if isinstance(binding, Mapping) and binding.get("revision") and a.subject_revision != str(binding.get("revision")):
            return rejected(DecisionCode.APPROVAL_REVISION_MISMATCH, "Approval subject_revision does not match the required revision binding.")
        # Action scope: governed by the gate for a crossing, else by the requirement.
        action_scope = governed_actions if governed_actions is not None else frozenset(getattr(effective, "actions_requiring_approval", ()) or ())
        if action_scope and a.action_ref not in action_scope:
            return rejected(DecisionCode.APPROVAL_ACTION_MISMATCH, f"Approval action {a.action_ref!r} is outside the governed action scope.")
        denied_types = set(getattr(effective, "denied_actor_types", ()) or ())
        if a.claimed_actor_type != "human" or a.claimed_actor_type in denied_types:
            return rejected(DecisionCode.APPROVAL_NON_HUMAN, "AI systems, tools, models, and execution surfaces cannot approve.")
        eligible = set(getattr(effective, "eligible_roles", ()) or ()) | set(getattr(effective, "required_roles", ()) or ())
        if a.role not in eligible:
            return rejected(DecisionCode.APPROVAL_ROLE_INVALID, f"Role {a.role!r} is outside the composed approval authority.")
        required_evidence = set(getattr(effective, "required_evidence", ()) or ())
        if required_evidence and not required_evidence.issubset(set(a.evidence_refs)):
            return rejected(DecisionCode.APPROVAL_EVIDENCE_MISSING, "The approval does not reference all required evidence.")
        # Temporal validity at decision_at: earliest applicable expiry across the
        # assertion expiry, the effective absolute expiry, and issued_at +
        # expires_after. Future-issued approvals fail closed. (Field FORMATS were
        # validated in _approval_shape_ok; malformed values never reach here.)
        issued = _parse_time(a.issued_at)
        max_age = _parse_duration(getattr(effective, "expires_after", None))
        if getattr(effective, "expires_after", None) is not None and issued is None:
            return rejected(DecisionCode.APPROVAL_STALE, "The requirement uses a relative expiry but the approval declares no issuance time.")
        if issued is not None and ts is not None and ts < issued:
            return rejected(DecisionCode.APPROVAL_STALE, "The approval is issued after decision_at (not yet valid).")
        expiries: list[datetime] = [c for c in (_parse_time(a.expires_at), _parse_time(getattr(effective, "expires_at", None))) if c is not None]
        if issued is not None and max_age is not None:
            expiries.append(issued + max_age)
        if expiries and ts is not None and ts >= min(expiries):
            return rejected(DecisionCode.APPROVAL_STALE, "The approval is expired at decision_at (earliest applicable expiry).")
        if not a.granted:
            return rejected(DecisionCode.APPROVAL_NOT_GRANTED, "The supplied human approval record does not grant approval.")
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            "",
            basis=(DecisionBasis("approval", a.approval_ref),),
            event_intents=(requested, _intent("approval_granted", actor_ref=actor, approval_ref=a.approval_ref, approver={"role": a.role, "actor_type": "human"})),
        )

    def _governing_gates(self, source: str, target: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(gate for gate in self._gates if source in _str_items(gate.get("source_zone_refs")) and target in _str_items(gate.get("target_zone_refs")))

    def _zone_crossing(self, request: ZoneCrossingRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        bad = self._known_effective(actor, ts)
        if bad is not None:
            return bad
        zone = self._zones.get(request.source_zone)
        if zone is None or request.target_zone not in _str_items(zone.get("allowed_transition_targets")):
            return _deny(
                DecisionCode.ZONE_CROSSING_DENIED,
                f"Crossing {request.source_zone!r} -> {request.target_zone!r} is not declared.",
                basis=(DecisionBasis("zone", request.target_zone),),
                intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone if request.source_zone in self._zones else None, target_zone_ref=request.target_zone if request.target_zone in self._zones else None),),
            )
        if not self._zone_member(actor, request.source_zone, ts):
            return _deny(
                DecisionCode.ZONE_CROSSING_DENIED,
                f"Identity {actor!r} has no valid membership in source zone {request.source_zone!r}.",
                basis=(DecisionBasis("zone", request.source_zone),),
                intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
            )
        destination = self._zones.get(request.target_zone)
        needs_approval = destination is not None and destination.get("classification") in EXTERNAL_ZONE_CLASSIFICATIONS
        approval_intents: tuple[DecisionEventIntent, ...] = ()
        gate_basis: tuple[DecisionBasis, ...] = ()
        if needs_approval:
            gates = self._governing_gates(request.source_zone, request.target_zone)
            if not gates:
                return _deny(
                    DecisionCode.ZONE_CROSSING_DENIED,
                    "No declared gate governs this external trust-zone crossing.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                )
            if request.approval is None:
                expected = sorted({r for g in gates for r in _str_items(g.get("required_approval_refs"))})
                return Decision(
                    DecisionEffect.APPROVAL_REQUIRED,
                    DecisionCode.CROSSING_APPROVAL_REQUIRED,
                    "External trust-zone crossings require a human approval.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    event_intents=(_intent("approval_requested", actor_ref=actor, approval_ref=(expected[0] if expected else None)),),
                )
            ar, ac = request.approval.approval_ref, request.approval.action_ref
            # Per-gate authority: one individual gate must require this approval
            # AND govern this action. No union across gates.
            matched = [g for g in gates if ar in _str_items(g.get("required_approval_refs")) and ac in _str_items(g.get("action_classes"))]
            if not matched:
                approval_gates = [g for g in gates if ar in _str_items(g.get("required_approval_refs"))]
                if approval_gates:
                    return _deny(
                        DecisionCode.APPROVAL_ACTION_MISMATCH,
                        f"Action {ac!r} is not governed by the gate(s) requiring approval {ar!r} for this crossing.",
                        basis=(DecisionBasis("zone", request.target_zone),),
                        intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                    )
                return _deny(
                    DecisionCode.CROSSING_APPROVAL_REQUIRED,
                    f"Approval {ar!r} is not required by any gate governing this crossing.",
                    basis=(DecisionBasis("zone", request.target_zone),),
                    intents=(_intent("policy_violation", actor_ref=actor, source_zone_ref=request.source_zone, target_zone_ref=request.target_zone),),
                )
            gate_basis = tuple(DecisionBasis("gate", str(g.get("id"))) for g in matched)
            sub = self._approval(ApprovalRequest(actor, request.approval), ts, governed_actions=frozenset({ac}))
            if not sub.allowed:
                return sub
            approval_intents = sub.event_intents
        # Authorized. trust_zone_crossed is a post-action OBSERVATION.
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("zone", request.target_zone),) + gate_basis, event_intents=approval_intents)

    def _data_share(self, request: DataShareRequest, ts: datetime | None) -> Decision:
        actor = request.identity_ref
        for party in (actor, request.target_ref):
            bad = self._known_effective(party, ts)
            if bad is not None:
                return bad
        categories = set(request.categories)
        sensitive = SENSITIVE_CATEGORIES & categories
        if sensitive:
            return _deny(DecisionCode.SENSITIVE_SHARING, "Sensitive categories are never shareable: " + ", ".join(sorted(sensitive)) + ".", basis=(DecisionBasis("share", sorted(sensitive)[0]),), intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),))
        for zone_id in (request.source_zone, request.target_zone):
            zone = self._zones.get(zone_id)
            allowlist = set(_str_items(zone.get("share_allowlist"))) if zone else set()
            uncovered = sorted(categories - allowlist)
            if uncovered:
                return _deny(DecisionCode.SHARE_NOT_ALLOWED, f"Zone {zone_id!r} does not allow sharing: " + ", ".join(uncovered) + ".", basis=(DecisionBasis("share", uncovered[0]),), intents=(_intent("policy_violation", actor_ref=actor, target_ref=request.target_ref),))
        # Authorized. data_shared is a post-action OBSERVATION.
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "", basis=(DecisionBasis("share", "allowlisted"),))


def load_authorizer(contract_path: str | Path, lock_path: str | Path, *, validation_as_of: str) -> Authorizer:
    """Load, validate (as of ``validation_as_of``), and lock-verify one contract.

    Fails closed with an :class:`AuthorizerLoadError` mapping every stage failure
    deterministically into the frozen load taxonomy: contract/parser/registry/
    check/composition -> CONTRACT_INVALID; missing profile -> PROFILE_MISSING;
    lock read/parse -> LOCK_INVALID; lock verification -> LOCK_STALE.
    """
    try:
        registry = registry_for_contract(contract_path)
        document = load_nyx(contract_path)
    except AuthorizerLoadError:
        raise
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed mapping
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"Cannot load the contract: {type(exc).__name__}") from exc
    if not isinstance(document, Mapping):
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, "The contract is not a mapping/object.")
    document_root = Path(contract_path).resolve().parent
    try:
        diagnostics = list(check_document(document))
        composition = compose_document_governance(document, registry=registry)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"The contract fails to compose: {type(exc).__name__}") from exc
    if composition is None:
        raise AuthorizerLoadError(AuthorizerLoadCode.PROFILE_MISSING, "The contract does not resolve a governance profile.")
    contributed = {item.block for item in (composition.block_schemas or ())}
    diagnostics = [item for item in diagnostics if not (item.code == "UNKNOWN_TOP_LEVEL_BLOCK" and item.path in contributed)]
    try:
        diagnostics.extend(evaluate_document_governance(document, registry=registry, as_of=validation_as_of, document_root=document_root))
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, f"The contract fails governance evaluation: {type(exc).__name__}") from exc
    if has_errors(diagnostics):
        codes = sorted({item.code for item in diagnostics if item.level == "error"})
        raise AuthorizerLoadError(AuthorizerLoadCode.CONTRACT_INVALID, "The contract fails governance validation: " + ", ".join(codes))
    try:
        lock_payload = load_agentic_network_lock(lock_path)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_INVALID, f"Cannot load the agentic-network lock: {type(exc).__name__}") from exc
    try:
        stale = verify_agentic_network_lock(lock_payload, document, composition)
    except Exception as exc:  # noqa: BLE001
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_STALE, f"Cannot verify the agentic-network lock: {type(exc).__name__}") from exc
    if stale:
        raise AuthorizerLoadError(AuthorizerLoadCode.LOCK_STALE, "Stale or mismatched agentic-network lock: " + ", ".join(sorted({item.code for item in stale})))
    return Authorizer(document, composition, lock_payload)


# ------------------------------------------------------------------ evidence recorder
class EvidenceRecorder:
    """Deterministic construction + consistency binding for runtime evidence.

    Turns decision-event intents and adapter-supplied post-action observations
    into a schema-valid ``nornyx.agentic_runtime_events.v1`` stream bound to the
    contract, lock, and already-verified observed subject revision. It stamps ids,
    mission-local sequence numbers, producer, timestamps (from the bound
    ``context.decision_at`` — no wall-clock), and binding digests.

    The bound ``EvaluationContext`` is validated **once at construction**: the
    recorder fails closed (``ValueError``) if ``context.observed_subject_revision``
    does not exactly equal the authorizer's ``subject_revision``.

    It provides construction and consistency binding ONLY: it does not
    authenticate the adapter, attest the occurrence, or make an event true.
    Permitting the ``external_runtime`` producer label confers no Tier-3 assurance.

    Caller-controlled string scalars accept ``str`` and its subclasses, but
    subclasses are immediately converted to exact strings through the unbound
    base implementation. Canonicalization occurs before lock acquisition and
    before any membership, dict-key, formatting, or error-rendering use, so a
    hostile subclass override never runs inside the recorder. Mutation of the
    event list and per-mission sequence counters is confined to one lock, taken
    only after all caller-controlled values have become exact plain builtins.
    """

    def __init__(self, authorizer: Authorizer, context: EvaluationContext, *, producer_id: str, producer_version: str = "1.0", producer_type: str = "framework_adapter") -> None:
        producer_id = _canonical_str(producer_id, "producer_id")
        producer_version = _canonical_str(producer_version, "producer_version")
        producer_type = _canonical_str(producer_type, "producer_type")
        decision_at = _canonical_str(context.decision_at, "context.decision_at")
        observed_subject_revision = _canonical_str(
            context.observed_subject_revision,
            "context.observed_subject_revision",
        )
        if producer_type not in _PRODUCER_TYPES:
            raise ValueError(f"invalid producer_type {producer_type!r}; permitted: {sorted(_PRODUCER_TYPES)}")
        if observed_subject_revision != authorizer.subject_revision:
            raise ValueError("observed_subject_revision does not match the contract subject_revision; the recorder refuses to bind a mismatched runtime revision.")
        self._authorizer = authorizer
        self._context = EvaluationContext(
            decision_at=decision_at,
            observed_subject_revision=observed_subject_revision,
        )
        self._producer = {"type": producer_type, "id": producer_id, "version": producer_version}
        self._events: list[dict[str, Any]] = []
        self._sequences: dict[str, int] = {}
        locked_schema = self._authorizer._lock_payload.get("runtime_events_schema")
        self._schema_version = (
            str(locked_schema.get("version"))
            if isinstance(locked_schema, Mapping)
            else RUNTIME_EVENTS_SCHEMA_VERSION
        )
        if self._schema_version not in {"1.0", "1.1"}:
            raise ValueError(
                "the authorizer lock declares an unsupported runtime-events "
                f"schema version {self._schema_version!r}"
            )
        self._occurrence_mode: str | None = (
            None if self._schema_version == "1.0" else "legacy"
        )
        self._lock = threading.Lock()

    @classmethod
    def for_occurrences(
        cls,
        authorizer: Authorizer,
        context: EvaluationContext,
        *,
        producer_id: str,
        producer_version: str = "1.0",
        producer_type: str = "framework_adapter",
    ) -> EvidenceRecorder:
        """Create a recorder that requires explicit occurrence metadata."""

        recorder = cls(
            authorizer,
            context,
            producer_id=producer_id,
            producer_version=producer_version,
            producer_type=producer_type,
        )
        if recorder._schema_version != "1.1":
            raise ValueError(
                "explicit occurrence recording requires a lock bound to "
                "runtime-events schema version 1.1"
            )
        recorder._occurrence_mode = "explicit"
        return recorder

    @classmethod
    def resume(
        cls,
        authorizer: Authorizer,
        context: EvaluationContext,
        prior_stream: Mapping[str, Any],
        *,
        producer_id: str,
        producer_version: str = "1.0",
        producer_type: str = "framework_adapter",
    ) -> EvidenceRecorder:
        """Resume one validated stream and continue returning cumulative evidence.

        The prior stream must be valid against the exact authorizer contract and
        lock, use the same producer identity, and not contain timestamps later
        than the new context's ``decision_at``. The prefix is deeply detached
        before becoming recorder-owned state.
        """

        from ..agentic_evidence import validate_runtime_events

        if not isinstance(prior_stream, Mapping):
            raise TypeError("prior_stream must be a mapping")
        recorder = cls(
            authorizer,
            context,
            producer_id=producer_id,
            producer_version=producer_version,
            producer_type=producer_type,
        )
        detached = _detach_plain(prior_stream)
        if detached.get("producer") != recorder._producer:
            raise ValueError("prior_stream producer does not match the resumed recorder")
        if detached.get("schema_version") != recorder._schema_version:
            raise ValueError(
                "prior_stream schema version does not match the authorizer lock"
            )
        prior_mode = detached.get("occurrence_mode")
        if recorder._schema_version == "1.0":
            if prior_mode is not None:
                raise ValueError("runtime-events 1.0 streams cannot declare occurrence_mode")
            recorder._occurrence_mode = None
        elif prior_mode in {"legacy", "explicit"}:
            recorder._occurrence_mode = prior_mode
        else:
            raise ValueError("runtime-events 1.1 streams require a valid occurrence_mode")

        report = validate_runtime_events(
            _thaw(authorizer._document),
            authorizer._composition,
            _thaw(authorizer._lock_payload),
            detached,
        )
        if report["status"] != "pass":
            codes = sorted(
                {
                    item.get("code", "AN_EVT_INVALID")
                    for item in report.get("diagnostics", [])
                    if isinstance(item, Mapping)
                }
            )
            raise ValueError(
                "prior_stream is not valid against the supplied authorizer: "
                + ", ".join(codes)
            )

        resumed_at = _parse_time(recorder._context.decision_at)
        prior_events = detached.get("events")
        if not isinstance(prior_events, list):
            raise ValueError("prior_stream events must be a list")
        for event in prior_events:
            if not isinstance(event, Mapping):
                raise ValueError("prior_stream events must be objects")
            event_time = _parse_time(event.get("timestamp"))
            if resumed_at is None or event_time is None or event_time > resumed_at:
                raise ValueError(
                    "resumed context.decision_at must not precede prior event timestamps"
                )

        with recorder._lock:
            recorder._events = [
                {key: _detach_plain(value) for key, value in event.items()}
                for event in prior_events
            ]
            recorder._sequences = {}
            for event in recorder._events:
                mission = event.get("mission_id")
                sequence = event.get("sequence")
                if isinstance(mission, str) and isinstance(sequence, int):
                    recorder._sequences[mission] = max(
                        recorder._sequences.get(mission, 0), sequence
                    )
        return recorder

    def _build_event_unlocked(self, event_type: str, mission_id: str, seq: int, fields: Mapping[str, Any]) -> dict[str, Any]:
        """Assemble one event dict. Does not itself acquire or require the lock —
        callers hold ``self._lock`` for the surrounding critical section — and
        must have already validated/detached ``event_type``, ``mission_id``, and
        ``fields``. Raising here (e.g. via a test double) must never leave
        ``self._events``/``self._sequences`` partially updated: callers commit
        those only after every build in a batch has already succeeded."""
        event: dict[str, Any] = {
            "event_id": f"{mission_id}-{seq:04d}",
            "event_type": event_type,
            "mission_id": mission_id,
            "sequence": seq,
            "timestamp": self._context.decision_at,
            "network_id": self._authorizer.network_id,
            "contract_digest": self._authorizer.contract_digest,
            "network_lock_digest": self._authorizer.network_lock_digest,
            "subject_revision": self._authorizer.subject_revision,  # == verified observed revision
            "producer": dict(self._producer),
        }
        event.update(fields)
        return event

    def _stamp(self, event_type: str, mission_id: str, fields: Mapping[str, Any]) -> None:
        """Detach fields, then perform one atomic build/append/counter update.

        Called only from :meth:`record_observation`. Private subclasses may
        override this to observe (or intercept) every post-action observation;
        :meth:`record_decision` deliberately does NOT call ``_stamp`` (see its
        docstring), so such an override never sees decision-intent commits.
        The event is fully built *before* ``self._sequences``/``self._events``
        are touched, so a build failure (e.g. a hostile/broken
        ``_build_event_unlocked`` override) leaves both untouched rather than
        advancing the sequence counter for an event that was never appended.
        """
        detached = _materialize_fields(fields)
        with self._lock:
            seq = self._sequences.get(mission_id, 0) + 1
            event = self._build_event_unlocked(event_type, mission_id, seq, detached)
            self._sequences[mission_id] = seq
            self._events.append(event)

    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        """Record the decision's intents. Intents only — never observations.

        Does NOT call :meth:`_stamp`. A decision's intents must commit as one
        transactional batch — either all of a decision's events are appended
        under a single lock acquisition, in mission-sequence order, with no
        other thread's events interleaved between them, or none are (validation
        failures raise before any mutation). Routing through the single-event
        ``_stamp`` would only guarantee each intent's atomicity individually, not
        the whole decision's; it would also let a private subclass that
        overrides ``_stamp`` to observe post-action observations silently
        intercept decision-intent commits too, which is a materially different
        (and unintended) capability. All validation and detachment happens
        before the lock is acquired.

        Inside the lock, every event in the batch is built first (via
        :meth:`_build_event_unlocked`) into a local list; ``self._sequences``
        and ``self._events`` are updated only after every build in the batch
        has succeeded. If any build raises partway through a multi-intent
        batch — not just a validation/detachment failure, which already raises
        before the lock is even acquired — neither ``self._sequences`` nor
        ``self._events`` is left partially updated.
        """
        mission_id = _canonical_str(mission_id, "mission_id")
        prepared: list[tuple[str, dict[str, Any]]] = []
        for intent in decision.event_intents:
            event_type = _canonical_str(intent.event_type, "intent.event_type")
            if event_type not in PHASE_INTENT:
                raise ValueError(f"{event_type!r} is not a decision-event intent")
            detached = _materialize_fields(intent.fields)
            prepared.append((event_type, detached))
        # Nothing above mutated recorder state: a malformed intent anywhere in
        # the batch raises before any event is appended or any counter moves.
        if not prepared:
            return
        with self._lock:
            base_seq = self._sequences.get(mission_id, 0)
            built = [
                self._build_event_unlocked(event_type, mission_id, base_seq + offset, fields)
                for offset, (event_type, fields) in enumerate(prepared, start=1)
            ]
            # Every build in the batch succeeded: commit the whole batch as one
            # atomic update. If any build above had raised, execution would
            # never reach here, and neither `_sequences` nor `_events` would
            # have been touched.
            self._sequences[mission_id] = base_seq + len(prepared)
            self._events.extend(built)

    @staticmethod
    def _occurrence_fields(occurrence: RuntimeOccurrence) -> dict[str, Any]:
        if not isinstance(occurrence, RuntimeOccurrence):
            raise TypeError("occurrence must be a RuntimeOccurrence")
        return {
            "occurrence": {
                "operation_id": occurrence.operation_id,
                "occurrence_id": occurrence.occurrence_id,
                "attempt": occurrence.attempt,
            }
        }

    def _require_explicit_occurrences(self) -> None:
        if self._schema_version != "1.1" or self._occurrence_mode != "explicit":
            raise ValueError(
                "occurrence-aware recording requires EvidenceRecorder.for_occurrences() "
                "or an explicit stream resumed with EvidenceRecorder.resume()"
            )

    def record_occurrence_decision(
        self,
        decision: Decision,
        *,
        mission_id: str,
        occurrence: RuntimeOccurrence,
    ) -> None:
        """Atomically record decision intents for one explicit attempt."""

        self._require_explicit_occurrences()
        mission_id = _canonical_str(mission_id, "mission_id")
        occurrence_fields = self._occurrence_fields(occurrence)
        prepared: list[tuple[str, dict[str, Any]]] = []
        for intent in decision.event_intents:
            event_type = _canonical_str(intent.event_type, "intent.event_type")
            if event_type not in PHASE_INTENT:
                raise ValueError(f"{event_type!r} is not a decision-event intent")
            detached = _materialize_fields(intent.fields)
            if "occurrence" in detached:
                raise ValueError("decision intent fields cannot override occurrence")
            detached.update(_detach_plain(occurrence_fields))
            prepared.append((event_type, detached))
        if not prepared:
            return
        with self._lock:
            base_seq = self._sequences.get(mission_id, 0)
            built = [
                self._build_event_unlocked(
                    event_type, mission_id, base_seq + offset, fields
                )
                for offset, (event_type, fields) in enumerate(prepared, start=1)
            ]
            self._sequences[mission_id] = base_seq + len(prepared)
            self._events.extend(built)

    def record_observation(self, event_type: str, *, mission_id: str, **fields: Any) -> None:
        """Record a post-action observation. Only the adapter, after the action.

        Python may hash or validate keys supplied through ``**fields`` before
        this method is entered; those language-level callbacks are outside the
        recorder's control. Once inside, strings and fields are canonicalized
        without builtin-subclass callbacks and before recorder mutation. The
        actual recording delegates to :meth:`_stamp`, which a private subclass
        may override to observe every call on this path.
        """
        event_type = _canonical_str(event_type, "event_type")
        mission_id = _canonical_str(mission_id, "mission_id")
        if event_type not in PHASE_OBSERVATION:
            raise ValueError(f"{event_type!r} is not a post-action observation")
        self._stamp(event_type, mission_id, fields)

    def record_occurrence_observation(
        self,
        event_type: str,
        *,
        mission_id: str,
        occurrence: RuntimeOccurrence,
        **fields: Any,
    ) -> None:
        """Record a post-action observation for one explicit attempt."""

        self._require_explicit_occurrences()
        event_type = _canonical_str(event_type, "event_type")
        mission_id = _canonical_str(mission_id, "mission_id")
        if event_type not in PHASE_OBSERVATION:
            raise ValueError(f"{event_type!r} is not a post-action observation")
        detached = _materialize_fields(fields)
        if "occurrence" in detached:
            raise ValueError("observation fields cannot override occurrence")
        detached.update(self._occurrence_fields(occurrence))
        with self._lock:
            seq = self._sequences.get(mission_id, 0) + 1
            event = self._build_event_unlocked(
                event_type, mission_id, seq, detached
            )
            self._sequences[mission_id] = seq
            self._events.append(event)

    def max_recorded_attempt(
        self,
        *,
        mission_id: str,
        operation_id: str,
        occurrence_id: str,
    ) -> int:
        """Return the highest explicit attempt already recorded, or zero."""

        self._require_explicit_occurrences()
        mission_id = _canonical_str(mission_id, "mission_id")
        operation_id = _canonical_str(operation_id, "operation_id")
        occurrence_id = _canonical_str(occurrence_id, "occurrence_id")
        if not _RUNTIME_ID_RE.fullmatch(operation_id):
            raise ValueError("operation_id is not a valid runtime identifier")
        if not _RUNTIME_ID_RE.fullmatch(occurrence_id):
            raise ValueError("occurrence_id is not a valid runtime identifier")
        highest = 0
        with self._lock:
            for event in self._events:
                occurrence = event.get("occurrence")
                if (
                    event.get("mission_id") == mission_id
                    and isinstance(occurrence, Mapping)
                    and occurrence.get("operation_id") == operation_id
                    and occurrence.get("occurrence_id") == occurrence_id
                    and isinstance(occurrence.get("attempt"), int)
                ):
                    highest = max(highest, occurrence["attempt"])
        return highest

    def _snapshot_unlocked(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build a fully independent, deeply detached ``(producer, events)``
        snapshot. Does not itself acquire the lock — :meth:`stream` holds
        ``self._lock`` for this call's entire duration, so a concurrent
        ``record_decision``/``record_observation`` cannot commit while a
        snapshot is in progress. Split out from :meth:`stream` purely so tests
        can pause/observe a snapshot in progress while the lock is held;
        behavior is unchanged from having this inline in :meth:`stream`.

        Every nested value — ``producer`` (top-level and per-event),
        ``approver``, ``evidence_artifact``, ``share_categories``,
        ``depends_on``, and any other adapter-supplied field — is copied, not
        shared: mutating any part of a returned snapshot can never change what
        a later call to :meth:`stream` or :meth:`validate` returns, and can
        never corrupt this recorder's internal state.

        Each event's *fields* are detached individually — ``{k: _detach_plain(v)
        for k, v in event.items()}`` — rather than passing the whole event dict
        through :func:`_detach_plain` as one unit. An event is the recorder's
        own envelope, not itself a caller-supplied nested value: detaching it
        as one unit would silently consume one extra level of the depth budget
        for every field, so a field value accepted at record time (right at
        ``_DETACH_PLAIN_MAX_DEPTH``) could spuriously fail on read. Detaching
        per field reproduces exactly the depth budget each field's value was
        already validated against when it was recorded, so this can never raise.
        """
        producer_snapshot = _detach_plain(self._producer)
        events_snapshot = [{key: _detach_plain(value) for key, value in event.items()} for event in self._events]
        return producer_snapshot, events_snapshot

    def stream(self) -> dict[str, Any]:
        """Return an independent, deeply detached snapshot of the recorded stream.

        Acquires the lock, builds the snapshot via :meth:`_snapshot_unlocked`,
        and releases the lock before returning.
        """
        with self._lock:
            producer_snapshot, events_snapshot = self._snapshot_unlocked()
        stream = {
            "schema": RUNTIME_EVENTS_SCHEMA_ID,
            "schema_version": self._schema_version,
            "network_id": self._authorizer.network_id,
            "producer": producer_snapshot,
            "events": events_snapshot,
        }
        if self._occurrence_mode is not None:
            stream["occurrence_mode"] = self._occurrence_mode
        return stream

    def validate(self, *, events_root: Path | None = None) -> dict[str, Any]:
        """Validate the assembled stream against a detached thaw of the snapshot.

        Delegates the payload construction to :meth:`stream`, which acquires
        the lock, builds the deeply detached payload, and releases the lock
        before returning — so ``validate_runtime_events`` below always runs
        against an already-detached, already-lock-free snapshot, never while
        holding ``self._lock``.
        """
        from ..agentic_evidence import validate_runtime_events

        return validate_runtime_events(
            _thaw(self._authorizer._document),
            self._authorizer._composition,
            _thaw(self._authorizer._lock_payload),
            self.stream(),
            events_root=events_root,
        )
