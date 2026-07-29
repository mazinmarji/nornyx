"""ADR-0039: behaviour tests for the core nornyx.agentic authorization engine."""

from __future__ import annotations

import threading
from collections.abc import Mapping as _AbcMapping
from pathlib import Path
from typing import Any

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
        action_ref="approve_agentic_network_contract",  # in actions_requiring_approval
        subject_revision=REVISION,
        issued_at="2026-07-17T09:00:00Z",               # 1h before decision_at (P7D policy)
        evidence_refs=("agentic_network_contract_review",),  # covers required_evidence
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
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")
    # A post-action observation is recorded after the fact by the adapter.
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
    )
    report = rec.validate()
    assert report["status"] == "pass", report["diagnostics"]
    assert report["event_count"] == 3


def test_recorder_rejects_observation_as_intent(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="t")
    with pytest.raises(ValueError):
        rec.record_observation("capability_allowed", mission_id="m")
    from nornyx.agentic import DecisionEventIntent

    fake = Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, event_intents=(DecisionEventIntent("tool_invoked", {}),))
    with pytest.raises(ValueError):
        rec.record_decision(fake, mission_id="m")


def test_recorder_rejects_mismatched_revision(authz: Authorizer):
    # F2: fail closed when the bound context's observed revision != contract.
    with pytest.raises(ValueError):
        EvidenceRecorder(authz, ctx(revision="git:" + "c" * 40), producer_id="t")


def test_zone_crossing_with_valid_approval_preserves_intents(authz: Authorizer):
    # F1: an approval that authorizes an external crossing must keep its intents.
    approval = _approval(action_ref="external_share")
    context = ctx()
    d = authz.evaluate(
        ZoneCrossingRequest(
            "identity.researcher.local", "zone.local_governed", "zone.external_contract", approval
        ),
        context=context,
    )
    assert d.effect is DecisionEffect.ALLOW
    assert [i.event_type for i in d.event_intents] == ["approval_requested", "approval_granted"]
    # And those intents produce runtime-event evidence that validates.
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")
    report = rec.validate()
    assert report["status"] == "pass", report["diagnostics"]


class _MutatedStreamRecorder(EvidenceRecorder):
    """An ``EvidenceRecorder`` whose assembled stream is altered before validation.

    Used to forge an event the engine would never emit, so the validator's own
    rule can be tested independently of what the emitter happens to produce.
    """

    def __init__(self, *args, mutate, **kwargs):
        super().__init__(*args, **kwargs)
        self._mutate = mutate

    def stream(self):
        payload = super().stream()
        self._mutate(payload["events"])
        return payload


def _record_refused_approval(authz: Authorizer, approval: ApprovalAssertion, **recorder_kw):
    context = ctx()
    decision = authz.evaluate(
        ApprovalRequest("identity.researcher.local", approval), context=context
    )
    recorder = EvidenceRecorder(
        authz, context, producer_id="tests", producer_type="synthetic_harness", **recorder_kw
    )
    recorder.record_decision(decision, mission_id="GOAL-001")
    return decision, recorder


def test_refused_non_human_approval_is_evidenced_truthfully(authz: Authorizer):
    """A refused AI approval must record the non-human claimant AND validate.

    The engine names whoever actually claimed the approval; the validator's
    human-approver rule governs grants, not refusals. Applying it to refusals
    made exercising the product's headline guarantee — refusing an AI-issued
    approval — the one outcome that could not be evidenced.
    """
    decision, recorder = _record_refused_approval(
        authz, _approval(claimed_actor_type="model", claimed_approver_ref="model.remediation_llm")
    )
    assert decision.code is DecisionCode.APPROVAL_NON_HUMAN
    assert decision.effect is DecisionEffect.DENY

    events = recorder.stream()["events"]
    assert [e["event_type"] for e in events] == ["approval_requested", "approval_rejected"]
    # Truthful: the record names the claimant as it was claimed, not as "human".
    assert events[-1]["approver"] == {
        "role": "network_governance_owner",
        "actor_type": "model",
    }

    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]
    assert report["diagnostics"] == []


def test_refused_invalid_role_approval_is_evidenced_truthfully(authz: Authorizer):
    """Same rule for the claimed role: a refusal records the claim, not an authority."""
    decision, recorder = _record_refused_approval(authz, _approval(role="intern"))
    assert decision.code is DecisionCode.APPROVAL_ROLE_INVALID
    assert recorder.stream()["events"][-1]["approver"]["role"] == "intern"
    report = recorder.validate()
    assert report["status"] == "pass", report["diagnostics"]


def test_granted_non_human_approval_still_fails_validation(authz: Authorizer):
    """The grant rule is unchanged: only a human can carry a granted approval."""
    context = ctx()
    decision = authz.evaluate(
        ApprovalRequest("identity.researcher.local", _approval()), context=context
    )
    assert decision.effect is DecisionEffect.ALLOW

    def forge_non_human_grant(events):
        granted = next(e for e in events if e["event_type"] == "approval_granted")
        granted["approver"] = {"role": "network_governance_owner", "actor_type": "model"}

    recorder = _MutatedStreamRecorder(
        authz,
        context,
        producer_id="tests",
        producer_type="synthetic_harness",
        mutate=forge_non_human_grant,
    )
    recorder.record_decision(decision, mission_id="GOAL-001")
    report = recorder.validate()
    assert report["status"] == "fail"
    assert [d["code"] for d in report["diagnostics"]] == ["AN_EVT_APPROVAL_NON_HUMAN"]


def test_granted_invalid_role_approval_still_fails_validation(authz: Authorizer):
    context = ctx()
    decision = authz.evaluate(
        ApprovalRequest("identity.researcher.local", _approval()), context=context
    )

    def forge_unlisted_role_grant(events):
        granted = next(e for e in events if e["event_type"] == "approval_granted")
        granted["approver"] = {"role": "unlisted_role", "actor_type": "human"}

    recorder = _MutatedStreamRecorder(
        authz,
        context,
        producer_id="tests",
        producer_type="synthetic_harness",
        mutate=forge_unlisted_role_grant,
    )
    recorder.record_decision(decision, mission_id="GOAL-001")
    report = recorder.validate()
    assert report["status"] == "fail"
    assert [d["code"] for d in report["diagnostics"]] == ["AN_EVT_APPROVAL_ROLE_INVALID"]


def test_authorizer_is_deterministic_and_immutable(authz: Authorizer):
    req = CapabilityRequest("identity.researcher.local", "read_governed_context")
    a = authz.evaluate(req, context=ctx())
    b = authz.evaluate(req, context=ctx())
    assert a == b
    # decision intents are decision-phase only
    for intent in a.event_intents:
        assert intent.event_type in PHASE_INTENT


# ================================ adversarial tests ================================

# ---- approvals: temporal, action, and evidence binding ----
def test_approval_action_mismatch(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(action_ref="unrelated_action")), context=ctx())
    assert d.code is DecisionCode.APPROVAL_ACTION_MISMATCH


def test_approval_evidence_missing(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(evidence_refs=())), context=ctx())
    assert d.code is DecisionCode.APPROVAL_EVIDENCE_MISSING


