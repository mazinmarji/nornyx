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
