"""ADR-0039 M2-D compatibility and baseline-closure corpus."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any
import warnings

import pytest

from nornyx.agentic import (
    Authorizer,
    AuthorizerState,
    CapabilityRequest,
    DecisionCode,
    EvaluationContext,
    EvidenceRecorder,
    SPI_VERSION,
    build_agentic_network_lock,
    compose_document_governance,
    load_nyx,
    registry_for_contract,
    validate_runtime_events,
)
from nornyx.agentic_artifacts import _build_agentic_network_lock


ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS = ROOT / "integrations"
ADAPTER_SRC = ROOT / "adapters" / "nornyx-agentic-adapters" / "src"
SUPPORT_CONTRACT = ROOT / "examples" / "agentic_network_support" / "support_network.nyx"
AS_OF = "2026-07-17T00:00:00Z"

if str(INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS))
if str(ADAPTER_SRC) not in sys.path:
    sys.path.insert(0, str(ADAPTER_SRC))

from nornyx_reference_adapters.crewai_adapter import (  # noqa: E402
    CrewAIGovernanceAdapter,
)
from nornyx_reference_adapters.governance_kernel import (  # noqa: E402
    _APPROVER_ACTOR_TYPES,
    _RUNTIME_EVENT_ID_MAX_LENGTH,
    _RUNTIME_EVENT_ID_PATTERN,
    DeterministicClock,
    GovernanceKernel,
    GovernanceViolation,
)
from nornyx_reference_adapters.langgraph_adapter import (  # noqa: E402
    LangGraphGovernanceAdapter,
)
from nornyx_reference_adapters.local_harness import DuckAgent  # noqa: E402
from nornyx_agentic_adapters.enforcement import enforce  # noqa: E402
from nornyx_agentic_adapters.errors import AdapterDenied  # noqa: E402


@pytest.fixture(scope="module")
def controls() -> tuple[dict[str, Any], Any]:
    document = load_nyx(SUPPORT_CONTRACT)
    composition = compose_document_governance(
        document,
        registry=registry_for_contract(SUPPORT_CONTRACT),
    )
    assert composition is not None
    return document, composition


def _kernel(
    controls: tuple[dict[str, Any], Any],
    *,
    framework: str = "crewai",
    schema_version: str = "1.1",
    document: dict[str, Any] | None = None,
) -> GovernanceKernel:
    original, composition = controls
    payload = deepcopy(document if document is not None else original)
    if schema_version == "1.0":
        lock = _build_agentic_network_lock(
            payload,
            composition,
            runtime_events_schema_version="1.0",
        )
    else:
        lock = build_agentic_network_lock(payload, composition)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return GovernanceKernel(
            payload,
            composition,
            lock,
            framework=framework,
            clock=DeterministicClock(AS_OF),
        )


def _event_types(kernel: GovernanceKernel) -> list[str]:
    return [event["event_type"] for event in kernel.events_payload()["events"]]


def test_spi_and_legacy_public_signatures_are_pinned() -> None:
    # The shim consumes the public Authorizer construction-state SPI, first
    # published in Nornyx 1.11.0 as SPI 1.2.
    assert SPI_VERSION == "1.2"
    signatures = {
        "resolve_identity": "(self, agent_key: 'str') -> 'str'",
        "check_capability": (
            "(self, identity_id: 'str', capability: 'str', *, "
            "mission_id: 'str') -> 'dict[str, Any]'"
        ),
        "invoke_tool": (
            "(self, identity_id: 'str', capability: 'str', *, "
            "mission_id: 'str') -> 'dict[str, Any]'"
        ),
        "request_delegation": (
            "(self, delegation_id: 'str', *, mission_id: 'str') -> 'None'"
        ),
        "request_handoff": "(self, handoff_id: 'str', *, mission_id: 'str') -> 'None'",
        "complete_handoff": "(self, handoff_id: 'str', *, mission_id: 'str') -> 'None'",
        "require_human_approval": (
            "(self, approval_record: 'Mapping[str, Any]', *, mission_id: 'str', "
            "actor_ref: 'str', approval_ref: 'str' = "
            "'agentic_network_authority') -> 'None'"
        ),
        "record_zone_crossing": (
            "(self, identity_id: 'str', source_zone: 'str', target_zone: 'str', *, "
            "mission_id: 'str', approval_ref: 'str | None' = None) -> 'None'"
        ),
        "record_data_shared": (
            "(self, identity_id: 'str', target_id: 'str', categories: 'list[str]', "
            "*, mission_id: 'str', source_zone: 'str', target_zone: 'str') -> 'None'"
        ),
        "events_payload": "(self) -> 'dict[str, Any]'",
        "write_events": "(self, path: 'str | Path') -> 'Path'",
    }
    for name, expected in signatures.items():
        assert str(inspect.signature(getattr(GovernanceKernel, name))) == expected


def test_deprecation_warns_once_and_does_not_change_denial(
    controls: tuple[dict[str, Any], Any],
) -> None:
    document, composition = controls
    lock = build_agentic_network_lock(document, composition)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        kernel = GovernanceKernel(
            document,
            composition,
            lock,
            framework="crewai",
            clock=DeterministicClock(AS_OF),
        )
        with pytest.raises(GovernanceViolation) as excinfo:
            kernel.check_capability(
                "identity.refund_agent",
                "escalate_high_value_refund",
                mission_id="M.warning",
            )
    matching = [item for item in caught if issubclass(item.category, DeprecationWarning)]
    assert len(matching) == 1
    assert "nornyx-agentic-adapters" in str(matching[0].message)
    assert "nornyx.agentic" in str(matching[0].message)
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"


def test_every_preserved_method_allows_and_stream_validates(
    controls: tuple[dict[str, Any], Any], tmp_path: Path
) -> None:
    document, composition = controls
    kernel = _kernel(controls)
    coordinator = kernel.resolve_identity("support_coordinator")
    refund = kernel.resolve_identity("refund_agent")
    escalation = kernel.resolve_identity("escalation_agent")

    allowed = kernel.check_capability(
        coordinator,
        "classify_support_request",
        mission_id="M.capability",
    )
    assert allowed["event_type"] == "capability_allowed"
    invoked = kernel.invoke_tool(
        coordinator,
        "classify_support_request",
        mission_id="M.invoke",
    )
    assert invoked["event_type"] == "tool_invoked"
    kernel.request_delegation(
        "delegation.refund_proposal",
        mission_id="M.delegation",
    )
    delegated = kernel.check_capability(
        refund,
        "propose_refund_under_limit",
        mission_id="M.delegated",
    )
    assert delegated["delegation_ref"] == "delegation.refund_proposal"
    kernel.request_handoff(
        "handoff.high_value_escalation",
        mission_id="M.handoff",
    )
    kernel.complete_handoff(
        "handoff.high_value_escalation",
        mission_id="M.handoff",
    )
    kernel.require_human_approval(
        {
            "role": "network_governance_owner",
            "actor_type": "human",
            "granted": True,
        },
        mission_id="M.approval",
        actor_ref=escalation,
    )
    kernel.record_zone_crossing(
        refund,
        "zone.support_internal",
        "zone.customer_channel",
        mission_id="M.crossing",
        approval_ref="agentic_network_authority",
    )
    kernel.record_data_shared(
        coordinator,
        refund,
        ["classification"],
        mission_id="M.share",
        source_zone="zone.support_internal",
        target_zone="zone.support_internal",
    )

    report = validate_runtime_events(
        document,
        composition,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass", report["diagnostics"]
    target = tmp_path / "evidence" / "events.json"
    assert kernel.write_events(target) == target
    assert target.is_file()


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (
            lambda k: k.resolve_identity("not-bound"),
            "AN_ADAPTER_IDENTITY_UNKNOWN",
        ),
        (
            lambda k: k.check_capability(
                "identity.support_coordinator", "missing", mission_id="M.deny"
            ),
            "AN_ADAPTER_CAPABILITY_UNKNOWN",
        ),
        (
            lambda k: k.check_capability(
                "identity.refund_agent",
                "escalate_high_value_refund",
                mission_id="M.deny",
            ),
            "AN_ADAPTER_CAPABILITY_DENIED",
        ),
        (
            lambda k: k.request_delegation("missing", mission_id="M.deny"),
            "AN_ADAPTER_DELEGATION_UNKNOWN",
        ),
        (
            lambda k: k.request_handoff("missing", mission_id="M.deny"),
            "AN_ADAPTER_HANDOFF_UNKNOWN",
        ),
        (
            lambda k: k.require_human_approval(
                {
                    "role": "network_governance_owner",
                    "actor_type": "model",
                    "granted": True,
                },
                mission_id="M.deny",
                actor_ref="identity.escalation_agent",
            ),
            "AN_ADAPTER_APPROVAL_NON_HUMAN",
        ),
        (
            lambda k: k.require_human_approval(
                {"role": "unknown", "actor_type": "human", "granted": True},
                mission_id="M.deny",
                actor_ref="identity.escalation_agent",
            ),
            "AN_ADAPTER_APPROVAL_ROLE_INVALID",
        ),
        (
            lambda k: k.require_human_approval(
                {
                    "role": "network_governance_owner",
                    "actor_type": "human",
                    "granted": False,
                },
                mission_id="M.deny",
                actor_ref="identity.escalation_agent",
            ),
            "AN_ADAPTER_APPROVAL_NOT_GRANTED",
        ),
        (
            lambda k: k.record_zone_crossing(
                "identity.refund_agent",
                "zone.support_internal",
                "zone.customer_channel",
                mission_id="M.deny",
            ),
            "AN_ADAPTER_CROSSING_APPROVAL_REQUIRED",
        ),
        (
            lambda k: k.record_zone_crossing(
                "identity.refund_agent",
                "zone.customer_channel",
                "zone.support_internal",
                mission_id="M.deny",
            ),
            "AN_ADAPTER_ZONE_CROSSING_DENIED",
        ),
        (
            lambda k: k.record_data_shared(
                "identity.support_coordinator",
                "identity.refund_agent",
                ["secrets"],
                mission_id="M.deny",
                source_zone="zone.support_internal",
                target_zone="zone.support_internal",
            ),
            "AN_ADAPTER_SENSITIVE_SHARING",
        ),
        (
            lambda k: k.record_data_shared(
                "identity.support_coordinator",
                "identity.refund_agent",
                ["undeclared"],
                mission_id="M.deny",
                source_zone="zone.support_internal",
                target_zone="zone.support_internal",
            ),
            "AN_ADAPTER_SHARE_NOT_ALLOWED",
        ),
    ],
)
def test_stable_legacy_denial_codes(
    controls: tuple[dict[str, Any], Any],
    operation: Any,
    expected: str,
) -> None:
    kernel = _kernel(controls)
    with pytest.raises(GovernanceViolation) as excinfo:
        operation(kernel)
    assert excinfo.value.code == expected


def test_inactive_delegation_and_handoff_authority_codes(
    controls: tuple[dict[str, Any], Any],
) -> None:
    original, _ = controls
    inactive_doc = deepcopy(original)
    inactive_doc["agentic_network"]["delegations"][0]["status"] = "suspended"
    inactive = _kernel(controls, document=inactive_doc)
    with pytest.raises(GovernanceViolation) as excinfo:
        inactive.request_delegation(
            "delegation.refund_proposal",
            mission_id="M.inactive",
        )
    assert excinfo.value.code == "AN_ADAPTER_DELEGATION_INACTIVE"

    no_authority_doc = deepcopy(original)
    no_authority_doc["agentic_network"]["handoffs"][0][
        "required_capability_refs"
    ] = ["produce_customer_safe_response"]
    no_authority = _kernel(controls, document=no_authority_doc)
    with pytest.raises(GovernanceViolation) as excinfo:
        no_authority.request_handoff(
            "handoff.high_value_escalation",
            mission_id="M.handoff-deny",
        )
    assert excinfo.value.code == "AN_ADAPTER_HANDOFF_AUTHORITY"


def test_crewai_callable_order_exactly_once_allow_and_zero_on_deny(
    controls: tuple[dict[str, Any], Any],
) -> None:
    kernel = _kernel(controls)
    adapter = CrewAIGovernanceAdapter(kernel)
    timeline: list[str] = []
    original_observation = kernel._record_observation

    def observe(event_type: str, mission_id: str, **fields: Any) -> dict[str, Any]:
        timeline.append(f"observe:{event_type}")
        return original_observation(event_type, mission_id, **fields)

    kernel._record_observation = observe  # type: ignore[method-assign]
    guarded = adapter.guarded_task(
        DuckAgent("support_coordinator"),
        "classify_support_request",
        lambda: timeline.append("work") or "done",
        mission_id="M.order",
    )
    assert guarded() == "done"
    assert timeline == ["work", "observe:tool_invoked"]
    assert _event_types(kernel) == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]

    denied_kernel = _kernel(controls)
    denied_adapter = CrewAIGovernanceAdapter(denied_kernel)
    calls = 0

    def forbidden() -> None:
        nonlocal calls
        calls += 1

    blocked = denied_adapter.guarded_task(
        DuckAgent("refund_agent"),
        "escalate_high_value_refund",
        forbidden,
        mission_id="M.denied-order",
    )
    with pytest.raises(GovernanceViolation) as excinfo:
        blocked()
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"
    assert calls == 0
    assert "tool_invoked" not in _event_types(denied_kernel)


def test_runtime_failure_is_recorded_after_the_callable_raises(
    controls: tuple[dict[str, Any], Any],
) -> None:
    kernel = _kernel(controls, framework="langgraph")
    adapter = LangGraphGovernanceAdapter(kernel)
    timeline: list[str] = []
    original_observation = kernel._record_observation

    def observe(event_type: str, mission_id: str, **fields: Any) -> dict[str, Any]:
        timeline.append(f"observe:{event_type}")
        return original_observation(event_type, mission_id, **fields)

    kernel._record_observation = observe  # type: ignore[method-assign]

    def fail(_state: dict) -> dict:
        timeline.append("work")
        raise RuntimeError("bounded failure")

    node = adapter.guard_node(
        "support_coordinator",
        "classify_support_request",
        fail,
        mission_id="M.failure",
    )
    with pytest.raises(RuntimeError, match="bounded failure"):
        node({})
    assert timeline == ["work", "observe:runtime_failed"]
    assert _event_types(kernel)[-1] == "runtime_failed"
    assert "tool_invoked" not in _event_types(kernel)
    assert kernel._recorder.validate()["status"] == "pass"


def test_one_legacy_tool_call_evaluates_once_and_emits_no_duplicates(
    controls: tuple[dict[str, Any], Any],
) -> None:
    kernel = _kernel(controls)
    authoritative = kernel._authorizer

    class CountingAuthorizer:
        def __init__(self) -> None:
            self.calls = 0

        def evaluate(self, request: Any, *, context: EvaluationContext) -> Any:
            self.calls += 1
            return authoritative.evaluate(request, context=context)

        def resolve_identity(self, framework: str, agent_key: str) -> str:
            return authoritative.resolve_identity(framework, agent_key)

    counting = CountingAuthorizer()
    kernel._authorizer = counting  # type: ignore[assignment]
    kernel.invoke_tool(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.single",
    )
    assert counting.calls == 1
    assert _event_types(kernel) == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    assert len({event["event_id"] for event in kernel.events_payload()["events"]}) == 3


@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
def test_runtime_events_10_and_11_legacy_modes_validate(
    controls: tuple[dict[str, Any], Any], schema_version: str
) -> None:
    document, composition = controls
    kernel = _kernel(controls, schema_version=schema_version)
    kernel.invoke_tool(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id=f"M.schema-{schema_version}",
    )
    stream = kernel.events_payload()
    assert stream["schema_version"] == schema_version
    if schema_version == "1.0":
        assert "occurrence_mode" not in stream
    else:
        assert stream["occurrence_mode"] == "legacy"
    assert all("occurrence" not in event for event in stream["events"])
    report = validate_runtime_events(document, composition, kernel.lock_payload, stream)
    assert report["status"] == "pass", report["diagnostics"]


def test_legacy_and_supported_foundation_are_semantically_equivalent(
    controls: tuple[dict[str, Any], Any],
) -> None:
    document, composition = controls
    lock = build_agentic_network_lock(document, composition)
    context = EvaluationContext(AS_OF, document["agentic_network"]["subject_revision"])

    legacy = _kernel(controls)
    legacy_result = CrewAIGovernanceAdapter(legacy).guarded_task(
        DuckAgent("support_coordinator"),
        "classify_support_request",
        lambda: "same",
        mission_id="M.equivalent",
    )()

    authorizer = Authorizer(document, composition, lock)
    recorder = EvidenceRecorder(authorizer, context, producer_id="supported")
    supported_result = enforce(
        authorizer,
        CapabilityRequest(
            "identity.support_coordinator",
            "classify_support_request",
        ),
        context=context,
        recorder=recorder,
        mission_id="M.equivalent",
        action=lambda: "same",
    )
    recorder.record_observation(
        "tool_invoked",
        mission_id="M.equivalent",
        actor_ref="identity.support_coordinator",
        capability_ref="classify_support_request",
    )
    assert legacy_result == supported_result == "same"
    assert _event_types(legacy) == [
        event["event_type"] for event in recorder.stream()["events"]
    ]

    denied_legacy = _kernel(controls)
    with pytest.raises(GovernanceViolation) as legacy_exc:
        denied_legacy.check_capability(
            "identity.refund_agent",
            "escalate_high_value_refund",
            mission_id="M.equivalent-deny",
        )
    denied_recorder = EvidenceRecorder(authorizer, context, producer_id="supported")
    with pytest.raises(AdapterDenied) as supported_exc:
        enforce(
            authorizer,
            CapabilityRequest(
                "identity.refund_agent",
                "escalate_high_value_refund",
            ),
            context=context,
            recorder=denied_recorder,
            mission_id="M.equivalent-deny",
            action=lambda: pytest.fail("denied callable executed"),
        )
    assert legacy_exc.value.code == "AN_ADAPTER_CAPABILITY_DENIED"
    assert supported_exc.value.decision.code is DecisionCode.CAPABILITY_DENIED
    assert _event_types(denied_legacy) == [
        event["event_type"] for event in denied_recorder.stream()["events"]
    ]


def test_hostile_or_malformed_inputs_fail_before_authorization_or_side_effect(
    controls: tuple[dict[str, Any], Any],
) -> None:
    kernel = _kernel(controls)
    authoritative = kernel._authorizer

    class CountingAuthorizer:
        calls = 0

        def evaluate(self, request: Any, *, context: EvaluationContext) -> Any:
            self.calls += 1
            return authoritative.evaluate(request, context=context)

        def resolve_identity(self, framework: str, agent_key: str) -> str:
            return authoritative.resolve_identity(framework, agent_key)

    counting = CountingAuthorizer()
    kernel._authorizer = counting  # type: ignore[assignment]
    work_calls = 0

    def work() -> None:
        nonlocal work_calls
        work_calls += 1

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel._execute_tool_callable(
            "identity.support_coordinator",
            "classify_support_request",
            work,
            mission_id=[],  # type: ignore[arg-type]
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counting.calls == 0
    assert work_calls == 0
    assert kernel.events_payload()["events"] == []

    with pytest.raises(GovernanceViolation) as excinfo:
        CrewAIGovernanceAdapter(kernel).guarded_task(
            DuckAgent("support_coordinator"),
            "classify_support_request",
            None,  # type: ignore[arg-type]
            mission_id="M.bad-callable",
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counting.calls == 0


def test_offline_flow_and_public_import_boundary(
    controls: tuple[dict[str, Any], Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("compatibility shim attempted external IO")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    kernel = _kernel(controls)
    kernel.invoke_tool(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.offline",
    )

    source = (
        INTEGRATIONS / "nornyx_reference_adapters" / "governance_kernel.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    nornyx_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and isinstance(node.module, str)
        and node.module.startswith("nornyx")
    }
    assert nornyx_imports == {"nornyx.agentic"}
    assert "crewai" not in source.lower()
    assert "langgraph" not in source.lower()


# --------------------------------------------------------------------------
# SPI 1.2 remediation: the shim's only source of truth is Authorizer.state.
# --------------------------------------------------------------------------

# Authorizer internals the shim must never touch. Reading any of these would
# reintroduce a private, second interpretation of validated construction state.
_FORBIDDEN_AUTHORIZER_PRIVATE_ATTRS = frozenset(
    {
        "_approvals",
        "_capabilities",
        "_composition",
        "_delegations",
        "_document",
        "_gates",
        "_handoffs",
        "_identities",
        "_lock_payload",
        "_memberships",
        "_network",
        "_revocations",
        "_state",
        "_zones",
    }
)

_SHIM_SOURCES = (
    "governance_kernel.py",
    "crewai_adapter.py",
    "langgraph_adapter.py",
)


def _shim_source(name: str) -> str:
    return (INTEGRATIONS / "nornyx_reference_adapters" / name).read_text(encoding="utf-8")


def test_shim_never_reads_authorizer_private_state() -> None:
    """Static guard: no shim module may read a private Authorizer attribute.

    This fails loudly if a future edit reaches around ``Authorizer.state`` back
    into Authorizer internals.
    """

    offenders: list[str] = []
    for name in _SHIM_SOURCES:
        tree = ast.parse(_shim_source(name))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if node.attr not in _FORBIDDEN_AUTHORIZER_PRIVATE_ATTRS:
                continue
            # ``self._state`` is the shim's own bound AuthorizerState reference,
            # not a read of Authorizer internals.
            value = node.value
            if (
                node.attr == "_state"
                and isinstance(value, ast.Name)
                and value.id == "self"
            ):
                continue
            offenders.append(f"{name}:{node.lineno} -> .{node.attr}")
    assert offenders == [], f"shim reads private Authorizer state: {offenders}"


def test_shim_binds_the_public_authorizer_state_object(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """The bound state is exactly the Authorizer's own public state object."""

    kernel = _kernel(controls)
    assert isinstance(kernel._state, AuthorizerState)
    assert kernel._state is kernel._authorizer.state
    # Public digests are the state's digests, not independently recomputed.
    assert kernel.contract_digest == kernel._authorizer.state.contract_digest
    assert kernel.lock_digest == kernel._authorizer.state.network_lock_digest


