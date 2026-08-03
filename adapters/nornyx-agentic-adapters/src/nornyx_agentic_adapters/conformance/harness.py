"""Shared, offline machinery every conformance suite builds on.

The contract fixture is resolved through :mod:`importlib.resources` against
this package, never through a repository-relative path. That is the property
that lets conformance run from an installed wheel outside every source root —
and therefore the property that makes a conformance result meaningful to a
consumer rather than only to this monorepo.

Nothing here opens a network, loads a credential, calls a model, or executes a
connector. Timestamps come from the contract-bound ``decision_at``, never a
wall clock, so repeated runs produce identical evidence.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import threading
from importlib import resources
from typing import Any, Iterator

import yaml

import nornyx.agentic as _agentic
from nornyx.agentic import (
    Authorizer,
    AuthorizationRequest,
    Decision,
    EvaluationContext,
    EvidenceRecorder,
    GovernanceRegistry,
    build_agentic_network_lock,
    compose_document_governance,
)

from .model import EvidenceValidation, OccurrenceSummary

#: The bound decision time for every conformance run. A fixed instant inside
#: the fixture's validity window; never ``now()``, so evidence is reproducible.
DECISION_AT = "2026-07-17T10:00:00Z"

#: One mission for the whole run, per ADR-0042 mission semantics.
MISSION_ID = "GOAL-001"

PRODUCER_ID = "nornyx-agentic-adapters-conformance"
PRODUCER_TYPE = "synthetic_harness"

FIXTURE_PACKAGE = "nornyx_agentic_adapters.conformance.fixtures"
FIXTURE_NAME = "conformance_network.nyx"

#: Identities declared by the bundled fixture.
RESEARCHER = "identity.researcher.local"
REVIEWER = "identity.reviewer.local"
#: ``researcher`` holds this; ``reviewer`` does not — the denial fixture.
READ_CAPABILITY = "read_governed_context"
PROPOSE_CAPABILITY = "propose_research_finding"
LOCAL_ZONE = "zone.local_governed"
EXTERNAL_ZONE = "zone.external_contract"

#: Event-type classification the kit owns outright.
#:
#: Deliberately declared here rather than imported from ``nornyx.agentic.authz``:
#: the core's ``PHASE_INTENT``/``PHASE_OBSERVATION`` sets are not part of the
#: frozen ``nornyx.agentic`` facade, and a shipped adapter must not depend on a
#: core internal. The adapter test suite cross-checks these two sets against the
#: core's own constants so drift is caught there, not in shipped code.
DECISION_EVENT_TYPES: frozenset[str] = frozenset(
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
OBSERVATION_EVENT_TYPES: frozenset[str] = frozenset(
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


def fixture_text() -> str:
    """Read the bundled contract fixture from this package's own resources."""
    return (
        resources.files(FIXTURE_PACKAGE)
        .joinpath(FIXTURE_NAME)
        .read_text(encoding="utf-8")
    )


def load_document() -> dict[str, Any]:
    return yaml.safe_load(fixture_text())


def build_authorizer(document: dict[str, Any] | None = None) -> Authorizer:
    """Compose, lock, and load an Authorizer over the bundled fixture."""
    document = load_document() if document is None else document
    composition = compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    lock = build_agentic_network_lock(document, composition)
    return Authorizer(document, composition, lock)


def build_context(authorizer: Authorizer) -> EvaluationContext:
    return EvaluationContext(
        decision_at=DECISION_AT,
        observed_subject_revision=authorizer.subject_revision,
    )


def build_recorder(authorizer: Authorizer, context: EvaluationContext) -> EvidenceRecorder:
    """A legacy-mode recorder, matching what the CrewAI adapter expects."""
    return EvidenceRecorder(
        authorizer, context, producer_id=PRODUCER_ID, producer_type=PRODUCER_TYPE
    )


