"""AN-004 tests: runtime-event evidence validation and ordering."""

from __future__ import annotations

import builtins
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any

import pytest
import yaml

from nornyx.agentic_artifacts import (
    agentic_network_lock_digest,
    build_agentic_network_lock,
    contract_digest,
    write_agentic_network_lock,
)
from nornyx.agentic_evidence import (
    LIMITATIONS,
    load_runtime_events,
    validate_runtime_events,
)
from nornyx.cli import main as cli_main
from nornyx.governance import GovernanceError, GovernanceRegistry, compose_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
REGISTRY = GovernanceRegistry.builtins()
COMPOSITION = compose_governance(REGISTRY, profile_identity="agentic_network")
BASE_TS = "2026-07-17T10:{minute:02d}:00Z"


def _document() -> dict[str, Any]:
    document = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    document["capabilities"][1]["delegable"] = True
    document["capabilities"][1]["max_delegation_depth"] = 2
    document["agentic_network"]["delegations"] = [
        {
            "id": "delegation.research",
            "delegator_ref": "identity.researcher.local",
            "delegate_ref": "identity.reviewer.local",
            "capability_ref": "propose_research_finding",
            "purpose": "Bounded review-cycle finding proposals",
            "actions": ["propose_finding"],
            "scope_refs": ["GovernedNetworkContext"],
            "status": "active",
            "valid_from": "2026-01-01T00:00:00Z",
            "expires_at": "2026-08-01T00:00:00Z",
            "max_depth": 2,
            "current_depth": 0,
            "onward_delegation": "allowed_with_policy",
            "source_zone_ref": "zone.local_governed",
            "target_zone_ref": "zone.local_governed",
            "required_gate_refs": [],
            "required_policy_refs": [],
            "required_approval_refs": [],
            "required_evidence_refs": [],
            "revocation_refs": [],
        }
    ]
    document["agentic_network"]["handoffs"] = [
        {
            "id": "handoff.review",
            "from_identity_ref": "identity.researcher.local",
            "to_identity_ref": "identity.reviewer.local",
            "purpose": "Transfer finding-review responsibility",
            "mission_ref": "GOAL-001",
            "from_zone_ref": "zone.local_governed",
            "to_zone_ref": "zone.local_governed",
            "required_capability_refs": ["read_governed_context"],
            "delegation_refs": [],
            "shared_context": ["finding_summary"],
            "never_share": ["secrets", "credentials", "tokens", "private_memory"],
            "status": "initiated",
            "valid_from": "2026-01-01T00:00:00Z",
            "expires_at": "2026-08-01T00:00:00Z",
            "required_gate_refs": [],
            "required_approval_refs": [],
            "required_evidence_refs": [],
            "revocation_refs": [],
        }
    ]
    return document


class Context:
    def __init__(self, document: dict[str, Any]):
        self.document = document
        self.lock = build_agentic_network_lock(document, COMPOSITION)
        self.contract_digest = contract_digest(document)
        self.lock_digest = agentic_network_lock_digest(self.lock)

    def event(self, sequence: int, event_type: str, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": f"evt-{sequence:03d}",
            "event_type": event_type,
            "mission_id": "GOAL-001",
            "sequence": sequence,
            "actor_ref": "identity.researcher.local",
            "timestamp": BASE_TS.format(minute=sequence),
            "network_id": "network.research",
            "contract_digest": self.contract_digest,
            "network_lock_digest": self.lock_digest,
            "subject_revision": self.document["agentic_network"]["subject_revision"],
            "producer": {
                "type": "synthetic_harness",
                "id": "nornyx.tests",
                "version": "1.0",
            },
        }
        payload.update(overrides)
        return payload

    def stream(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema": "nornyx.agentic_runtime_events.v1",
            "schema_version": "1.0",
            "network_id": "network.research",
            "producer": {
                "type": "synthetic_harness",
                "id": "nornyx.tests",
                "version": "1.0",
            },
            "events": events,
        }

    def validate(
        self,
        events: list[dict[str, Any]] | dict[str, Any],
        *,
        events_root: Path | None = None,
    ) -> dict[str, Any]:
        payload = events if isinstance(events, dict) else self.stream(events)
        return validate_runtime_events(
            self.document,
            COMPOSITION,
            self.lock,
            payload,
            events_root=events_root,
        )


