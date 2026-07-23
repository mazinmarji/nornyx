"""No network access during any adapter-package runtime operation."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Iterator

from nornyx.agentic import CapabilityRequest, Decision, DecisionCode, DecisionEffect, EvaluationContext

from nornyx_agentic_adapters import (
    AdapterMetadata,
    CoverageInventory,
    SurfaceBinding,
    SurfaceCoverage,
    SurfaceStatus,
    enforce,
    validate_binding,
)


@contextmanager
def _no_network() -> Iterator[None]:
    def _blocked(*_a: object, **_k: object) -> None:
        raise AssertionError("network access attempted during adapter runtime operation")

    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    socket.socket.connect = _blocked  # type: ignore[method-assign]
    socket.create_connection = _blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.create_connection = original_create_connection  # type: ignore[assignment]


class _FakeAuthorizer:
    def evaluate(self, request: object, *, context: object) -> Decision:
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "")


class _FakeRecorder:
    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        del decision, mission_id


def test_enforce_performs_no_network_io() -> None:
    with _no_network():
        result = enforce(
            _FakeAuthorizer(),
            CapabilityRequest(identity_ref="identity:agent-1", capability_ref="capability:file_write"),
            context=EvaluationContext(
                decision_at="2026-07-23T00:00:00Z",
                observed_subject_revision="git:0123456789abcdef0123456789abcdef01234567",
            ),
            recorder=_FakeRecorder(),
            mission_id="mission-1",
            action=lambda: "ok",
        )
    assert result == "ok"


def test_binding_metadata_and_coverage_construction_perform_no_network_io() -> None:
    with _no_network():
        validate_binding(SurfaceBinding("tool_invocation", "identity:agent-1", "capability:file_write"))
        AdapterMetadata(
            adapter_name="nornyx-agentic-adapters",
            adapter_version="0.1.0",
            spi_version="1.0",
            framework_name="crewai",
            framework_version_range="==1.15.4",
            nornyx_version_range=">=1.8,<2",
        )
        CoverageInventory(entries=(SurfaceCoverage("tool_invocation", "crewai", SurfaceStatus.WRAPPED),)).as_dict()