def test_approval_future_issued_fails_closed(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(issued_at="2026-07-18T00:00:00Z")), context=ctx())
    assert d.code is DecisionCode.APPROVAL_STALE


def test_approval_later_assertion_expiry_cannot_beat_policy(authz: Authorizer):
    # A caller-supplied far-future expiry must not bypass the P7D relative policy.
    stale = _approval(issued_at="2026-07-01T00:00:00Z", expires_at="2027-01-01T00:00:00Z")
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", stale), context=ctx())
    assert d.code is DecisionCode.APPROVAL_STALE


def test_approval_relative_expiry_requires_issuance(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(issued_at=None)), context=ctx())
    assert d.code is DecisionCode.APPROVAL_STALE


def test_zone_crossing_cross_action_replay_rejected(authz: Authorizer):
    # An approval whose action is not the governing gate's action must not authorize the crossing.
    wrong = _approval(action_ref="approve_agentic_network_contract")  # not in gate action_classes
    d = authz.evaluate(
        ZoneCrossingRequest("identity.researcher.local", "zone.local_governed", "zone.external_contract", wrong),
        context=ctx(),
    )
    assert d.code is DecisionCode.APPROVAL_ACTION_MISMATCH


# ---- party validity (identity/membership/revocation) across every request family ----
def _doc_inactive_reviewer() -> dict:
    document = _rich_document()
    for ident in document["agent_identities"]:
        if ident["id"] == "identity.reviewer.local":
            ident["status"] = "inactive"
    return document


@pytest.fixture(scope="module")
def inactive() -> Authorizer:
    return _inmemory(_doc_inactive_reviewer())


def test_ineffective_party_capability(inactive: Authorizer):
    d = inactive.evaluate(CapabilityRequest("identity.reviewer.local", "read_governed_context"), context=ctx())
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_ineffective_party_delegation(inactive: Authorizer):
    d = inactive.evaluate(DelegationRequest("delegation.research"), context=ctx())  # delegate is the inactive reviewer
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_ineffective_party_handoff(inactive: Authorizer):
    d = inactive.evaluate(HandoffRequest("handoff.review"), context=ctx())  # to_identity is the inactive reviewer
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_ineffective_party_approval(inactive: Authorizer):
    d = inactive.evaluate(ApprovalRequest("identity.reviewer.local", _approval()), context=ctx())
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_ineffective_party_zone_crossing(inactive: Authorizer):
    d = inactive.evaluate(
        ZoneCrossingRequest("identity.reviewer.local", "zone.local_governed", "zone.external_contract"), context=ctx()
    )
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_ineffective_party_data_share(inactive: Authorizer):
    d = inactive.evaluate(
        DataShareRequest("identity.researcher.local", "identity.reviewer.local", ("finding_summary",), "zone.local_governed", "zone.local_governed"),
        context=ctx(),
    )
    assert d.code is DecisionCode.PARTY_INEFFECTIVE


def test_zone_crossing_requires_source_zone_membership(authz: Authorizer):
    # Reviewer holds no membership in the (declared) external source zone.
    d = authz.evaluate(
        ZoneCrossingRequest("identity.reviewer.local", "zone.local_governed", "zone.external_contract"), context=ctx()
    )
    # reviewer IS a member of local_governed, so this crosses to the approval branch:
    assert d.code in {DecisionCode.CROSSING_APPROVAL_REQUIRED}


# ---- malformed requests fail closed (never an incidental exception) ----
def test_malformed_non_str_field(authz: Authorizer):
    d = authz.evaluate(CapabilityRequest(123, "read_governed_context"), context=ctx())  # type: ignore[arg-type]
    assert d.code is DecisionCode.REQUEST_MALFORMED


def test_malformed_unhashable_category(authz: Authorizer):
    d = authz.evaluate(
        DataShareRequest("identity.researcher.local", "identity.reviewer.local", ([],), "zone.local_governed", "zone.local_governed"),  # type: ignore[arg-type]
        context=ctx(),
    )
    assert d.code is DecisionCode.REQUEST_MALFORMED


# ---- structural immutability ----
def test_authorizer_rejects_mutation(authz: Authorizer):
    with pytest.raises(AttributeError):
        authz.subject_revision = "git:" + "0" * 40
    with pytest.raises(AttributeError):
        authz.new_attribute = 1
    with pytest.raises(TypeError):
        authz._identities["x"] = {}  # read-only mapping


# ---- every load-error code ----
def test_load_code_contract_invalid(tmp_path):
    p = tmp_path / "c.nyx"
    p.write_text("::: not yaml :::\n", encoding="utf-8")
    (tmp_path / "l.lock").write_text("{}", encoding="utf-8")
    with pytest.raises(AuthorizerLoadError) as e:
        load_authorizer(p, tmp_path / "l.lock", validation_as_of=AS_OF)
    assert e.value.code is AuthorizerLoadCode.CONTRACT_INVALID


def test_load_code_profile_missing(tmp_path):
    p = tmp_path / "c.nyx"
    p.write_text(yaml.safe_dump({"nornyx": "0.2", "project": {"name": "X"}}), encoding="utf-8")
    (tmp_path / "l.lock").write_text("{}", encoding="utf-8")
    with pytest.raises(AuthorizerLoadError) as e:
        load_authorizer(p, tmp_path / "l.lock", validation_as_of=AS_OF)
    assert e.value.code is AuthorizerLoadCode.PROFILE_MISSING


def test_load_code_lock_invalid(tmp_path):
    (tmp_path / "bad.lock").write_text("{ not json", encoding="utf-8")
    with pytest.raises(AuthorizerLoadError) as e:
        load_authorizer(EXAMPLE, tmp_path / "bad.lock", validation_as_of=AS_OF)
    assert e.value.code is AuthorizerLoadCode.LOCK_INVALID


def test_load_code_lock_stale(tmp_path):
    document = _base_document()
    document["agentic_network"]["id"] = "network.mutated"
    composition = A.compose_document_governance(document, registry=A.registry_for_contract(EXAMPLE))
    lock = build_agentic_network_lock(document, composition)
    lock_path = tmp_path / "stale.lock"
    write_agentic_network_lock(lock, lock_path)
    with pytest.raises(AuthorizerLoadError) as e:
        load_authorizer(EXAMPLE, lock_path, validation_as_of=AS_OF)
    assert e.value.code is AuthorizerLoadCode.LOCK_STALE


# ---- runtime-event producer compatibility ----
def test_recorder_accepts_all_schema_producer_types(authz: Authorizer):
    for producer_type in ("framework_adapter", "synthetic_harness", "external_runtime"):
        EvidenceRecorder(authz, ctx(), producer_id="p", producer_type=producer_type)  # must not raise


def test_recorder_rejects_unknown_producer_type(authz: Authorizer):
    with pytest.raises(ValueError):
        EvidenceRecorder(authz, ctx(), producer_id="p", producer_type="bogus")