@pytest.fixture(scope="module")
def context() -> Context:
    return Context(_document())


def _positive_events(context: Context) -> list[dict[str, Any]]:
    return [
        context.event(1, "agent_invoked"),
        context.event(2, "capability_requested", capability_ref="read_governed_context"),
        context.event(
            3,
            "capability_allowed",
            capability_ref="read_governed_context",
            policy_decision="allow",
            depends_on=["evt-002"],
        ),
        context.event(4, "tool_invoked", capability_ref="read_governed_context"),
        context.event(5, "delegation_requested", delegation_ref="delegation.research"),
        context.event(
            6,
            "delegation_accepted",
            delegation_ref="delegation.research",
            actor_ref="identity.reviewer.local",
        ),
        context.event(
            7,
            "handoff_initiated",
            handoff_ref="handoff.review",
            target_ref="identity.reviewer.local",
        ),
        context.event(
            8,
            "handoff_completed",
            handoff_ref="handoff.review",
            target_ref="identity.reviewer.local",
        ),
        context.event(9, "approval_requested", approval_ref="agentic_network_authority"),
        context.event(
            10,
            "approval_granted",
            approval_ref="agentic_network_authority",
            approver={"role": "network_governance_owner", "actor_type": "human"},
        ),
        context.event(
            11,
            "data_shared",
            target_ref="identity.reviewer.local",
            share_categories=["finding_summary"],
            source_zone_ref="zone.local_governed",
            target_zone_ref="zone.local_governed",
        ),
        context.event(
            12,
            "capability_allowed",
            actor_ref="identity.reviewer.local",
            capability_ref="propose_research_finding",
            delegation_ref="delegation.research",
            policy_decision="allow",
        ),
    ]


def test_positive_event_stream_passes(context: Context) -> None:
    report = context.validate(_positive_events(context))
    assert report["status"] == "pass"
    assert report["diagnostics"] == []
    assert report["event_count"] == 12
    assert report["mission_count"] == 1
    assert report["limitations"] == list(LIMITATIONS)
    assert report["safety"]["network_used"] is False


