"""ADR-0039 M2-D compatibility and baseline-closure corpus."""

from __future__ import annotations

import ast
from copy import deepcopy
import inspect
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any
import warnings

import pytest

from nornyx.agentic import (
    Authorizer,
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
    assert SPI_VERSION == "1.1"
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