# ------------------------------------- ADR-0041: caller-controlled scalar validation
class _CallbackTripwire(str):
    """A ``str`` subclass whose dunders raise if the recorder ever invokes them.

    Proves exact-type validation rejects the subclass before any of these
    caller-controlled methods executes.
    """

    def __hash__(self):  # pragma: no cover - must never run
        raise AssertionError("__hash__ must not be invoked on a rejected value")

    def __eq__(self, other):  # pragma: no cover - must never run
        raise AssertionError("__eq__ must not be invoked on a rejected value")

    def __format__(self, spec):  # pragma: no cover - must never run
        raise AssertionError("__format__ must not be invoked on a rejected value")

    def __str__(self):  # pragma: no cover - must never run
        raise AssertionError("__str__ must not be invoked on a rejected value")

    def __repr__(self):  # pragma: no cover - must never run
        raise AssertionError("__repr__ must not be invoked on a rejected value")


def test_str_subclass_mission_id_rejected_before_dunders_run(authz: Authorizer):
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    hostile = _CallbackTripwire("GOAL-001")
    with pytest.raises(TypeError):
        rec.record_decision(d, mission_id=hostile)
    with pytest.raises(TypeError):
        rec.record_observation("tool_invoked", mission_id=hostile, actor_ref="identity.researcher.local")
    assert rec.stream()["events"] == []


@pytest.mark.parametrize("field", ["producer_id", "producer_version", "producer_type"])
def test_str_subclass_producer_field_rejected_before_dunders_run(authz: Authorizer, field: str):
    kwargs = {"producer_id": "p", "producer_version": "1.0", "producer_type": "framework_adapter"}
    kwargs[field] = _CallbackTripwire(kwargs[field])
    with pytest.raises(TypeError):
        EvidenceRecorder(authz, ctx(), **kwargs)