def test_report_is_deterministic(context: Context) -> None:
    first = context.validate(_positive_events(context))
    second = context.validate(deepcopy(_positive_events(context)))
    assert first == second


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda e: e[0].update({"contract_digest": "sha256:" + "0" * 64}),
            "AN_EVT_CONTRACT_MISMATCH",
        ),
        (
            lambda e: e[0].update({"network_lock_digest": "sha256:" + "0" * 64}),
            "AN_EVT_LOCK_MISMATCH",
        ),
        (
            lambda e: e[0].update({"subject_revision": "git:" + "9" * 40}),
            "AN_EVT_REVISION_MISMATCH",
        ),
        (
            lambda e: e[0].update({"network_id": "network.other"}),
            "AN_EVT_NETWORK_MISMATCH",
        ),
        (
            lambda e: e[0].update({"actor_ref": "identity.unknown"}),
            "AN_EVT_ACTOR_UNKNOWN",
        ),
        (
            lambda e: e[1].update({"capability_ref": "capability.unknown"}),
            "AN_EVT_CAPABILITY_UNKNOWN",
        ),
        (
            lambda e: e[11].pop("delegation_ref"),
            "AN_EVT_CAPABILITY_NOT_HELD",
        ),
        (
            lambda e: e[4].update({"delegation_ref": "delegation.unknown"}),
            "AN_EVT_DELEGATION_UNKNOWN",
        ),
        (
            lambda e: e[5].update({"actor_ref": "identity.researcher.local"}),
            "AN_EVT_DELEGATION_ACTOR_MISMATCH",
        ),
        (
            lambda e: e[1].update({"event_id": "evt-001"}),
            "AN_EVT_DUPLICATE_ID",
        ),
        (
            lambda e: e[1].update({"sequence": 1, "event_id": "evt-dup"}),
            "AN_EVT_DUPLICATE_SEQUENCE",
        ),
        (
            lambda e: e[1].update({"sequence": 9}),
            "AN_EVT_SEQUENCE_GAP",
        ),
        (
            lambda e: e[3].update({"timestamp": "2026-07-17T09:00:00Z"}),
            "AN_EVT_ORDER_INVALID",
        ),
        (
            lambda e: e[2].update({"depends_on": ["evt-999"]}),
            "AN_EVT_DEPENDENCY_MISSING",
        ),
        (
            lambda e: e[2].update({"depends_on": ["evt-012"]}),
            "AN_EVT_ORDER_INVALID",
        ),
        (
            lambda e: e.pop(6),
            "AN_EVT_COMPLETION_WITHOUT_INITIATION",
        ),
        (
            lambda e: e.pop(4),
            "AN_EVT_ACCEPTANCE_WITHOUT_REQUEST",
        ),
        (
            lambda e: e.pop(8),
            "AN_EVT_GRANT_WITHOUT_REQUEST",
        ),
        (
            lambda e: e.pop(2),
            "AN_EVT_TOOL_WITHOUT_ALLOWANCE",
        ),
        (
            lambda e: e[9].update(
                {"approver": {"role": "network_governance_owner", "actor_type": "model"}}
            ),
            "AN_EVT_APPROVAL_NON_HUMAN",
        ),
        (
            lambda e: e[9].update(
                {"approver": {"role": "unlisted_role", "actor_type": "human"}}
            ),
            "AN_EVT_APPROVAL_ROLE_INVALID",
        ),
        (
            lambda e: e[8].update({"approval_ref": "approval.unknown"}),
            "AN_EVT_APPROVAL_UNKNOWN",
        ),
        (
            lambda e: e[10].update({"share_categories": ["finding_summary", "secrets"]}),
            "AN_EVT_SENSITIVE_SHARING",
        ),
        (
            lambda e: e[10].update({"share_categories": ["undeclared_category"]}),
            "AN_EVT_SHARE_NOT_ALLOWED",
        ),
        (
            lambda e: e[0].update({"event_type": "made_up_type"}),
            "AN_EVT_SCHEMA_INVALID",
        ),
        (
            lambda e: e[2].update({"policy_decision": "deny"}),
            "AN_EVT_DECISION_CONTRADICTION",
        ),
    ],
)
def test_single_event_mutation_matrix(
    context: Context, mutate: Any, expected: str
) -> None:
    events = _positive_events(context)
    mutate(events)
    report = context.validate(events)
    assert report["status"] == "fail"
    assert expected in {item["code"] for item in report["diagnostics"]}


def test_sequence_gap_when_missing_events_are_omitted(context: Context) -> None:
    events = _positive_events(context)[0:3] + _positive_events(context)[5:6]
    report = context.validate(events)
    assert "AN_EVT_SEQUENCE_GAP" in {item["code"] for item in report["diagnostics"]}


def test_replayed_content_is_rejected(context: Context) -> None:
    events = _positive_events(context)
    replay = deepcopy(events[3])
    replay["event_id"] = "evt-replay"
    replay["sequence"] = 13
    events.append(replay)
    report = context.validate(events)
    assert "AN_EVT_REPLAY" in {item["code"] for item in report["diagnostics"]}


def test_allow_and_deny_contradiction_in_one_mission(context: Context) -> None:
    events = _positive_events(context)
    events.append(
        context.event(
            13,
            "capability_denied",
            capability_ref="read_governed_context",
            policy_decision="deny",
        )
    )
    report = context.validate(events)
    assert "AN_EVT_DECISION_CONTRADICTION" in {
        item["code"] for item in report["diagnostics"]
    }


def test_stale_lock_is_rejected(context: Context) -> None:
    drifted = _document()
    drifted["capabilities"][0]["risk"] = "medium"
    report = validate_runtime_events(
        drifted,
        COMPOSITION,
        context.lock,
        context.stream([]),
    )
    codes = {item["code"] for item in report["diagnostics"]}
    assert "AN_EVT_LOCK_STALE" in codes


