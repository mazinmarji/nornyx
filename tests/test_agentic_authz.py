"""ADR-0039: behaviour tests for the core nornyx.agentic authorization engine."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nornyx.agentic import (
    ApprovalAssertion,
    ApprovalRequest,
    Authorizer,
    AuthorizerLoadError,
    CapabilityRequest,
    DataShareRequest,
    Decision,
    DecisionCode,
    DecisionEffect,
    DelegationRequest,
    EvaluationContext,
    EvidenceRecorder,
    HandoffRequest,
    IdentityResolutionCode,
    IdentityResolutionError,
    ZoneCrossingRequest,
    load_authorizer,
)
import nornyx.agentic as A
from nornyx.agentic.authz import AuthorizerLoadCode, PHASE_INTENT
from nornyx.agentic_artifacts import (
    build_agentic_network_lock,
    write_agentic_network_lock,
)
from nornyx.governance import GovernanceRegistry

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
AS_OF = "2026-07-17T10:00:00Z"
REVISION = "git:0123456789abcdef0123456789abcdef01234567"


def _inmemory(document: dict) -> Authorizer:
    """Build an Authorizer directly to exercise evaluate() without touching the
    filesystem (load_authorizer's file/evidence-artifact validation is covered
    separately by test_load_authorizer_from_files)."""
    composition = A.compose_document_governance(
        document, registry=GovernanceRegistry.builtins()
    )
    lock = build_agentic_network_lock(document, composition)
    return Authorizer(document, composition, lock)


def _base_document() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _rich_document() -> dict:
    """Base example plus an active delegation and a handoff (mirrors evidence test)."""
    document = _base_document()
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


@pytest.fixture(scope="module")
def authz() -> Authorizer:
    return _inmemory(_base_document())


@pytest.fixture(scope="module")
def rich() -> Authorizer:
    return _inmemory(_rich_document())


def ctx(revision: str = REVISION, decision_at: str = AS_OF) -> EvaluationContext:
    return EvaluationContext(decision_at=decision_at, observed_subject_revision=revision)


# --------------------------------------------------------------- load + identity
def test_authorizer_bindings(authz: Authorizer):
    assert authz.subject_revision == REVISION
    assert authz.contract_digest.startswith("sha256:")
    assert authz.network_lock_digest.startswith("sha256:")


def test_load_authorizer_from_files(tmp_path):
    document = _base_document()
    composition = A.compose_document_governance(
        document, registry=A.registry_for_contract(EXAMPLE)
    )
    lock = build_agentic_network_lock(document, composition)
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(lock, lock_path)
    az = load_authorizer(EXAMPLE, lock_path, validation_as_of=AS_OF)
    assert az.subject_revision == REVISION
    assert az.contract_digest.startswith("sha256:")


def test_load_error_on_bad_lock(tmp_path):
    (tmp_path / "bad.lock").write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(AuthorizerLoadError) as exc:
        load_authorizer(EXAMPLE, tmp_path / "bad.lock", validation_as_of=AS_OF)
    assert exc.value.code in {AuthorizerLoadCode.LOCK_INVALID, AuthorizerLoadCode.LOCK_STALE}


def test_resolve_identity(authz: Authorizer):
    assert authz.resolve_identity("contract_fixture", "researcher") == "identity.researcher.local"
    with pytest.raises(IdentityResolutionError) as exc:
        authz.resolve_identity("contract_fixture", "nobody")
    assert exc.value.code is IdentityResolutionCode.IDENTITY_UNKNOWN


def test_resolve_identity_ambiguous():
    document = _base_document()
    # Give a second identity the same framework binding as the researcher.
    document["agent_identities"][1]["framework_bindings"] = [
        {"framework": "contract_fixture", "agent_key": "researcher"}
    ]
    authz = _inmemory(document)
    with pytest.raises(IdentityResolutionError) as exc:
        authz.resolve_identity("contract_fixture", "researcher")
    assert exc.value.code is IdentityResolutionCode.IDENTITY_AMBIGUOUS


# --------------------------------------------------------------------- capability
def test_capability_allow(authz: Authorizer):
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=ctx())
    assert d.effect is DecisionEffect.ALLOW and d.code is DecisionCode.ALLOWED
    assert [i.event_type for i in d.event_intents] == ["capability_requested", "capability_allowed"]


def test_capability_deny(authz: Authorizer):
    d = authz.evaluate(CapabilityRequest("identity.reviewer.local", "propose_research_finding"), context=ctx())
    assert d.code is DecisionCode.CAPABILITY_DENIED
    assert d.event_intents[-1].fields["policy_decision"] == "deny"


def test_capability_unknown(authz: Authorizer):
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "nope"), context=ctx())
    assert d.code is DecisionCode.CAPABILITY_UNKNOWN


def test_capability_unknown_identity_is_malformed(authz: Authorizer):
    d = authz.evaluate(CapabilityRequest("identity.ghost", "read_governed_context"), context=ctx())
    assert d.code is DecisionCode.REQUEST_MALFORMED


# ------------------------------------------------------------- revision + context
def test_revision_mismatch_is_unconditional(authz: Authorizer):
    d = authz.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=ctx(revision="git:" + "a" * 40),
    )
    assert d.effect is DecisionEffect.DENY and d.code is DecisionCode.REVISION_MISMATCH


def test_revision_mismatch_delegation_emits_no_actorless_intent(rich: Authorizer):
    # A DelegationRequest carries no identity_ref; the revision-mismatch
    # policy_violation intent must be omitted rather than emitted without the
    # schema-required actor_ref (which would make recorded evidence invalid).
    d = rich.evaluate(DelegationRequest("delegation.research"), context=ctx(revision="git:" + "b" * 40))
    assert d.code is DecisionCode.REVISION_MISMATCH
    assert d.event_intents == ()


def test_malformed_context(authz: Authorizer):
    d = authz.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=EvaluationContext(decision_at="nope", observed_subject_revision=REVISION),
    )
    assert d.code is DecisionCode.REQUEST_MALFORMED
    d2 = authz.evaluate(
        CapabilityRequest("identity.researcher.local", "read_governed_context"),
        context=EvaluationContext(decision_at=AS_OF, observed_subject_revision="main"),
    )
    assert d2.code is DecisionCode.REQUEST_MALFORMED


# ------------------------------------------------------------- delegation/handoff
def test_delegation_active(rich: Authorizer):
    d = rich.evaluate(DelegationRequest("delegation.research"), context=ctx())
    assert d.effect is DecisionEffect.ALLOW
    d2 = rich.evaluate(DelegationRequest("no.such"), context=ctx())
    assert d2.code is DecisionCode.DELEGATION_UNKNOWN


def test_handoff_authority(rich: Authorizer):
    d = rich.evaluate(HandoffRequest("handoff.review"), context=ctx())
    assert d.effect is DecisionEffect.ALLOW  # reviewer holds read_governed_context
    d2 = rich.evaluate(HandoffRequest("ghost.handoff"), context=ctx())
    assert d2.code is DecisionCode.HANDOFF_UNKNOWN


# ------------------------------------------------------------------- zone + share
def test_zone_crossing_requires_approval(authz: Authorizer):
    d = authz.evaluate(
        ZoneCrossingRequest("identity.researcher.local", "zone.local_governed", "zone.external_contract"),
        context=ctx(),
    )
    assert d.effect is DecisionEffect.APPROVAL_REQUIRED and d.code is DecisionCode.CROSSING_APPROVAL_REQUIRED


def test_zone_crossing_undeclared(authz: Authorizer):
    d = authz.evaluate(
        ZoneCrossingRequest("identity.researcher.local", "zone.external_contract", "zone.local_governed"),
        context=ctx(),
    )
    assert d.code is DecisionCode.ZONE_CROSSING_DENIED


def test_data_share_allow_and_denials(authz: Authorizer):
    ok = authz.evaluate(
        DataShareRequest("identity.researcher.local", "identity.reviewer.local", ("finding_summary",), "zone.local_governed", "zone.local_governed"),
        context=ctx(),
    )
    assert ok.effect is DecisionEffect.ALLOW
    sensitive = authz.evaluate(
        DataShareRequest("identity.researcher.local", "identity.reviewer.local", ("secrets",), "zone.local_governed", "zone.local_governed"),
        context=ctx(),
    )
    assert sensitive.code is DecisionCode.SENSITIVE_SHARING
    not_allowed = authz.evaluate(
        DataShareRequest("identity.researcher.local", "identity.reviewer.local", ("random_category",), "zone.local_governed", "zone.local_governed"),
        context=ctx(),
    )
    assert not_allowed.code is DecisionCode.SHARE_NOT_ALLOWED


# ---------------------------------------------------------------------- approvals
def _approval(**overrides) -> ApprovalAssertion:
    base = dict(
        approval_ref="agentic_network_authority",
        claimed_approver_ref="alice",
        claimed_actor_type="human",
        role="network_governance_owner",
        granted=True,
        action_ref="approve_agentic_network_contract",
        subject_revision=REVISION,
    )
    base.update(overrides)
    return ApprovalAssertion(**base)


def test_approval_grant(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval()), context=ctx())
    assert d.effect is DecisionEffect.ALLOW
    assert d.event_intents[-1].event_type == "approval_granted"


def test_approval_non_human(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(claimed_actor_type="ai_tool")), context=ctx())
    assert d.code is DecisionCode.APPROVAL_NON_HUMAN


def test_approval_role_invalid(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(role="intern")), context=ctx())
    assert d.code is DecisionCode.APPROVAL_ROLE_INVALID


def test_approval_not_granted(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(granted=False)), context=ctx())
    assert d.code is DecisionCode.APPROVAL_NOT_GRANTED


def test_approval_unknown_ref_is_malformed(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(approval_ref="ghost")), context=ctx())
    assert d.code is DecisionCode.REQUEST_MALFORMED


# --------------------------------------------------------------- recorder + phases
def test_recorder_produces_valid_evidence(authz: Authorizer):
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, context=context, mission_id="GOAL-001")
    # A post-action observation is recorded after the fact by the adapter.
    rec.record_observation(
        "tool_invoked", context=context, mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
    )
    report = rec.validate()
    assert report["status"] == "pass", report["diagnostics"]
    assert report["event_count"] == 3


def test_recorder_rejects_observation_as_intent(authz: Authorizer):
    rec = EvidenceRecorder(authz, producer_id="t")
    with pytest.raises(ValueError):
        rec.record_observation("capability_allowed", context=ctx(), mission_id="m")
    from nornyx.agentic import DecisionEventIntent

    fake = Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, event_intents=(DecisionEventIntent("tool_invoked", {}),))
    with pytest.raises(ValueError):
        rec.record_decision(fake, context=ctx(), mission_id="m")


def test_authorizer_is_deterministic_and_immutable(authz: Authorizer):
    req = CapabilityRequest("identity.researcher.local", "read_governed_context")
    a = authz.evaluate(req, context=ctx())
    b = authz.evaluate(req, context=ctx())
    assert a == b
    # decision intents are decision-phase only
    for intent in a.event_intents:
        assert intent.event_type in PHASE_INTENT