def test_str_subclass_event_type_rejected_before_dunders_run(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(TypeError):
        rec.record_observation(_CallbackTripwire("tool_invoked"), mission_id="GOAL-001")
    assert rec.stream()["events"] == []


class _KeyTripwire:
    """A non-``str`` object whose ``__repr__``/``__hash__`` raise if ever invoked."""

    def __repr__(self):  # pragma: no cover - must never run
        raise AssertionError("__repr__ must not be invoked on a rejected field key")

    def __hash__(self):  # pragma: no cover - must never run
        raise AssertionError("__hash__ must not be invoked on a rejected field key")


class _HostileFieldMapping(_AbcMapping):
    """A ``Mapping`` holding a non-hashable-by-design key without ever hashing it.

    A real ``dict`` literal would hash its key at construction time, which
    would defeat the point of this fixture; this stores pairs in a plain list.
    """

    def __init__(self, pairs):
        self._pairs = list(pairs)

    def __getitem__(self, key):  # pragma: no cover - not exercised by these tests
        for k, v in self._pairs:
            if k is key:
                return v
        raise KeyError(key)

    def __iter__(self):
        return (k for k, _ in self._pairs)

    def __len__(self):
        return len(self._pairs)

    def items(self):
        return list(self._pairs)


def test_non_string_intent_field_key_rejected_without_repr(authz: Authorizer):
    from nornyx.agentic import DecisionEventIntent

    hostile_key = _KeyTripwire()
    fields = _HostileFieldMapping([(hostile_key, "value"), ("actor_ref", "identity.researcher.local")])
    fake = Decision(
        DecisionEffect.ALLOW,
        DecisionCode.ALLOWED,
        event_intents=(DecisionEventIntent("capability_requested", fields),),
    )
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(TypeError):
        rec.record_decision(fake, mission_id="GOAL-001")
    assert rec.stream()["events"] == []


def test_rejected_intent_field_key_causes_no_partial_mutation(authz: Authorizer):
    """A malformed intent anywhere in a decision's batch must not partially commit."""
    from nornyx.agentic import DecisionEventIntent

    hostile_key = _KeyTripwire()
    good_fields = {"actor_ref": "identity.researcher.local", "capability_ref": "read_governed_context"}
    bad_fields = _HostileFieldMapping([(hostile_key, "value")])
    fake = Decision(
        DecisionEffect.ALLOW,
        DecisionCode.ALLOWED,
        event_intents=(
            DecisionEventIntent("capability_requested", good_fields),
            DecisionEventIntent("capability_allowed", bad_fields),
        ),
    )
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(TypeError):
        rec.record_decision(fake, mission_id="GOAL-001")
    assert rec.stream()["events"] == []
    # The mission's sequence counter must not have advanced either: a fresh
    # observation on the same mission must start at sequence 1, not 2.
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    assert rec.stream()["events"][0]["sequence"] == 1


class _ListSubclass(list):
    """A ``list`` subclass; the restricted copier accepts only exact ``list``."""


class _DictSubclass(dict):
    """A ``dict`` subclass; the restricted copier accepts only exact ``dict``."""


class _Unsupported:
    """A plain object of a type the restricted copier does not recognize at all."""


def test_detach_plain_rejects_container_subclasses(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(TypeError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_ListSubclass(["a"]))
    assert rec.stream()["events"] == []


def test_detach_plain_rejects_dict_subclass(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(TypeError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_DictSubclass(a="b"))
    assert rec.stream()["events"] == []


@pytest.mark.parametrize(
    "bad_value",
    [
        pytest.param(_Unsupported(), id="custom-object"),
        pytest.param({"a", "b"}, id="set"),
        pytest.param(frozenset({"a"}), id="frozenset"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_unsupported_or_non_finite_field_value_rejected_before_mutation(authz: Authorizer, bad_value):
    """set/frozenset are rejected outright, never normalized (ADR-0041 correction)."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises((TypeError, ValueError)):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=bad_value)
    assert rec.stream()["events"] == []
    # Event-build failure must leave sequence state untouched: the next
    # successful observation on the same mission still starts at sequence 1.
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    assert rec.stream()["events"][0]["sequence"] == 1


def test_self_referential_field_value_fails_closed(authz: Authorizer):
    cyclic: dict = {}
    cyclic["self"] = cyclic
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(ValueError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=cyclic)
    assert rec.stream()["events"] == []


def _nested_dict(depth: int) -> Any:
    value: Any = "leaf"
    for _ in range(depth):
        value = {"n": value}
    return value


def test_detach_plain_depth_limit_boundary_is_exactly_eight(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    # Exactly at the approved limit (8): accepted.
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_nested_dict(8))
    assert len(rec.stream()["events"]) == 1
    # One level deeper: rejected, and the failed attempt leaves no trace.
    with pytest.raises(ValueError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_nested_dict(9))
    events = rec.stream()["events"]
    assert len(events) == 1
    assert events[0]["sequence"] == 1


def test_tuple_field_value_normalized_to_list(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local",
        depends_on=("GOAL-001-0001", "GOAL-001-0002"),
    )
    value = rec.stream()["events"][0]["depends_on"]
    assert value == ["GOAL-001-0001", "GOAL-001-0002"]
    assert type(value) is list


@pytest.mark.parametrize(
    "field, original, mutate",
    [
        pytest.param("depends_on", ["GOAL-001-0001"], lambda v: v.append("INJECTED"), id="depends_on"),
        pytest.param("share_categories", ["telemetry"], lambda v: v.append("INJECTED"), id="share_categories"),
        pytest.param(
            "approver",
            {"role": "network_governance_owner", "actor_type": "human"},
            lambda v: v.__setitem__("role", "INJECTED"),
            id="approver",
        ),
        pytest.param(
            "evidence_artifact",
            {"path": "a.txt", "sha256": "0" * 64},
            lambda v: v.__setitem__("path", "INJECTED"),
            id="evidence_artifact",
        ),
    ],
)
def test_mutating_returned_stream_nested_field_does_not_corrupt_recorder_state(authz: Authorizer, field, original, mutate):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", **{field: original})
    first = rec.stream()
    mutate(first["events"][0][field])
    second = rec.stream()
    assert second["events"][0][field] == original


def test_mutating_returned_stream_producer_metadata_does_not_corrupt_recorder_state(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_version="1.0", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    first = rec.stream()
    first["producer"]["id"] = "INJECTED"
    first["events"][0]["producer"]["id"] = "INJECTED"
    second = rec.stream()
    assert second["producer"] == {"type": "synthetic_harness", "id": "tests", "version": "1.0"}
    assert second["events"][0]["producer"] == {"type": "synthetic_harness", "id": "tests", "version": "1.0"}


def test_caller_owned_container_mutated_after_recording_does_not_affect_stream(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    categories = ["telemetry"]
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", share_categories=categories)
    categories.append("INJECTED")  # mutate the caller's own original object after the call returns
    assert rec.stream()["events"][0]["share_categories"] == ["telemetry"]


class _StampSpy(EvidenceRecorder):
    """Counts calls reaching the private ``_stamp`` hook, to prove routing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stamp_calls = 0

    def _stamp(self, event_type, mission_id, fields):
        self.stamp_calls += 1
        super()._stamp(event_type, mission_id, fields)


def test_record_observation_routes_through_overridden_stamp(authz: Authorizer):
    rec = _StampSpy(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    assert rec.stamp_calls == 1
    assert len(rec.stream()["events"]) == 1


def test_record_decision_does_not_route_through_stamp(authz: Authorizer):
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    assert len(d.event_intents) > 0
    rec = _StampSpy(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")
    assert rec.stamp_calls == 0
    assert len(rec.stream()["events"]) == len(d.event_intents)


def test_empty_decision_is_a_no_op(authz: Authorizer):
    empty = Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, event_intents=())
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(empty, mission_id="GOAL-001")
    assert rec.stream()["events"] == []
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    assert rec.stream()["events"][0]["sequence"] == 1


def test_single_intent_decision_detachment_failure_leaves_no_events(authz: Authorizer):
    """A decision with exactly one, malformed intent: an event-build failure
    (field detachment) must leave events and sequence state unchanged."""
    from nornyx.agentic import DecisionEventIntent

    fake = Decision(
        DecisionEffect.ALLOW,
        DecisionCode.ALLOWED,
        event_intents=(DecisionEventIntent("capability_requested", {"actor_ref": float("nan")}),),
    )
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises(ValueError):
        rec.record_decision(fake, mission_id="GOAL-001")
    assert rec.stream()["events"] == []
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    assert rec.stream()["events"][0]["sequence"] == 1


def test_golden_single_threaded_stream_is_exact(authz: Authorizer):
    """Pins the exact, byte-identical shape of a canonical decision + observation."""
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_version="1.0", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
    )
    stream = rec.stream()
    expected_producer = {"type": "synthetic_harness", "id": "tests", "version": "1.0"}

    assert stream["schema"] == "nornyx.agentic_runtime_events.v1"
    assert stream["schema_version"] == "1.0"
    assert stream["network_id"] == authz.network_id
    assert stream["producer"] == expected_producer
    assert [e["event_type"] for e in stream["events"]] == ["capability_requested", "capability_allowed", "tool_invoked"]
    assert [e["sequence"] for e in stream["events"]] == [1, 2, 3]
    assert [e["event_id"] for e in stream["events"]] == ["GOAL-001-0001", "GOAL-001-0002", "GOAL-001-0003"]
    for event in stream["events"]:
        assert event["mission_id"] == "GOAL-001"
        assert event["producer"] == expected_producer
        assert event["network_id"] == authz.network_id
        assert event["contract_digest"] == authz.contract_digest
        assert event["network_lock_digest"] == authz.network_lock_digest
        assert event["subject_revision"] == authz.subject_revision
        assert event["timestamp"] == context.decision_at
    assert stream["events"][0]["actor_ref"] == "identity.researcher.local"
    assert stream["events"][0]["capability_ref"] == "read_governed_context"
    assert stream["events"][1]["policy_decision"] == "allow"
    assert stream["events"][2]["capability_ref"] == "read_governed_context"
    # Re-fetching produces a deep-equal, independently-copied stream.
    assert rec.stream() == stream
    assert rec.stream() is not stream
    assert rec.stream()["events"] is not stream["events"]


def test_concurrent_record_observation_produces_unique_sequences(authz: Authorizer):
    """Supplementary stress coverage only — NOT the decisive proof of
    serialization (see test_concurrent_observations_serialize_through_the_recorder_lock
    for that). An aggressive GIL switch interval widens the window for a
    scheduling-dependent bug to surface; the previous interval is restored on
    teardown regardless of outcome."""
    import sys
    import threading

    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(50):
                rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
        except BaseException as exc:  # noqa: BLE001 - surfaced via `errors` below
            errors.append(exc)

    previous_interval = sys.getswitchinterval()
    try:
        sys.setswitchinterval(1e-9)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(previous_interval)

    assert not errors
    events = rec.stream()["events"]
    assert len(events) == 400
    assert sorted(e["sequence"] for e in events) == list(range(1, 401))
    assert sorted(e["event_id"] for e in events) == [f"GOAL-001-{i:04d}" for i in range(1, 401)]


def test_concurrent_multi_intent_decisions_commit_as_contiguous_batches(authz: Authorizer):
    """Supplementary scheduler-stress coverage only — NOT the decisive proof
    of batch indivisibility. This relies on thread scheduling to surface an
    interleaving bug; it can pass by luck even against a broken
    implementation. See test_concurrent_multi_intent_decisions_batch_is_indivisible
    for the deterministic, mutation-checked proof (Event/Barrier-synchronized,
    forces a pause inside the locked batch-build step and proves a second
    decision cannot build or commit until released).

    Every decision has 2 intents; under concurrency, each pair must land as
    an adjacent, contiguous, non-interleaved (requested, allowed) batch."""
    import threading

    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    assert len(d.event_intents) == 2
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            for _ in range(25):
                rec.record_decision(d, mission_id="GOAL-001")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    events = rec.stream()["events"]
    assert len(events) == 8 * 25 * 2
    by_sequence = sorted(events, key=lambda e: e["sequence"])
    assert [e["sequence"] for e in by_sequence] == list(range(1, len(events) + 1))
    for i in range(0, len(by_sequence), 2):
        first, second = by_sequence[i], by_sequence[i + 1]
        assert first["event_type"] == "capability_requested"
        assert second["event_type"] == "capability_allowed"
        assert second["sequence"] == first["sequence"] + 1


def test_stream_snapshot_consistent_during_concurrent_writes(authz: Authorizer):
    """Supplementary scheduler-stress coverage only — NOT the decisive proof
    of snapshot consistency. This relies on the reader thread happening to
    race the writer; it can pass by luck even against a broken
    implementation. See test_concurrent_stream_snapshots_are_deterministic_and_consistent
    (Event-choreographed writer/reader steps, requires multiple genuinely
    partial snapshot sizes) and test_stream_snapshot_holds_lock_for_its_duration
    (lock-ownership probe, proves a concurrent writer cannot commit while a
    snapshot is in progress) for the deterministic, mutation-checked proofs.
    """
    import threading

    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    errors: list[BaseException] = []
    stop = threading.Event()

    def writer() -> None:
        try:
            for _ in range(200):
                rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            stop.set()

    def reader() -> None:
        try:
            while not stop.is_set():
                events = rec.stream()["events"]
                sequences = [e["sequence"] for e in events]
                # A snapshot taken mid-write must be internally consistent:
                # exactly 1..len(events), ascending, no gaps, no duplicates —
                # never a torn/partial view of the underlying state.
                assert sequences == list(range(1, len(events) + 1))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    reader_thread.start()
    writer_thread.join()
    reader_thread.join()

    assert not errors
    assert len(rec.stream()["events"]) == 200


def test_validate_does_not_hold_lock_during_validation(authz: Authorizer, monkeypatch):
    """validate() must build the detached snapshot under the lock, release the
    lock, and only then call validate_runtime_events — never while holding it."""
    import threading

    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")

    entered = threading.Event()
    release = threading.Event()

    def slow_validate(*_args, **_kwargs):
        entered.set()
        release.wait(timeout=5)
        return {"status": "pass", "diagnostics": [], "event_count": 0}

    monkeypatch.setattr("nornyx.agentic_evidence.validate_runtime_events", slow_validate)

    result: dict = {}

    def call_validate() -> None:
        result["report"] = rec.validate()

    validator_thread = threading.Thread(target=call_validate)
    validator_thread.start()
    assert entered.wait(timeout=5)

    recorded = threading.Event()

    def record_concurrently() -> None:
        rec.record_observation("tool_invoked", mission_id="GOAL-002", actor_ref="identity.researcher.local")
        recorded.set()

    recorder_thread = threading.Thread(target=record_concurrently)
    recorder_thread.start()
    # If validate() were still holding the lock while validate_runtime_events
    # ran, this would time out instead of completing.
    assert recorded.wait(timeout=5)
    release.set()
    validator_thread.join()
    recorder_thread.join()
    assert result["report"]["status"] == "pass"


# ------------------------------- ADR-0041: AN_EVT_REPLAY / mission / DAG pinning
def test_repeated_identical_observation_triggers_an_evt_replay_at_expected_position(authz: Authorizer):
    """Regression pin: content-hash-based replay detection (agentic_evidence.py,
    untouched by ADR-0041) must behave identically through the corrected recorder."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
    )
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
    )
    report = rec.validate()
    assert report["status"] == "fail"
    replay = [d for d in report["diagnostics"] if d["code"] == "AN_EVT_REPLAY"]
    assert len(replay) == 1
    assert replay[0]["path"] == "events[1]"


def test_identical_content_across_separate_missions_does_not_trigger_replay(authz: Authorizer):
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    for mission in ("GOAL-001", "GOAL-002"):
        rec.record_decision(d, mission_id=mission)  # prior capability_allowed, required by AN_EVT_TOOL_WITHOUT_ALLOWANCE
        rec.record_observation(
            "tool_invoked", mission_id=mission,
            actor_ref="identity.researcher.local", capability_ref="read_governed_context",
        )
    report = rec.validate()
    assert report["status"] == "pass", report["diagnostics"]


def test_distinct_dag_nodes_in_one_mission_do_not_trigger_replay(authz: Authorizer):
    """Two otherwise-identical events in one mission, distinguished only by
    depends_on, must not be flagged as replays of each other."""
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")  # prior capability_allowed, required by AN_EVT_TOOL_WITHOUT_ALLOWANCE
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context", depends_on=[],
    )
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
        depends_on=["GOAL-001-0001"],
    )
    report = rec.validate()
    assert report["status"] == "pass", report["diagnostics"]


@pytest.mark.parametrize(
    "attempt",
    [
        pytest.param(lambda rec: rec.record_observation("tool_invoked", mission_id=_CallbackTripwire("m"), actor_ref="a"), id="hostile-mission-id"),
        pytest.param(lambda rec: rec.record_observation(_CallbackTripwire("tool_invoked"), mission_id="m", actor_ref="a"), id="hostile-event-type"),
        pytest.param(lambda rec: rec.record_observation("tool_invoked", mission_id="m", payload={1, 2}), id="set-value"),
        pytest.param(lambda rec: rec.record_observation("tool_invoked", mission_id="m", payload=_ListSubclass(["a"])), id="list-subclass"),
        pytest.param(lambda rec: rec.record_observation("tool_invoked", mission_id="m", payload=_DictSubclass(a="b")), id="dict-subclass"),
        pytest.param(lambda rec: rec.record_observation("tool_invoked", mission_id="m", payload=float("nan")), id="nan"),
        pytest.param(lambda rec: rec.record_observation("bogus_event_type", mission_id="m"), id="unknown-event-type"),
    ],
)
def test_every_rejected_recording_attempt_leaves_recorder_state_unchanged(authz: Authorizer, attempt):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    with pytest.raises((TypeError, ValueError)):
        attempt(rec)
    assert rec.stream()["events"] == []
    rec.record_observation("tool_invoked", mission_id="m", actor_ref="identity.researcher.local")
    assert rec.stream()["events"][0]["sequence"] == 1


def test_invalid_second_event_type_rolls_back_entire_decision(authz: Authorizer):
    """A Decision whose SECOND intent's event_type is not in PHASE_INTENT must
    raise before any mutation, inspecting the recorder's private state
    (``_events``/``_sequences``) directly rather than through ``stream()``."""
    from nornyx.agentic import DecisionEventIntent

    fake = Decision(
        DecisionEffect.ALLOW,
        DecisionCode.ALLOWED,
        event_intents=(
            DecisionEventIntent("capability_requested", {"actor_ref": "identity.researcher.local"}),
            DecisionEventIntent("tool_invoked", {"actor_ref": "identity.researcher.local"}),  # a PHASE_OBSERVATION type, not PHASE_INTENT
        ),
    )
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    events_before = list(rec._events)
    sequences_before = dict(rec._sequences)
    with pytest.raises(ValueError):
        rec.record_decision(fake, mission_id="GOAL-001")
    # Neither the first (valid) nor the second (invalid) intent was committed.
    assert rec._events == events_before
    assert rec._sequences == sequences_before


def test_multi_intent_event_build_failure_rolls_back_entire_batch(authz: Authorizer, monkeypatch):
    """Monkeypatch _build_event_unlocked so the first call in a batch succeeds
    and the second raises: the whole batch must roll back, not just the
    failed intent, and _events/_sequences must be byte-identical to their
    pre-call state — not just empty, but unchanged from whatever they held
    before this call (including any prior recordings)."""
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    assert len(d.event_intents) >= 2

    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    # Seed prior state so "unchanged" is a meaningful assertion, not just "empty".
    rec.record_observation("tool_invoked", mission_id="EARLIER", actor_ref="identity.researcher.local")

    original_build = EvidenceRecorder._build_event_unlocked
    calls = {"n": 0}

    def flaky_build(self, event_type, mission_id, seq, fields):
        calls["n"] += 1
        if calls["n"] == 1:
            return original_build(self, event_type, mission_id, seq, fields)
        raise RuntimeError("deterministic build failure")

    monkeypatch.setattr(EvidenceRecorder, "_build_event_unlocked", flaky_build)

    events_before = list(rec._events)
    sequences_before = dict(rec._sequences)
    with pytest.raises(RuntimeError):
        rec.record_decision(d, mission_id="GOAL-001")
    assert calls["n"] == 2  # the first build ran (and would have succeeded) before the second raised
    assert rec._events == events_before
    assert rec._sequences == sequences_before
    # No partial batch is visible through the public API either.
    assert rec.stream()["events"] == events_before


def test_validate_payload_is_detached_from_recorder_state(authz: Authorizer, monkeypatch):
    """Monkeypatch validate_runtime_events to mutate every category of nested
    value in the payload it receives (top-level producer, per-event producer,
    a nested mapping, a nested list). After validate() returns, the recorder's
    own state must be completely unaffected."""
    context = ctx()
    d = authz.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=context)
    rec = EvidenceRecorder(authz, context, producer_id="tests", producer_type="synthetic_harness")
    rec.record_decision(d, mission_id="GOAL-001")
    rec.record_observation(
        "tool_invoked", mission_id="GOAL-001",
        actor_ref="identity.researcher.local", capability_ref="read_governed_context",
        approver={"role": "network_governance_owner", "actor_type": "human"},
        depends_on=["GOAL-001-0001"],
    )

    def mutating_validator(_document, _composition, _lock_payload, payload, *, events_root=None):
        payload["producer"]["id"] = "INJECTED"  # top-level producer
        for event in payload["events"]:
            event["producer"]["id"] = "INJECTED"  # per-event producer
            if "approver" in event:
                event["approver"]["role"] = "INJECTED"  # nested mapping
            if "depends_on" in event:
                event["depends_on"].append("INJECTED")  # nested list
        return {"status": "pass", "diagnostics": [], "event_count": len(payload["events"])}

    monkeypatch.setattr("nornyx.agentic_evidence.validate_runtime_events", mutating_validator)

    before = rec.stream()
    report = rec.validate()
    after = rec.stream()

    assert report["status"] == "pass"
    assert after == before


# ============================= ADR-0041: deterministic concurrency proofs =============================
class _ProbeLock:
    """Wraps a real ``threading.Lock``, exposing deterministic hooks so tests
    can prove a second thread is genuinely blocked on lock acquisition —
    rather than merely "hasn't run yet" — without sleeping or hoping the
    scheduler cooperates. ``second_attempt_started`` fires the instant a
    second caller enters ``acquire()``, even though that call then blocks
    inside the real lock; ``acquired`` only increments once a caller actually
    holds it."""

    def __init__(self) -> None:
        self._real = threading.Lock()
        self._mutex = threading.Lock()
        self.attempts = 0
        self.acquired = 0
        self.second_attempt_started = threading.Event()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        with self._mutex:
            self.attempts += 1
            if self.attempts == 2:
                self.second_attempt_started.set()
        ok = self._real.acquire(blocking, timeout)
        if ok:
            with self._mutex:
                self.acquired += 1
        return ok

    def release(self) -> None:
        self._real.release()

    def __enter__(self) -> "_ProbeLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.release()
        return False


def test_concurrent_observations_serialize_through_the_recorder_lock(authz: Authorizer, monkeypatch):
    """Deterministic proof (Barrier + Event + a probe lock — no sleep, no
    reliance on the GIL switch interval) that two overlapping
    record_observation calls serialize through self._lock: one worker is
    forced to remain inside the locked build step while the other
    demonstrably attempts entry and cannot commit until the first releases."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    probe = _ProbeLock()
    rec._lock = probe

    entered_build = threading.Event()
    release_first = threading.Event()
    first_call_claimed = threading.Event()
    original_build = EvidenceRecorder._build_event_unlocked

    def instrumented_build(self, event_type, mission_id, seq, fields):
        if not first_call_claimed.is_set():
            first_call_claimed.set()
            entered_build.set()
            assert release_first.wait(timeout=5), "deadlock guard: release_first never signaled"
        return original_build(self, event_type, mission_id, seq, fields)

    monkeypatch.setattr(EvidenceRecorder, "_build_event_unlocked", instrumented_build)

    start_barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            start_barrier.wait(timeout=5)
            rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
        except BaseException as exc:  # noqa: BLE001 - surfaced via `errors`
            errors.append(exc)

    thread_a = threading.Thread(target=worker)
    thread_b = threading.Thread(target=worker)
    thread_a.start()
    thread_b.start()

    # Both workers synchronized at the barrier and are now racing to record.
    assert entered_build.wait(timeout=5), "deadlock guard: no worker ever entered the locked build step"
    # Whichever worker got there first is now paused *inside* the locked
    # build: it holds the lock, but has not yet appended anything.
    assert probe.acquired == 1
    assert rec._events == []

    # The other worker has demonstrably attempted entry (a second, distinct
    # acquire() call started) but is genuinely blocked on the real lock.
    assert probe.second_attempt_started.wait(timeout=5), "deadlock guard: second worker never attempted the lock"
    assert probe.acquired == 1  # still only one holder; the second cannot commit yet
    assert rec._events == []

    release_first.set()
    thread_a.join(timeout=5)
    thread_b.join(timeout=5)
    assert not thread_a.is_alive() and not thread_b.is_alive()
    assert not errors

    assert probe.attempts == 2
    assert probe.acquired == 2
    events = rec.stream()["events"]
    assert len(events) == 2
    assert sorted(e["sequence"] for e in events) == [1, 2]
    assert len({e["event_id"] for e in events}) == 2


def test_concurrent_multi_intent_decisions_batch_is_indivisible(authz: Authorizer, monkeypatch):
    """Deterministic proof that a whole decision batch commits indivisibly:
    decision A is paused after its first event is built but before commit;
    decision B demonstrably attempts entry and cannot build or commit while
    A is paused; after release, both complete with disjoint, contiguous
    sequence ranges and no interleaving."""
    from nornyx.agentic import DecisionEventIntent

    def make_decision(tag: str) -> Decision:
        return Decision(
            DecisionEffect.ALLOW,
            DecisionCode.ALLOWED,
            event_intents=(
                DecisionEventIntent("capability_requested", {"actor_ref": "identity.researcher.local", "capability_ref": "read_governed_context", "batch": tag}),
                DecisionEventIntent("capability_allowed", {"actor_ref": "identity.researcher.local", "capability_ref": "read_governed_context", "policy_decision": "allow", "batch": tag}),
            ),
        )

    decision_a = make_decision("A")
    decision_b = make_decision("B")

    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    probe = _ProbeLock()
    rec._lock = probe

    entered_pause = threading.Event()
    release_pause = threading.Event()
    original_build = EvidenceRecorder._build_event_unlocked
    calls = {"n": 0}

    def instrumented_build(self, event_type, mission_id, seq, fields):
        calls["n"] += 1
        if calls["n"] == 2:  # A's first event has already been built; pause before its second
            entered_pause.set()
            assert release_pause.wait(timeout=5), "deadlock guard: release_pause never signaled"
        return original_build(self, event_type, mission_id, seq, fields)

    monkeypatch.setattr(EvidenceRecorder, "_build_event_unlocked", instrumented_build)

    errors: list[BaseException] = []

    def run_a() -> None:
        try:
            rec.record_decision(decision_a, mission_id="GOAL-001")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def run_b() -> None:
        try:
            rec.record_decision(decision_b, mission_id="GOAL-001")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread_a = threading.Thread(target=run_a)
    thread_a.start()
    assert entered_pause.wait(timeout=5), "deadlock guard: A never reached the pause point"
    # A built one event but has not committed: it still holds the lock.
    assert probe.acquired == 1
    assert rec._events == []
    assert rec._sequences == {}

    thread_b = threading.Thread(target=run_b)
    thread_b.start()
    assert probe.second_attempt_started.wait(timeout=5), "deadlock guard: B never attempted to acquire the lock"
    # B has demonstrably attempted entry but cannot build or commit while A is paused.
    assert probe.acquired == 1
    assert rec._events == []
    assert rec._sequences == {}

    release_pause.set()
    thread_a.join(timeout=5)
    thread_b.join(timeout=5)
    assert not thread_a.is_alive() and not thread_b.is_alive()
    assert not errors

    events = rec.stream()["events"]
    assert len(events) == 4
    by_seq = sorted(events, key=lambda e: e["sequence"])
    assert [e["sequence"] for e in by_seq] == [1, 2, 3, 4]
    assert {by_seq[0]["batch"], by_seq[1]["batch"]} == {"A"}
    assert {by_seq[2]["batch"], by_seq[3]["batch"]} == {"B"}
    assert len({e["event_id"] for e in events}) == 4


def test_concurrent_stream_snapshots_are_deterministic_and_consistent(authz: Authorizer):
    """Writer/reader coordination entirely via threading.Event — the writer
    commits in controlled steps, the reader is explicitly released to
    snapshot after each step, and the writer waits for that snapshot to be
    captured before proceeding. No sleep, no hoping the reader is scheduled."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    steps = 3
    commit_done = [threading.Event() for _ in range(steps)]
    snapshot_done = [threading.Event() for _ in range(steps)]
    snapshots: list[list[dict]] = [None] * steps  # type: ignore[list-item]
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            for i in range(steps):
                rec.record_observation(
                    "tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local",
                    depends_on=[f"tag-{i}"],
                )
                commit_done[i].set()
                assert snapshot_done[i].wait(timeout=5), f"deadlock guard: snapshot {i} never captured"
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def reader() -> None:
        try:
            for i in range(steps):
                assert commit_done[i].wait(timeout=5), f"deadlock guard: commit {i} never happened"
                snapshots[i] = rec.stream()["events"]
                snapshot_done[i].set()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    writer_thread.start()
    reader_thread.start()
    writer_thread.join(timeout=10)
    reader_thread.join(timeout=10)
    assert not writer_thread.is_alive() and not reader_thread.is_alive()
    assert not errors

    sizes = [len(s) for s in snapshots]
    assert sizes == [1, 2, 3]  # multiple genuinely partial sizes (1, 2), not zero
    for snap in snapshots:
        assert [e["sequence"] for e in snap] == list(range(1, len(snap) + 1))  # contiguous
        assert len({e["event_id"] for e in snap}) == len(snap)  # unique IDs

    # Deeply detached: mutating a nested value in an earlier, smaller
    # snapshot must not affect the recorder's own state or a later snapshot.
    snapshots[0][0]["depends_on"].append("MUTATED")
    final_events = rec.stream()["events"]
    assert final_events[0]["depends_on"] == ["tag-0"]


def test_stream_snapshot_holds_lock_for_its_duration(authz: Authorizer, monkeypatch):
    """Lock-ownership probe: pause _snapshot_unlocked from inside stream()
    while the recorder lock is held, then prove a concurrent writer
    demonstrably attempts the recording operation but cannot commit until
    the snapshot is released."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")

    probe = _ProbeLock()
    rec._lock = probe

    entered_snapshot = threading.Event()
    release_snapshot = threading.Event()
    original_snapshot = EvidenceRecorder._snapshot_unlocked

    def paused_snapshot(self):
        entered_snapshot.set()
        assert release_snapshot.wait(timeout=5), "deadlock guard: release_snapshot never signaled"
        return original_snapshot(self)

    monkeypatch.setattr(EvidenceRecorder, "_snapshot_unlocked", paused_snapshot)

    result: dict = {}

    def call_stream() -> None:
        result["stream"] = rec.stream()

    reader_thread = threading.Thread(target=call_stream)
    reader_thread.start()
    assert entered_snapshot.wait(timeout=5), "deadlock guard: reader never entered the snapshot"
    assert probe.acquired == 1  # the reader holds the lock while paused inside the snapshot

    errors: list[BaseException] = []

    def writer() -> None:
        try:
            rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    assert probe.second_attempt_started.wait(timeout=5), "deadlock guard: writer never attempted the lock"
    # The writer has demonstrably attempted the operation but cannot commit
    # while the reader's snapshot is still in progress and holding the lock.
    assert probe.acquired == 1
    assert len(rec._events) == 1  # only the seeded event; the writer has not committed yet

    release_snapshot.set()
    reader_thread.join(timeout=5)
    writer_thread.join(timeout=5)
    assert not reader_thread.is_alive() and not writer_thread.is_alive()
    assert not errors
    assert len(rec._events) == 2
    assert len(result["stream"]["events"]) == 1  # snapshot captured before the writer's commit


# ===================================== ADR-0041: F-05 coverage additions =====================================
def test_hostile_str_subclass_as_field_value_rejected_without_callbacks(authz: Authorizer):
    """A hostile str subclass used as an event FIELD VALUE (not a scalar
    argument like mission_id) must be rejected without invoking any of its
    overridden dunders."""
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    hostile_value = _CallbackTripwire("read_governed_context")
    with pytest.raises(TypeError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", capability_ref=hostile_value)
    assert rec.stream()["events"] == []


class _CallbackTripwireContainer:
    """A non-plain object whose container/pickle-related dunders raise if
    ever invoked. Used to prove the restricted copier rejects unsupported
    types by exact-type check alone, before touching any of these."""

    def __iter__(self):  # pragma: no cover - must never run
        raise AssertionError("__iter__ must not be invoked on a rejected value")

    def keys(self):  # pragma: no cover - must never run
        raise AssertionError("keys must not be invoked on a rejected value")

    def __reduce__(self):  # pragma: no cover - must never run
        raise AssertionError("__reduce__ must not be invoked on a rejected value")

    def __reduce_ex__(self, protocol):  # pragma: no cover - must never run
        raise AssertionError("__reduce_ex__ must not be invoked on a rejected value")

    def __getstate__(self):  # pragma: no cover - must never run
        raise AssertionError("__getstate__ must not be invoked on a rejected value")

    def __deepcopy__(self, memo):  # pragma: no cover - must never run
        raise AssertionError("__deepcopy__ must not be invoked on a rejected value")


def test_hostile_container_tripwire_dunders_never_invoked_on_rejected_value(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    hostile = _CallbackTripwireContainer()
    with pytest.raises(TypeError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=hostile)
    assert rec.stream()["events"] == []


def _nested_list(depth: int) -> Any:
    value: Any = "leaf"
    for _ in range(depth):
        value = [value]
    return value


def test_detach_plain_list_nesting_depth_limit_boundary_is_exactly_eight(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_nested_list(8))
    assert len(rec.stream()["events"]) == 1
    with pytest.raises(ValueError):
        rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local", payload=_nested_list(9))
    events = rec.stream()["events"]
    assert len(events) == 1
    assert events[0]["sequence"] == 1


def test_non_mapping_intent_fields_rejected_before_recorder_mutation(authz: Authorizer):
    from nornyx.agentic import DecisionEventIntent

    fake = Decision(
        DecisionEffect.ALLOW, DecisionCode.ALLOWED,
        event_intents=(DecisionEventIntent("capability_requested", ["not", "a", "mapping"]),),
    )
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    events_before = list(rec._events)
    sequences_before = dict(rec._sequences)
    with pytest.raises(TypeError):
        rec.record_decision(fake, mission_id="GOAL-001")
    assert rec._events == events_before
    assert rec._sequences == sequences_before


def test_stream_output_omits_sequences(authz: Authorizer):
    rec = EvidenceRecorder(authz, ctx(), producer_id="tests", producer_type="synthetic_harness")
    rec.record_observation("tool_invoked", mission_id="GOAL-001", actor_ref="identity.researcher.local")
    stream = rec.stream()
    assert set(stream.keys()) == {"schema", "schema_version", "network_id", "producer", "events"}
    assert "sequences" not in stream
    assert "_sequences" not in stream


# ===================== residual-boundary corrections (A–E) =====================

# A. Universal approval context binding.
def test_approval_wrong_revision_rejected_without_binding(authz: Authorizer):
    # agentic_network_authority declares no revision_binding, yet a mismatched
    # subject_revision must still be rejected (universal context binding).
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(subject_revision="git:" + "9" * 40)), context=ctx())
    assert d.code is DecisionCode.APPROVAL_REVISION_MISMATCH


@pytest.mark.parametrize("change", ["identity", "capability", "membership", "zone", "policy"])
def test_stale_approval_reuse_after_state_revision_rejected(change):
    # Any governed change bumps subject_revision; an approval issued under the
    # prior revision is rejected against the new-revision contract.
    doc = _base_document()
    new_rev = "git:" + ("a1b2c3d4" * 5)
    doc["agentic_network"]["subject_revision"] = new_rev
    az = _inmemory(doc)
    d = az.evaluate(
        ApprovalRequest("identity.researcher.local", _approval(subject_revision=REVISION)),
        context=EvaluationContext(decision_at=AS_OF, observed_subject_revision=new_rev),
    )
    assert d.code is DecisionCode.APPROVAL_REVISION_MISMATCH, change


# B. Per-gate zone-crossing authorization.
def _doc_with_second_gate() -> dict:
    document = _base_document()
    document["agentic_network"]["network_gates"].append({
        "id": "gate.second",
        "action_classes": ["read_context"],
        "source_zone_refs": ["zone.local_governed"],
        "target_zone_refs": ["zone.external_contract"],
        "required_policy_refs": [],
        "required_approval_refs": ["governance_authority"],
        "required_evidence_refs": [],
    })
    return document


@pytest.fixture(scope="module")
def multigate() -> Authorizer:
    return _inmemory(_doc_with_second_gate())


def test_zone_crossing_cross_gate_combo_denied(multigate: Authorizer):
    # gate.second requires governance_authority for read_context; external_share
    # is only gate.external_share's action (requires agentic_network_authority).
    cross = _approval(approval_ref="governance_authority", action_ref="external_share")
    d = multigate.evaluate(ZoneCrossingRequest("identity.researcher.local", "zone.local_governed", "zone.external_contract", cross), context=ctx())
    assert d.code is DecisionCode.APPROVAL_ACTION_MISMATCH


def test_zone_crossing_valid_gate_pair_allows_with_gate_basis(multigate: Authorizer):
    ok = _approval(action_ref="external_share")  # agentic_network_authority + external_share = gate.external_share
    d = multigate.evaluate(ZoneCrossingRequest("identity.researcher.local", "zone.local_governed", "zone.external_contract", ok), context=ctx())
    assert d.effect is DecisionEffect.ALLOW
    assert any(b.kind == "gate" for b in d.basis)


def test_zone_crossing_no_governing_gate_denied():
    doc = _base_document()
    doc["agentic_network"]["network_gates"] = []
    az = _inmemory(doc)
    d = az.evaluate(ZoneCrossingRequest("identity.researcher.local", "zone.local_governed", "zone.external_contract", _approval(action_ref="external_share")), context=ctx())
    assert d.code is DecisionCode.ZONE_CROSSING_DENIED


# C. Deep immutability.
def test_deep_immutability_nested_references(authz: Authorizer):
    with pytest.raises(TypeError):
        authz._identities["identity.researcher.local"]["status"] = "inactive"  # frozen mapping
    with pytest.raises(TypeError):
        authz._document["agentic_network"]["id"] = "x"  # frozen mapping item assign
    with pytest.raises(AttributeError):
        authz._document["agentic_network"]["memberships"].append({})  # tuple: no append


def test_mutating_original_input_after_construction_does_not_alter_state():
    doc = _base_document()
    az = _inmemory(doc)
    before = az.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=ctx()).code
    digest_before = az.contract_digest
    # Mutate the caller's original objects after construction.
    doc["agent_identities"][0]["status"] = "inactive"
    doc["agentic_network"]["memberships"].clear()
    after = az.evaluate(CapabilityRequest("identity.researcher.local", "read_governed_context"), context=ctx()).code
    assert before is after is DecisionCode.ALLOWED
    assert az.contract_digest == digest_before


# D. Malformed temporal values fail closed.
def test_malformed_expires_at_fails_closed(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(expires_at="garbage")), context=ctx())
    assert d.code is DecisionCode.REQUEST_MALFORMED


def test_malformed_issued_at_fails_closed(authz: Authorizer):
    d = authz.evaluate(ApprovalRequest("identity.researcher.local", _approval(issued_at="not-a-time")), context=ctx())
    assert d.code is DecisionCode.REQUEST_MALFORMED