def test_cross_network_evidence_is_rejected(context: Context) -> None:
    stream = context.stream([])
    stream["network_id"] = "network.other"
    report = context.validate(stream)
    assert "AN_EVT_NETWORK_MISMATCH" in {
        item["code"] for item in report["diagnostics"]
    }


def test_expired_delegation_and_expired_actor(context: Context) -> None:
    events = [
        context.event(
            1,
            "delegation_requested",
            delegation_ref="delegation.research",
            timestamp="2026-09-01T00:00:00Z",
        ),
        context.event(
            2,
            "delegation_accepted",
            delegation_ref="delegation.research",
            actor_ref="identity.reviewer.local",
            timestamp="2026-09-01T00:01:00Z",
        ),
    ]
    report = context.validate(events)
    codes = {item["code"] for item in report["diagnostics"]}
    assert "AN_EVT_DELEGATION_EXPIRED" in codes
    assert "AN_EVT_ACTOR_NOT_EFFECTIVE" in codes


def test_revocation_timing_controls_event_validity() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        {
            "id": "revocation.delegation",
            "target": {"kind": "delegation", "delegation_ref": "delegation.research"},
            "effective_at": "2026-07-20T00:00:00Z",
            "reason": "test",
            "required_approval_refs": [],
            "required_evidence_refs": [],
        }
    ]
    local = Context(document)
    before = [
        local.event(1, "delegation_requested", delegation_ref="delegation.research"),
        local.event(
            2,
            "delegation_accepted",
            delegation_ref="delegation.research",
            actor_ref="identity.reviewer.local",
        ),
    ]
    assert local.validate(before)["status"] == "pass"

    after = [
        local.event(
            1,
            "delegation_requested",
            delegation_ref="delegation.research",
            timestamp="2026-07-21T00:00:00Z",
        ),
        local.event(
            2,
            "delegation_accepted",
            delegation_ref="delegation.research",
            actor_ref="identity.reviewer.local",
            timestamp="2026-07-21T00:01:00Z",
        ),
    ]
    codes = {item["code"] for item in local.validate(after)["diagnostics"]}
    assert "AN_EVT_DELEGATION_REVOKED" in codes


def test_revoked_actor_is_rejected() -> None:
    document = _document()
    document["agentic_network"]["revocations"] = [
        {
            "id": "revocation.researcher",
            "target": {
                "kind": "agent_identity",
                "identity_ref": "identity.researcher.local",
            },
            "effective_at": "2026-07-20T00:00:00Z",
            "reason": "test",
            "required_approval_refs": [],
            "required_evidence_refs": [],
        }
    ]
    local = Context(document)
    events = [local.event(1, "agent_invoked", timestamp="2026-07-21T00:00:00Z")]
    codes = {item["code"] for item in local.validate(events)["diagnostics"]}
    assert "AN_EVT_ACTOR_REVOKED" in codes


def test_trust_zone_crossing_rules(context: Context) -> None:
    valid = [
        context.event(
            1,
            "trust_zone_crossed",
            source_zone_ref="zone.local_governed",
            target_zone_ref="zone.external_contract",
            approval_ref="agentic_network_authority",
        )
    ]
    assert context.validate(valid)["status"] == "pass"

    missing_approval = [
        context.event(
            1,
            "trust_zone_crossed",
            source_zone_ref="zone.local_governed",
            target_zone_ref="zone.external_contract",
        )
    ]
    codes = {
        item["code"] for item in context.validate(missing_approval)["diagnostics"]
    }
    assert "AN_EVT_CROSSING_APPROVAL_MISSING" in codes

    undeclared = [
        context.event(
            1,
            "trust_zone_crossed",
            source_zone_ref="zone.external_contract",
            target_zone_ref="zone.local_governed",
        )
    ]
    codes = {item["code"] for item in context.validate(undeclared)["diagnostics"]}
    assert {"AN_EVT_CROSSING_NOT_DECLARED", "AN_EVT_CROSSING_UNGOVERNED"} <= codes