def test_compatibility_projections_equal_public_state_at_construction(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """Every legacy projection equals the corresponding AuthorizerState data."""

    kernel = _kernel(controls)
    state = kernel._authorizer.state

    assert kernel.document == state.document
    assert kernel.lock_payload == state.lock_payload
    assert kernel.network == state.document["agentic_network"]
    assert [req.id for req in kernel.composition.approval_requirements] == [
        req.id for req in state.composition.approval_requirements
    ]
    assert kernel.contract_digest == state.contract_digest
    assert kernel.lock_digest == state.network_lock_digest


def test_projections_are_read_only_and_detached(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """A projection cannot be reassigned, and mutating one changes nothing."""

    kernel = _kernel(controls)
    baseline_document = kernel.document
    baseline_lock = kernel.lock_payload
    baseline_digest = kernel.contract_digest
    baseline_lock_digest = kernel.lock_digest

    # Non-authoritative projections are read-only: they cannot be swapped for a
    # caller-controlled second source of truth.
    for attribute in ("document", "composition", "lock_payload", "network"):
        with pytest.raises(AttributeError):
            setattr(kernel, attribute, {"tampered": True})

    # Each access is a fresh detached copy.
    first = kernel.document
    second = kernel.document
    assert first is not second

    first["agent_identities"] = []
    first["agentic_network"]["subject_revision"] = "tampered"
    mutated_lock = kernel.lock_payload
    mutated_lock.clear()
    mutated_network = kernel.network
    mutated_network["handoffs"] = []

    # The composition projection satisfies the same guarantee by the stronger
    # branch: its requirement sequence is a tuple, so mutation is impossible.
    mutated_composition = kernel.composition
    assert isinstance(mutated_composition.approval_requirements, tuple)
    with pytest.raises(AttributeError):
        mutated_composition.approval_requirements.clear()  # type: ignore[attr-defined]

    # Neither the Authorizer nor any later projection moved.
    assert kernel.document == baseline_document
    assert kernel.lock_payload == baseline_lock
    assert kernel.contract_digest == baseline_digest
    assert kernel.lock_digest == baseline_lock_digest
    assert kernel._authorizer.state.document == baseline_document
    assert kernel._authorizer.state.contract_digest == baseline_digest
    assert kernel.composition.approval_requirements

    # And a decision still succeeds on the untouched validated state.
    kernel.check_capability(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.projection-mutation",
    )


def test_caller_owned_inputs_cannot_reach_the_kernel_after_construction(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """Mutating the caller's own structures cannot alter any later outcome."""

    original, composition = controls
    document = deepcopy(original)
    lock = build_agentic_network_lock(document, composition)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        kernel = GovernanceKernel(
            document,
            composition,
            lock,
            framework="crewai",
            clock=DeterministicClock(AS_OF),
        )

    baseline_document = kernel.document
    baseline_digest = kernel.contract_digest
    baseline_lock_digest = kernel.lock_digest
    baseline_requirements = [req.id for req in kernel.composition.approval_requirements]

    # Hostile post-construction mutation of every caller-supplied structure.
    document["agent_identities"] = []
    document["agentic_network"]["handoffs"] = []
    document["agentic_network"]["network_gates"] = []
    document["agentic_network"]["subject_revision"] = "tampered"
    lock.clear()

    # Projections, digests and approval data are unchanged.
    assert kernel.document == baseline_document
    assert kernel.contract_digest == baseline_digest
    assert kernel.lock_digest == baseline_lock_digest
    assert [
        req.id for req in kernel.composition.approval_requirements
    ] == baseline_requirements

    # Decisions are unchanged: an allow still allows...
    kernel.check_capability(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.caller-mutation",
    )
    # ...a denial still denies...
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.check_capability(
            "identity.refund_agent",
            "escalate_high_value_refund",
            mission_id="M.caller-mutation-deny",
        )
    assert excinfo.value.code == "AN_ADAPTER_CAPABILITY_DENIED"
    # ...and approval evaluation still rejects a non-human approver.
    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {
                "role": "network_governance_owner",
                "actor_type": "model",
                "granted": True,
            },
            mission_id="M.caller-mutation-approval",
            actor_ref="identity.escalation_agent",
        )
    assert excinfo.value.code == "AN_ADAPTER_APPROVAL_NON_HUMAN"

    # The emitted evidence still validates against the bound lock.
    report = validate_runtime_events(
        baseline_document,
        kernel.composition,
        kernel.lock_payload,
        kernel.events_payload(),
    )
    assert report["status"] == "pass", report["diagnostics"]


def test_no_split_brain_between_decisions_projections_and_digests(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """Decisions, compatibility data, and digest reporting share one state."""

    original, _ = controls
    # A materially different contract: one delegation suspended.
    divergent = deepcopy(original)
    divergent["agentic_network"]["delegations"][0]["status"] = "suspended"

    baseline = _kernel(controls)
    divergent_kernel = _kernel(controls, document=divergent)

    # Distinct validated states produce distinct digests...
    assert baseline.contract_digest != divergent_kernel.contract_digest
    assert baseline.lock_digest != divergent_kernel.lock_digest

    # ...each kernel's projection agrees with its own Authorizer, not the other.
    assert divergent_kernel.document == divergent_kernel._authorizer.state.document
    assert divergent_kernel.document != baseline.document
    assert divergent_kernel.network["delegations"][0]["status"] == "suspended"
    assert baseline.network["delegations"][0]["status"] != "suspended"

    # ...and the decision follows the same state the projection reports.
    with pytest.raises(GovernanceViolation) as excinfo:
        divergent_kernel.request_delegation(
            "delegation.refund_proposal",
            mission_id="M.split-brain",
        )
    assert excinfo.value.code == "AN_ADAPTER_DELEGATION_INACTIVE"
    baseline.request_delegation(
        "delegation.refund_proposal",
        mission_id="M.split-brain",
    )


def test_from_local_controls_loads_once_and_never_recomposes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assured path performs exactly one load and no second composition."""

    import nornyx_reference_adapters.governance_kernel as shim

    # The shim must not bind any second read/composition/digest entry point.
    for name in (
        "load_nyx",
        "compose_document_governance",
        "load_agentic_network_lock",
        "registry_for_contract",
        "contract_digest",
        "agentic_network_lock_digest",
    ):
        assert not hasattr(shim, name), (
            f"the shim must not bind {name}; Authorizer.state is the only source"
        )

    loads = 0
    real_load_authorizer = shim.load_authorizer

    def counting_load_authorizer(*args: Any, **kwargs: Any) -> Any:
        nonlocal loads
        loads += 1
        return real_load_authorizer(*args, **kwargs)

    monkeypatch.setattr(shim, "load_authorizer", counting_load_authorizer)

    document = load_nyx(SUPPORT_CONTRACT)
    composition = compose_document_governance(
        document,
        registry=registry_for_contract(SUPPORT_CONTRACT),
    )
    lock_path = tmp_path / "agentic_network.lock.json"
    lock_path.write_text(
        json.dumps(build_agentic_network_lock(document, composition), sort_keys=True),
        encoding="utf-8",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        kernel = GovernanceKernel.from_local_controls(
            SUPPORT_CONTRACT,
            lock_path,
            framework="crewai",
            as_of=AS_OF,
        )
    assert loads == 1
    assert (
        sum(1 for item in caught if issubclass(item.category, DeprecationWarning)) == 1
    )

    # The loaded Authorizer's own state is what the kernel exposes.
    assert kernel._state is kernel._authorizer.state
    assert kernel.contract_digest == kernel._authorizer.state.contract_digest
    assert kernel.document == kernel._authorizer.state.document
    kernel.check_capability(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.local-controls",
    )


def test_core_import_stays_independent_of_crewai_and_langgraph() -> None:
    """Importing the core SPI must not drag in any agent framework."""

    code = (
        "import sys\n"
        "import nornyx\n"
        "import nornyx.agentic\n"
        "assert 'crewai' not in sys.modules\n"
        "assert 'langgraph' not in sys.modules\n"
        "assert 'nornyx_reference_adapters' not in sys.modules\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_repository_shim_is_not_declared_in_the_core_distribution() -> None:
    """The core wheel packages only ``nornyx*``; the shim stays unpackaged."""

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["nornyx*"]' in pyproject
    assert "integrations" not in pyproject
    assert "nornyx_reference_adapters" not in pyproject


# --------------------------------------------------------------------------
# Adapter-boundary approver-block validation (assurance finding M1).
#
# A denial echoes the caller's approver claim into the runtime-events stream as
# ``approver = {"role": ..., "actor_type": ...}``. Before this was validated at
# the boundary the shim fabricated ``role=""`` / ``actor_type="legacy_invalid"``
# for omitted fields, the Authorizer denied correctly, and the *invalid decision
# was still recorded* — which then broke ``EvidenceRecorder.resume`` for every
# later operation. These tests pin the invariant:
#
#   a malformed adapter-boundary request cannot append schema-invalid evidence
#   and cannot poison the next operation.
# --------------------------------------------------------------------------

_APPROVER = "identity.escalation_agent"
_ELIGIBLE_ROLE = "network_governance_owner"
_SCHEMA_LEGAL_ACTOR_TYPES = (
    "human",
    "ai_tool",
    "execution_surface",
    "autonomous_agent",
    "model",
    "connector",
    "generated_output",
)

_MALFORMED_APPROVAL_RECORDS: dict[str, dict[str, Any]] = {
    "empty_record": {},
    "role_only_missing_actor_type": {"role": "r"},
    "actor_type_only_missing_role": {"actor_type": "human", "granted": False},
    "empty_role": {"role": "", "actor_type": "human", "granted": True},
    "non_string_role": {"role": 7, "actor_type": "human", "granted": True},
    "role_with_whitespace": {
        "role": "network governance owner",
        "actor_type": "human",
        "granted": True,
    },
    "role_with_illegal_character": {
        "role": "role/owner",
        "actor_type": "human",
        "granted": True,
    },
    "role_leading_illegal_character": {
        "role": ".owner",
        "actor_type": "human",
        "granted": True,
    },
    "role_too_long": {"role": "a" * 129, "actor_type": "human", "granted": True},
    "missing_actor_type": {"role": _ELIGIBLE_ROLE, "granted": True},
    "non_string_actor_type": {
        "role": _ELIGIBLE_ROLE,
        "actor_type": 3,
        "granted": True,
    },
    "unknown_actor_type": {
        "role": _ELIGIBLE_ROLE,
        "actor_type": "legacy_invalid",
        "granted": True,
    },
    "none_actor_type": {
        "role": _ELIGIBLE_ROLE,
        "actor_type": None,
        "granted": True,
    },
}


class _CountingAuthorizer:
    """Wrap an Authorizer and count ``evaluate`` calls."""

    def __init__(self, inner: Any):
        self._inner = inner
        self.evaluations = 0

    def evaluate(self, request: Any, *, context: Any) -> Any:
        self.evaluations += 1
        return self._inner.evaluate(request, context=context)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _count_evaluations(kernel: GovernanceKernel) -> _CountingAuthorizer:
    counter = _CountingAuthorizer(kernel._authorizer)
    kernel._authorizer = counter
    return counter


def _validates(kernel: GovernanceKernel, controls: tuple[dict[str, Any], Any]) -> bool:
    document, composition = controls
    report = validate_runtime_events(
        document, composition, kernel.lock_payload, kernel.events_payload()
    )
    return report["status"] == "pass"


@pytest.mark.parametrize("case", sorted(_MALFORMED_APPROVAL_RECORDS))
@pytest.mark.parametrize("schema_version", ["1.0", "1.1"])
def test_malformed_approval_record_is_rejected_before_evidence(
    controls: tuple[dict[str, Any], Any], case: str, schema_version: str
) -> None:
    """Malformed approver claims fail closed without touching the stream."""

    kernel = _kernel(controls, schema_version=schema_version)
    # Give the stream real prior content so "unchanged" is a meaningful claim.
    kernel.invoke_tool(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.prior",
    )
    counter = _count_evaluations(kernel)
    before = deepcopy(kernel.events_payload())
    assert before["events"], "precondition: stream should not be empty"

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            _MALFORMED_APPROVAL_RECORDS[case],
            mission_id="M.malformed",
            actor_ref=_APPROVER,
        )

    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    # No Authorizer evaluation, no recorder advancement, no event mutation.
    assert counter.evaluations == 0
    assert kernel.events_payload() == before
    assert _validates(kernel, controls)

    # The kernel remains usable and the next operation still validates.
    kernel.require_human_approval(
        {"role": _ELIGIBLE_ROLE, "actor_type": "human", "granted": True},
        mission_id="M.after-malformed",
        actor_ref=_APPROVER,
    )
    assert counter.evaluations == 1
    assert "approval_granted" in _event_types(kernel)
    assert _validates(kernel, controls)


@pytest.mark.parametrize("case", sorted(_MALFORMED_APPROVAL_RECORDS))
def test_malformed_approval_leaves_zone_crossing_path_usable(
    controls: tuple[dict[str, Any], Any], case: str
) -> None:
    """A poisoned stream would break the other approval call path too."""

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)
    before = deepcopy(kernel.events_payload())

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            _MALFORMED_APPROVAL_RECORDS[case],
            mission_id="M.zone-malformed",
            actor_ref=_APPROVER,
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counter.evaluations == 0
    assert kernel.events_payload() == before

    # A valid zone crossing still works afterwards on the same kernel.
    kernel.record_zone_crossing(
        "identity.refund_agent",
        "zone.support_internal",
        "zone.customer_channel",
        mission_id="M.zone-after",
        approval_ref="agentic_network_authority",
    )
    assert "trust_zone_crossed" in _event_types(kernel)
    assert _validates(kernel, controls)


def test_zone_crossing_without_a_named_role_fails_closed(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """A requirement naming no role cannot fabricate an empty approver role.

    This is the second ``_approval_assertion`` call path: ``record_zone_crossing``
    synthesizes its approver claim from the composed requirement, so the only
    way it can produce a schema-inexpressible block is a requirement that names
    no role at all.
    """

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)
    before = deepcopy(kernel.events_payload())

    spec = kernel._approval_specs["agentic_network_authority"]
    patched = dict(kernel._approval_specs)
    patched["agentic_network_authority"] = replace(
        spec, required_roles=(), eligible_roles=()
    )
    kernel._approval_specs = patched

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.record_zone_crossing(
            "identity.refund_agent",
            "zone.support_internal",
            "zone.customer_channel",
            mission_id="M.zone-no-role",
            approval_ref="agentic_network_authority",
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counter.evaluations == 0
    assert kernel.events_payload() == before
    assert _validates(kernel, controls)


@pytest.mark.parametrize(
    "actor_type", [t for t in _SCHEMA_LEGAL_ACTOR_TYPES if t != "human"]
)
def test_schema_legal_non_human_actor_types_are_policy_denials(
    controls: tuple[dict[str, Any], Any], actor_type: str
) -> None:
    """Legal-but-non-human claims reach the Authorizer and record validly."""

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {"role": _ELIGIBLE_ROLE, "actor_type": actor_type, "granted": True},
            mission_id=f"M.non-human-{actor_type}",
            actor_ref=_APPROVER,
        )

    assert excinfo.value.code == "AN_ADAPTER_APPROVAL_NON_HUMAN"
    assert counter.evaluations == 1
    events = kernel.events_payload()["events"]
    assert events[-1]["event_type"] == "approval_rejected"
    assert events[-1]["approver"] == {"role": _ELIGIBLE_ROLE, "actor_type": actor_type}
    assert _validates(kernel, controls)

    # Evidence stays resumable: the next operation is unaffected.
    kernel.invoke_tool(
        "identity.support_coordinator",
        "classify_support_request",
        mission_id="M.after-non-human",
    )
    assert _validates(kernel, controls)


def test_schema_valid_but_ineligible_role_is_a_policy_denial(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """An expressible but unauthorized role denies without poisoning evidence."""

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {"role": "not_an_eligible_role", "actor_type": "human", "granted": True},
            mission_id="M.role-invalid",
            actor_ref=_APPROVER,
        )

    assert excinfo.value.code == "AN_ADAPTER_APPROVAL_ROLE_INVALID"
    assert counter.evaluations == 1
    assert kernel.events_payload()["events"][-1]["approver"] == {
        "role": "not_an_eligible_role",
        "actor_type": "human",
    }
    assert _validates(kernel, controls)

    kernel.require_human_approval(
        {"role": _ELIGIBLE_ROLE, "actor_type": "human", "granted": True},
        mission_id="M.role-invalid-after",
        actor_ref=_APPROVER,
    )
    assert _validates(kernel, controls)


def test_not_granted_reaches_the_authorizer_and_records_validly(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """``granted=False`` is a semantic denial, not a structural rejection."""

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {"role": _ELIGIBLE_ROLE, "actor_type": "human", "granted": False},
            mission_id="M.not-granted",
            actor_ref=_APPROVER,
        )

    assert excinfo.value.code == "AN_ADAPTER_APPROVAL_NOT_GRANTED"
    assert counter.evaluations == 1
    assert _validates(kernel, controls)


def test_valid_human_approval_behaviour_is_unchanged(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """The happy path keeps its exact approver block and grant event."""

    kernel = _kernel(controls)
    kernel.require_human_approval(
        {"role": _ELIGIBLE_ROLE, "actor_type": "human", "granted": True},
        mission_id="M.valid",
        actor_ref=_APPROVER,
    )
    event = kernel.events_payload()["events"][-1]
    assert event["event_type"] == "approval_granted"
    assert event["approver"] == {"role": _ELIGIBLE_ROLE, "actor_type": "human"}
    assert _validates(kernel, controls)


def test_approver_role_is_never_defaulted_from_the_requirement(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """A caller claim is never fabricated from composed policy.

    The requirement names ``network_governance_owner``. If the shim defaulted
    the role from policy, an omitted role would silently *succeed* as that
    role. It must fail instead.
    """

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {"actor_type": "human", "granted": True},
            mission_id="M.no-role-default",
            actor_ref=_APPROVER,
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counter.evaluations == 0
    assert "approval_granted" not in _event_types(kernel)


def test_approver_actor_type_is_never_substituted_with_a_legal_value(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """An unknown actor type is rejected, never coerced to ``human``."""

    kernel = _kernel(controls)
    counter = _count_evaluations(kernel)

    with pytest.raises(GovernanceViolation) as excinfo:
        kernel.require_human_approval(
            {"role": _ELIGIBLE_ROLE, "actor_type": "LEGACY", "granted": True},
            mission_id="M.no-actor-substitution",
            actor_ref=_APPROVER,
        )
    assert excinfo.value.code == "AN_ADAPTER_REQUEST_MALFORMED"
    assert counter.evaluations == 0
    assert "approval_granted" not in _event_types(kernel)


def test_approver_validation_matches_the_published_schema_contract() -> None:
    """The boundary constants stay tied to the runtime-events schema."""

    schema = json.loads(
        (ROOT / "schemas" / "agentic_runtime_events_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    approver = schema["$defs"]["approver"]
    assert set(approver["required"]) == {"role", "actor_type"}
    assert set(approver["properties"]["actor_type"]["enum"]) == set(
        _APPROVER_ACTOR_TYPES
    )
    assert set(_SCHEMA_LEGAL_ACTOR_TYPES) == set(_APPROVER_ACTOR_TYPES)
    identifier = schema["$defs"]["id"]
    assert identifier["pattern"] == _RUNTIME_EVENT_ID_PATTERN.pattern
    assert identifier["maxLength"] == _RUNTIME_EVENT_ID_MAX_LENGTH
    assert identifier["minLength"] == 1


def test_hostile_role_str_is_not_invoked_by_the_boundary_validator(
    controls: tuple[dict[str, Any], Any],
) -> None:
    """Canonicalization never calls a caller-supplied ``__str__``."""

    class HostileRole(str):
        def __str__(self) -> str:  # pragma: no cover - must never run
            raise AssertionError("hostile __str__ was invoked")

    kernel = _kernel(controls)
    kernel.require_human_approval(
        {
            "role": HostileRole(_ELIGIBLE_ROLE),
            "actor_type": "human",
            "granted": True,
        },
        mission_id="M.hostile-role",
        actor_ref=_APPROVER,
    )
    event = kernel.events_payload()["events"][-1]
    assert event["approver"]["role"] == _ELIGIBLE_ROLE
    assert type(event["approver"]["role"]) is str
    assert _validates(kernel, controls)