def build_occurrence_recorder(
    authorizer: Authorizer, context: EvaluationContext
) -> EvidenceRecorder:
    """An explicit occurrence-aware recorder, as the LangGraph adapter requires."""
    return EvidenceRecorder.for_occurrences(
        authorizer, context, producer_id=PRODUCER_ID, producer_type=PRODUCER_TYPE
    )


class CountingAuthorizer:
    """Counts ``evaluate`` calls and forwards everything to the real Authorizer.

    Instrumentation only. Every call is delegated and the authoritative
    :class:`~nornyx.agentic.Decision` is returned unchanged, so a case measures
    what the adapter actually did rather than what a substitute would have done.
    The real :class:`~nornyx.agentic.Authorizer` — not this wrapper — is what
    the :class:`~nornyx.agentic.EvidenceRecorder` binds to.
    """

    def __init__(self, authorizer: Authorizer) -> None:
        self._authorizer = authorizer
        # Locked: LangGraph schedules parallel branches on a real thread pool.
        self._lock = threading.Lock()
        self.evaluations = 0

    def evaluate(
        self, request: AuthorizationRequest, *, context: EvaluationContext
    ) -> Decision:
        with self._lock:
            self.evaluations += 1
        return self._authorizer.evaluate(request, context=context)

    def resolve_identity(self, framework: str, agent_key: str) -> str:
        return self._authorizer.resolve_identity(framework, agent_key)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._authorizer, name)