def test_evidence_artifact_hashes(context: Context, tmp_path: Path) -> None:
    artifact = tmp_path / "output.json"
    artifact.write_text('{"result": "finding"}', encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    events = [
        context.event(
            1,
            "agent_invoked",
            evidence_artifact={"path": "output.json", "sha256": digest},
        )
    ]
    assert context.validate(events, events_root=tmp_path)["status"] == "pass"

    forged = [
        context.event(
            1,
            "agent_invoked",
            evidence_artifact={"path": "output.json", "sha256": "0" * 64},
        )
    ]
    codes = {
        item["code"]
        for item in context.validate(forged, events_root=tmp_path)["diagnostics"]
    }
    assert "AN_EVT_ARTIFACT_HASH_MISMATCH" in codes

    missing = [
        context.event(
            1,
            "agent_invoked",
            evidence_artifact={"path": "absent.json", "sha256": digest},
        )
    ]
    codes = {
        item["code"]
        for item in context.validate(missing, events_root=tmp_path)["diagnostics"]
    }
    assert "AN_EVT_ARTIFACT_MISSING" in codes


def test_large_bounded_stream(context: Context) -> None:
    events = [context.event(1, "agent_invoked")]
    for sequence in range(2, 502):
        events.append(
            context.event(
                sequence,
                "capability_requested",
                capability_ref="read_governed_context",
                event_id=f"evt-{sequence:04d}",
                timestamp=f"2026-07-18T{sequence // 60:02d}:{sequence % 60:02d}:00Z",
            )
        )
    report = context.validate(events)
    assert report["event_count"] == 501
    unexpected = {
        item["code"]
        for item in report["diagnostics"]
        if item["code"] != "AN_EVT_ORDER_INVALID"
    }
    assert unexpected == set()


def test_malformed_events_file_fails_closed(tmp_path: Path) -> None:
    broken = tmp_path / "events.json"
    broken.write_text("{\"schema\": ", encoding="utf-8")
    with pytest.raises(GovernanceError) as excinfo:
        load_runtime_events(broken)
    assert any(
        item.code == "AN_EVT_MALFORMED" for item in excinfo.value.diagnostics
    )

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
    with pytest.raises(GovernanceError):
        load_runtime_events(duplicate)


def test_unsupported_schema_version_fails(context: Context) -> None:
    stream = context.stream([])
    stream["schema_version"] = "2.0"
    report = context.validate(stream)
    assert "AN_EVT_SCHEMA_INVALID" in {
        item["code"] for item in report["diagnostics"]
    }


def test_cli_evidence_validate_flow(context: Context, tmp_path: Path) -> None:
    shutil.copytree(
        EXAMPLE.parent / "governance_evidence", tmp_path / "governance_evidence"
    )
    contract = tmp_path / "contract.nyx"
    contract.write_text(
        yaml.safe_dump(context.document, sort_keys=False), encoding="utf-8"
    )
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(context.lock, lock_path)
    events_path = tmp_path / "events.json"
    events_path.write_text(
        json.dumps(context.stream(_positive_events(context)), indent=2),
        encoding="utf-8",
    )
    report_path = tmp_path / "evidence_report.json"

    out = StringIO()
    with redirect_stdout(out):
        code = cli_main(
            [
                "agentic-network",
                "evidence-validate",
                str(contract),
                "--events",
                str(events_path),
                "--lock",
                str(lock_path),
                "--as-of",
                "2026-07-17T00:00:00Z",
                "--out",
                str(report_path),
                "--strict",
            ]
        )
    assert code == 0, out.getvalue()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "pass"

    forged = context.stream(_positive_events(context))
    forged["events"][0]["contract_digest"] = "sha256:" + "0" * 64
    events_path.write_text(json.dumps(forged, indent=2), encoding="utf-8")
    out = StringIO()
    with redirect_stdout(out):
        code = cli_main(
            [
                "agentic-network",
                "evidence-validate",
                str(contract),
                "--events",
                str(events_path),
                "--lock",
                str(lock_path),
                "--as-of",
                "2026-07-17T00:00:00Z",
                "--strict",
            ]
        )
    assert code == 1


def test_validation_uses_no_network_or_processes(
    context: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("evidence validation attempted an external operation")

    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.split(".", 1)[0] in {"crewai", "langgraph"}:
            raise AssertionError("evidence validation constructed a framework")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)

    report = context.validate(_positive_events(context))
    assert report["status"] == "pass"