class ExecutionCounter:
    """Counts how many times a protected action actually ran.

    Locked because LangGraph runs parallel branches on a real thread pool, so
    an unguarded increment could lose an update and report a count lower than
    what actually executed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.count = 0

    def bump(self) -> None:
        with self._lock:
            self.count += 1

    def run(self, result: Any = None, raises: BaseException | None = None) -> Any:
        self.bump()
        if raises is not None:
            raise raises
        return result


class NetworkGuard:
    """Blocks outbound and process-spawning operations during a guarded run.

    Loopback is permitted on every path that can express it —
    ``socket.socket.connect``, ``socket.create_connection`` and
    ``socket.getaddrinfo`` — because CrewAI's telemetry stack may touch it and
    reaches it through more than one of them. Anything naming a non-loopback
    host is blocked.

    Two counters, kept separate because they mean different things and a single
    number would misdescribe one of them:

    * ``outbound_attempts`` — blocked calls that named a non-loopback host.
    * ``process_attempts`` — blocked ``subprocess``/``os.system`` calls, which
      are local and involve no network at all.

    Both are disallowed during a conformance run and either fails it, but the
    report and the operator message say which actually happened.

    Not re-entrant across threads: two threads entering :meth:`active`
    concurrently would leak a patched module attribute. One guard per run.
    """

    _LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.outbound_attempts = 0
        self.process_attempts = 0

    @property
    def attempts(self) -> int:
        """Every blocked call, of either kind."""
        return self.outbound_attempts + self.process_attempts

    def _record_outbound(self) -> None:
        with self._lock:
            self.outbound_attempts += 1

    def _record_process(self) -> None:
        with self._lock:
            self.process_attempts += 1

    @classmethod
    def _is_loopback(cls, host: object) -> bool:
        return isinstance(host, str) and host in cls._LOOPBACK

    @contextlib.contextmanager
    def active(self) -> Iterator[NetworkGuard]:
        real_connect = socket.socket.connect
        real_create = socket.create_connection
        real_getaddrinfo = socket.getaddrinfo
        real_run, real_popen = subprocess.run, subprocess.Popen
        real_system = os.system

        def loopback_only(sock: socket.socket, address: Any) -> Any:
            host = address[0] if isinstance(address, tuple) else address
            if self._is_loopback(host):
                return real_connect(sock, address)
            self._record_outbound()
            raise AssertionError(f"external connection attempted: {address!r}")

        def loopback_create(address: Any, *args: Any, **kwargs: Any) -> Any:
            host = address[0] if isinstance(address, (tuple, list)) else address
            if self._is_loopback(host):
                return real_create(address, *args, **kwargs)
            self._record_outbound()
            raise AssertionError(f"external connection attempted: {address!r}")

        def loopback_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
            if self._is_loopback(host):
                return real_getaddrinfo(host, *args, **kwargs)
            self._record_outbound()
            raise AssertionError(f"external name resolution attempted: {host!r}")

        def no_subprocess(*_a: Any, **_k: Any) -> Any:
            self._record_process()
            raise AssertionError("process execution attempted during conformance")

        # No escape hatch: a permitted child process would be entirely
        # unguarded, and a count of attempts blocked in this process could then
        # say nothing about what that child did.
        socket.socket.connect = loopback_only  # type: ignore[method-assign]
        socket.create_connection = loopback_create  # type: ignore[assignment]
        socket.getaddrinfo = loopback_getaddrinfo  # type: ignore[assignment]
        subprocess.run = no_subprocess  # type: ignore[assignment]
        subprocess.Popen = no_subprocess  # type: ignore[assignment]
        os.system = no_subprocess  # type: ignore[assignment]
        try:
            yield self
        finally:
            socket.socket.connect = real_connect  # type: ignore[method-assign]
            socket.create_connection = real_create  # type: ignore[assignment]
            socket.getaddrinfo = real_getaddrinfo  # type: ignore[assignment]
            subprocess.run = real_run  # type: ignore[assignment]
            subprocess.Popen = real_popen  # type: ignore[assignment]
            os.system = real_system  # type: ignore[assignment]


def event_types(recorder: EvidenceRecorder) -> list[str]:
    return [event["event_type"] for event in recorder.stream()["events"]]


def decision_event_types(recorder: EvidenceRecorder) -> tuple[str, ...]:
    """Decision-event types in exactly the order the recorder committed them.

    Order is preserved deliberately. An ordering claim cannot be substantiated
    from a sorted list, and sorting would hide a regression that moved a
    recording relative to the protected action.
    """
    return tuple(e for e in event_types(recorder) if e in DECISION_EVENT_TYPES)


def observation_event_types(recorder: EvidenceRecorder) -> tuple[str, ...]:
    return tuple(e for e in event_types(recorder) if e in OBSERVATION_EVENT_TYPES)


def normalized(types: tuple[str, ...]) -> tuple[str, ...]:
    """Sorted-unique form, for the one situation that needs it.

    Only for paths where a framework's own executor decides how many times a
    governed call repeats, which would otherwise make the report
    non-reproducible. Every use must be accompanied by a stated reason.
    """
    return tuple(sorted(set(types)))


def decision_precedes_observations(recorder: EvidenceRecorder) -> bool | None:
    """Whether every recorded observation followed at least one decision event.

    Returns ``None`` when the stream contains no observation at all. There is
    no ordering to report in that case, and answering ``True`` would affirm an
    ordering property for a case that recorded nothing — including the bypass
    controls, which by design record nothing.

    Note the narrow scope: this is about the order of *recorded events*, not
    about when the protected action ran. The action-failure and retry cases are
    what pin the observation to the action.
    """
    recorded = event_types(recorder)
    if not any(event_type in OBSERVATION_EVENT_TYPES for event_type in recorded):
        return None
    seen_decision = False
    for event_type in recorded:
        if event_type in DECISION_EVENT_TYPES:
            seen_decision = True
        elif event_type in OBSERVATION_EVENT_TYPES and not seen_decision:
            return False
    return True


def validate_evidence(recorder: EvidenceRecorder) -> EvidenceValidation:
    """Schema validity and binding consistency of the recorded stream.

    Never a claim that the recorded events are true — only that they are
    well-formed and consistently bound to the contract, lock, and revision.

    An empty stream is ``NOT_APPLICABLE`` rather than ``PASS``: "the evidence
    validated" is a positive statement, and there is nothing to make it about
    when nothing was recorded. Reporting ``PASS`` there would let a bypass
    control, which by design produces no evidence, look like it produced good
    evidence.
    """
    if not recorder.stream()["events"]:
        return EvidenceValidation.NOT_APPLICABLE
    try:
        report = recorder.validate()
    except Exception:  # noqa: BLE001 - a failed validation is a conformance result
        return EvidenceValidation.FAIL
    return (
        EvidenceValidation.PASS
        if report.get("status") == "pass"
        else EvidenceValidation.FAIL
    )


def evidence_diagnostics(recorder: EvidenceRecorder) -> tuple[str, ...]:
    """The sorted unique diagnostic codes the evidence validator reported.

    A case that documents a known non-validating path must assert *which*
    failure it is seeing. Without this, any future evidence regression on that
    path — a broken digest, a stale lock, a schema-invalid event — would
    produce the same bare ``fail`` and the same reassuring prose, and would be
    structurally invisible.
    """
    try:
        report = recorder.validate()
    except Exception:  # noqa: BLE001
        return ("VALIDATION_RAISED",)
    codes = {
        str(item.get("code"))
        for item in report.get("diagnostics", [])
        if isinstance(item, dict) and item.get("code")
    }
    return tuple(sorted(codes))


def summarize_occurrences(recorder: EvidenceRecorder) -> OccurrenceSummary:
    """Determinism-safe occurrence facts.

    The raw ``occurrence_id`` values are deliberately dropped: LangGraph mints
    a fresh ``task_id`` per process, so the ids are not reproducible even
    though the structure they produce is. ``collided`` reports whether two
    different logical operations were recorded under one occurrence id, which
    is the failure this summary exists to detect.
    """
    per_occurrence: dict[str, set[str]] = {}
    attempts: set[int] = set()
    for event in recorder.stream()["events"]:
        occurrence = event.get("occurrence")
        if not isinstance(occurrence, dict):
            continue
        occurrence_id = str(occurrence.get("occurrence_id"))
        per_occurrence.setdefault(occurrence_id, set()).add(
            str(occurrence.get("operation_id"))
        )
        attempt = occurrence.get("attempt")
        if isinstance(attempt, int):
            attempts.add(attempt)
    return OccurrenceSummary(
        distinct_occurrences=len(per_occurrence),
        attempts=tuple(sorted(attempts)),
        collided=any(len(ops) > 1 for ops in per_occurrence.values()),
    )


def nornyx_version() -> str:
    version = getattr(_agentic, "__version__", None)
    if isinstance(version, str) and version:
        return version
    import nornyx

    return str(getattr(nornyx, "__version__", "unknown"))


def spi_version() -> str:
    return str(_agentic.SPI_VERSION)


def python_version() -> str:
    return "{}.{}.{}".format(*sys.version_info[:3])


__all__ = [
    "DECISION_AT",
    "DECISION_EVENT_TYPES",
    "EXTERNAL_ZONE",
    "FIXTURE_NAME",
    "FIXTURE_PACKAGE",
    "LOCAL_ZONE",
    "MISSION_ID",
    "OBSERVATION_EVENT_TYPES",
    "PRODUCER_ID",
    "PRODUCER_TYPE",
    "PROPOSE_CAPABILITY",
    "READ_CAPABILITY",
    "RESEARCHER",
    "REVIEWER",
    "CountingAuthorizer",
    "ExecutionCounter",
    "NetworkGuard",
    "build_authorizer",
    "build_context",
    "build_occurrence_recorder",
    "build_recorder",
    "decision_event_types",
    "decision_precedes_observations",
    "event_types",
    "evidence_diagnostics",
    "normalized",
    "fixture_text",
    "load_document",
    "nornyx_version",
    "observation_event_types",
    "python_version",
    "spi_version",
    "summarize_occurrences",
    "validate_evidence",
]
