"""Direct-vs-AuthZEN semantic equivalence, on a real loaded Authorizer.

The existing AuthZEN suite proves the codec in isolation and exercises the local
bridge against a ``_StubAuthorizer``. A stub returns whatever decision the test
handed it, so it can demonstrate that the bridge *plumbs* a decision, but it
cannot demonstrate that the two paths agree about a decision Nornyx actually
made. This module closes that: every case here runs through a contract loaded
and lock-verified by :func:`load_authorizer`, the authoritative public load
path.

WHAT "EQUIVALENT DECISION MEANING" MEANS HERE, EXACTLY
-----------------------------------------------------
The AuthZEN 1.0 response is a boolean plus a namespaced context, so it is a
projection of a Nornyx :class:`Decision`, not a copy of it. Equivalence is
therefore asserted field by field over what the mapping represents:

    effect        <-> the boolean, and context.nornyx.effect
    code          <-> context.nornyx.code
    reason        <-> context.nornyx.reason (omitted when empty)
    basis         <-> context.nornyx.basis (kind/ref/detail)
    prerequisite  <-> context.nornyx.prerequisite  -- COMPARED BUT NOT EXERCISED:
                      no case here produces APPROVAL_REQUIRED, so this
                      comparison is None == None on this corpus. Listed for
                      completeness of the mapping, not as something these cases
                      establish. The codec's encoding of the marker is covered
                      in test_agentic_authzen.py against a constructed Decision.

NOT represented, and therefore NOT claimed equivalent:
``Decision.event_intents``. The mapping carries no encoding for decision-event
intents, so a consumer reading only AuthZEN cannot reconstruct them. That is a
property of the supported profile, and
``test_the_authzen_projection_does_not_represent_event_intents`` pins it so the
gap stays visible rather than being read as equivalence.

APPROVAL_REQUIRED is deliberately absent from the equivalence cases. Issue #96
admits it "only if it can be produced honestly by the supported public request
path rather than fabricated", and it cannot: ``Authorizer._capability`` returns
ALLOW or DENY only, and ``CapabilityRequest`` is the sole request type the
AuthZEN mapping supports. The codec's APPROVAL_REQUIRED handling is already
covered against a constructed Decision in ``test_agentic_authzen.py``; inventing
a capability path that produced it here would be fabricating the case the issue
declines to fabricate.
"""

from __future__ import annotations

import shutil
import socket
from pathlib import Path
from typing import Any

import pytest

from nornyx.agentic import (
    Authorizer,
    CapabilityRequest,
    Decision,
    DecisionCode,
    DecisionEffect,
    EvaluationContext,
    build_agentic_network_lock,
    compose_document_governance,
    load_authorizer,
    load_nyx,
    registry_for_contract,
    write_agentic_network_lock,
)
from nornyx.agentic.authzen import (
    AuthZENMappingError,
    capability_request_from_authzen,
    capability_request_to_authzen,
    decision_to_authzen,
    evaluate_authzen_capability,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "agentic_network.nyx"
EVIDENCE = ROOT / "examples" / "governance_evidence"

#: Validation instant for the contract, matching the existing authorizer suites.
AS_OF = "2026-07-17T10:00:00Z"
#: Inside every identity/membership validity window in the example contract.
DECISION_AT = "2026-07-17T10:00:00Z"
#: After every window closes (2026-08-01), so identities are no longer effective.
DECISION_AT_LAPSED = "2026-09-01T10:00:00Z"
#: The exact subject_revision the example contract declares.
REVISION = "git:0123456789abcdef0123456789abcdef01234567"
OTHER_REVISION = "git:" + "b" * 40

RESEARCHER = "identity.researcher.local"
REVIEWER = "identity.reviewer.local"
HELD_CAPABILITY = "read_governed_context"
RESEARCHER_ONLY_CAPABILITY = "propose_research_finding"
UNDECLARED_CAPABILITY = "capability.not.in.contract"


@pytest.fixture(scope="module")
def authorizer(tmp_path_factory: pytest.TempPathFactory) -> Authorizer:
    """A real Authorizer, through the authoritative public load path.

    Not ``Authorizer(...)`` directly: that constructor performs no validation,
    composition, or lock verification, and its own docstring says so. Only
    ``load_authorizer`` runs those stages, so only it produces the artifact this
    module's claims are about.
    """
    tmp_path = tmp_path_factory.mktemp("authzen-equivalence")
    contract_path = tmp_path / "agentic_network.nyx"
    shutil.copyfile(EXAMPLE, contract_path)
    shutil.copytree(EVIDENCE, tmp_path / "governance_evidence")

    document = load_nyx(contract_path)
    composition = compose_document_governance(
        document, registry=registry_for_contract(contract_path)
    )
    assert composition is not None, "the example contract must resolve a governance profile"
    lock_path = tmp_path / "nornyx.agentic_network.lock"
    write_agentic_network_lock(build_agentic_network_lock(document, composition), lock_path)

    loaded = load_authorizer(contract_path, lock_path, validation_as_of=AS_OF)
    assert type(loaded) is Authorizer
    return loaded


def _context(decision_at: str = DECISION_AT, revision: str = REVISION) -> EvaluationContext:
    return EvaluationContext(decision_at=decision_at, observed_subject_revision=revision)


def _both_paths(
    authorizer: Authorizer,
    request: CapabilityRequest,
    context: EvaluationContext,
) -> tuple[Decision, dict[str, Any]]:
    """Evaluate one semantic request through both supported paths.

    The AuthZEN side goes through the real encode/bridge pair a caller uses --
    ``capability_request_to_authzen`` then ``evaluate_authzen_capability`` --
    rather than a locally reconstructed payload, so the assertion routes through
    the same production functions an integrator would call.
    """
    direct = authorizer.evaluate(request, context=context)
    payload = capability_request_to_authzen(request, context=context)
    mapped = evaluate_authzen_capability(authorizer, payload)
    return direct, mapped


def _assert_equivalent(direct: Decision, mapped: dict[str, Any]) -> None:
    """Every field the mapping represents must agree with the direct decision."""
    nornyx_context = mapped["context"]["nornyx"]

    assert mapped["decision"] is (direct.effect is DecisionEffect.ALLOW), (
        f"the AuthZEN boolean {mapped['decision']!r} does not follow the Nornyx "
        f"effect {direct.effect.value!r}"
    )
    assert nornyx_context["effect"] == direct.effect.value, (
        f"effect diverged: AuthZEN {nornyx_context['effect']!r} vs direct "
        f"{direct.effect.value!r}"
    )
    assert nornyx_context["code"] == direct.code.value, (
        f"decision code diverged: AuthZEN {nornyx_context['code']!r} vs direct "
        f"{direct.code.value!r} -- the boolean can agree while the reason differs, "
        "which is why the code is compared and not only the effect"
    )
    assert nornyx_context.get("reason", "") == direct.reason, (
        f"reason diverged: {nornyx_context.get('reason', '')!r} vs {direct.reason!r}"
    )

    expected_basis = [
        {"kind": item.kind, "ref": item.ref, **({"detail": item.detail} if item.detail else {})}
        for item in direct.basis
    ]
    assert nornyx_context.get("basis", []) == expected_basis, (
        f"decision basis diverged: {nornyx_context.get('basis', [])!r} vs "
        f"{expected_basis!r}"
    )

    expected_prerequisite = (
        "human_approval" if direct.effect is DecisionEffect.APPROVAL_REQUIRED else None
    )
    assert nornyx_context.get("prerequisite") == expected_prerequisite, (
        "prerequisite semantics diverged between the two paths"
    )

    # Completeness: nothing the mapping represents may differ in any other field.
    assert mapped == decision_to_authzen(direct), (
        "the two paths agreed on every field compared above but the encoded "
        "documents still differ, so some represented field is not being compared"
    )


# ---------------------------------------------------------------------------
# Equivalence across the honestly reachable capability outcomes
# ---------------------------------------------------------------------------

#: Each case is (label, identity, capability, decision_at, revision, effect, code).
#: Every one is produced by the real contract; none is constructed.
EQUIVALENCE_CASES = [
    (
        "allow_held_capability",
        RESEARCHER, HELD_CAPABILITY, DECISION_AT, REVISION,
        DecisionEffect.ALLOW, DecisionCode.ALLOWED,
    ),
    (
        "deny_capability_not_held",
        REVIEWER, RESEARCHER_ONLY_CAPABILITY, DECISION_AT, REVISION,
        DecisionEffect.DENY, DecisionCode.CAPABILITY_DENIED,
    ),
    (
        "deny_capability_undeclared",
        RESEARCHER, UNDECLARED_CAPABILITY, DECISION_AT, REVISION,
        DecisionEffect.DENY, DecisionCode.CAPABILITY_UNKNOWN,
    ),
    (
        "deny_identity_lapsed",
        RESEARCHER, HELD_CAPABILITY, DECISION_AT_LAPSED, REVISION,
        DecisionEffect.DENY, DecisionCode.PARTY_INEFFECTIVE,
    ),
    (
        "deny_revision_mismatch",
        RESEARCHER, HELD_CAPABILITY, DECISION_AT, OTHER_REVISION,
        DecisionEffect.DENY, DecisionCode.REVISION_MISMATCH,
    ),
]


@pytest.mark.parametrize(
    "label,identity,capability,decision_at,revision,expected_effect,expected_code",
    EQUIVALENCE_CASES,
    ids=[case[0] for case in EQUIVALENCE_CASES],
)
def test_direct_and_authzen_paths_agree_on_the_same_governed_request(
    authorizer: Authorizer,
    label: str,
    identity: str,
    capability: str,
    decision_at: str,
    revision: str,
    expected_effect: DecisionEffect,
    expected_code: DecisionCode,
) -> None:
    """The same request, decision time and revision, decided identically.

    The expected effect and code are asserted as well as compared. Comparing the
    two paths alone would pass if BOTH drifted to the same wrong answer -- an
    equivalence that holds while the semantics are wrong is not the property
    #96 asks for.
    """
    request = CapabilityRequest(identity_ref=identity, capability_ref=capability)
    context = _context(decision_at, revision)
    direct, mapped = _both_paths(authorizer, request, context)

    assert direct.effect is expected_effect, (
        f"{label}: the contract no longer produces {expected_effect.value!r}; this "
        "case is not exercising the outcome it names"
    )
    assert direct.code is expected_code, f"{label}: expected {expected_code.value!r}"

    _assert_equivalent(direct, mapped)


def test_the_two_paths_are_bound_to_the_same_decision_time_and_revision(
    authorizer: Authorizer,
) -> None:
    """Binding must PROPAGATE into the decision, not merely appear in the payload.

    Both values being present in the encoded request proves only that they were
    written down. The property is that the AuthZEN path's decision changes when
    they change -- so each is perturbed on the AuthZEN side alone and required
    to move the decision, while the direct path holds its answer.
    """
    request = CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY)
    context = _context()

    direct, mapped = _both_paths(authorizer, request, context)
    assert mapped["decision"] is True and direct.effect is DecisionEffect.ALLOW

    payload = capability_request_to_authzen(request, context=context)
    assert payload["context"]["nornyx"]["decision_at"] == DECISION_AT
    assert payload["context"]["nornyx"]["observed_subject_revision"] == REVISION

    # Revision is decision-sensitive on the AuthZEN path.
    perturbed = capability_request_to_authzen(request, context=_context(revision=OTHER_REVISION))
    result = evaluate_authzen_capability(authorizer, perturbed)
    assert result["decision"] is False, (
        "changing observed_subject_revision in the AuthZEN context did not change "
        "the decision, so the binding is carried but not consumed"
    )
    assert result["context"]["nornyx"]["code"] == DecisionCode.REVISION_MISMATCH.value

    # Decision time is decision-sensitive on the AuthZEN path.
    lapsed = capability_request_to_authzen(request, context=_context(decision_at=DECISION_AT_LAPSED))
    result = evaluate_authzen_capability(authorizer, lapsed)
    assert result["decision"] is False, (
        "moving decision_at outside every validity window did not change the "
        "decision, so decision_at is carried but not consumed"
    )
    assert result["context"]["nornyx"]["code"] == DecisionCode.PARTY_INEFFECTIVE.value


def test_the_encoded_request_round_trips_to_the_identical_spi_values(
    authorizer: Authorizer,
) -> None:
    """The AuthZEN path must evaluate the SAME request, not an equivalent-looking one.

    WHAT THIS DOES NOT ESTABLISH, stated because the first version of this
    docstring claimed the opposite: a round trip is blind to a defect the
    encoder and decoder share. Swap ``subject.id`` and ``resource.id`` in both
    and ``decode(encode(x)) == x`` still holds, while the emitted document is
    wire-nonsense no other AuthZEN implementation could read.

    What refuses that is the field-by-field pinning of the encoded document in
    ``tests/test_agentic_authzen.py``, which asserts the wire shape against
    literals rather than against a round trip. This test establishes the
    narrower property its name states: the values the bridge evaluates are the
    values that were encoded.
    """
    request = CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY)
    context = _context()

    decoded_request, decoded_context = capability_request_from_authzen(
        capability_request_to_authzen(request, context=context)
    )
    assert decoded_request == request, "the decoded request is not the request that was encoded"
    assert decoded_context == context, "the decoded context is not the context that was encoded"


#: Exactly what the AuthZEN projection is permitted to represent.
#:
#: A CLOSED SET, checked as a set. The first version of the control below
#: scanned `repr(mapped)` for each intent's `event_type` string, which decided a
#: SPELLING rather than the property: an encoder that added every intent's full
#: field payload under a new key passed it, and so did one that added the event
#: types themselves under a different case. Deciding which keys may exist
#: refuses any added field, whatever it is called.
_REPRESENTED_TOP_LEVEL = frozenset({"decision", "context"})
_REPRESENTED_NORNYX_FIELDS = frozenset(
    {"profile", "effect", "code", "reason", "basis", "prerequisite"}
)


@pytest.mark.parametrize(
    "label,identity,capability,decision_at,revision",
    [case[:5] for case in EQUIVALENCE_CASES],
    ids=[case[0] for case in EQUIVALENCE_CASES],
)
def test_the_projection_represents_exactly_the_documented_fields_and_no_others(
    authorizer: Authorizer,
    label: str,
    identity: str,
    capability: str,
    decision_at: str,
    revision: str,
) -> None:
    """Nothing beyond the documented projection may appear in the encoded decision.

    This is the mechanism behind the documented limitation that
    ``Decision.event_intents`` is not represented, and behind the claim that the
    compared field list is complete. Both are properties of WHICH KEYS EXIST, so
    the key set is what is asserted.
    """
    _direct, mapped = _both_paths(
        authorizer,
        CapabilityRequest(identity_ref=identity, capability_ref=capability),
        _context(decision_at, revision),
    )

    assert set(mapped) <= _REPRESENTED_TOP_LEVEL, (
        f"{label}: the encoded decision grew top-level keys "
        f"{sorted(set(mapped) - _REPRESENTED_TOP_LEVEL)}"
    )
    assert set(mapped["context"]) == {"nornyx"}, (
        f"{label}: the response context is no longer solely the Nornyx namespace"
    )
    extra = set(mapped["context"]["nornyx"]) - _REPRESENTED_NORNYX_FIELDS
    assert not extra, (
        f"{label}: the projection now represents {sorted(extra)}, which the "
        "documented field list and the equivalence comparison do not cover. If "
        "this is intended, widen both -- and re-check the documented limitation "
        "that decision-event intents are not represented."
    )


def test_the_authzen_projection_does_not_represent_event_intents(
    authorizer: Authorizer,
) -> None:
    """The disclosed limit of the equivalence claim, pinned so it stays visible.

    An ALLOW carries decision-event intents that the AuthZEN encoding has no
    field for. This is not a defect in the mapping -- AuthZEN has no such
    concept -- but it is the exact reason this module claims equivalence over
    "the supported capability profile" and not over "the Nornyx decision".

    HOW THIS IS ACTUALLY ENFORCED, since a name check alone would be the weak
    control this suite already had once: the structural work is done by
    ``test_the_projection_represents_exactly_the_documented_fields_and_no_others``,
    which refuses ANY key outside the documented set, so intents cannot arrive
    under a new field however it is spelled. The represented fields themselves
    are each compared to the direct decision by exact equality in
    ``_assert_equivalent``, so intents cannot be smuggled into one of those
    either. This test states the property those two mechanisms enforce.

    A value-level scan of the encoded document was tried here and removed: it
    reported ``policy_decision='allow'`` as a leak because ``effect: 'allow'``
    is legitimately represented. Substring identity is not field identity --
    the same confusion of spelling for property that this suite exists to
    refuse.
    """
    request = CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY)
    direct, mapped = _both_paths(authorizer, request, _context())

    assert direct.event_intents, "the ALLOW path stopped producing event intents"
    encoded = repr(mapped)
    for intent in direct.event_intents:
        assert intent.event_type not in encoded, (
            f"{intent.event_type!r} appears in the AuthZEN document, so the "
            "documented limitation is now wrong and the claim should widen"
        )


def test_no_capability_request_produces_approval_required(authorizer: Authorizer) -> None:
    """The reachability argument behind excluding APPROVAL_REQUIRED, made mechanical.

    This module's docstring and the public documentation both state that no
    honest ``CapabilityRequest`` can produce ``APPROVAL_REQUIRED``. That was
    true by inspection of ``Authorizer._capability`` and established by nothing:
    if capability evaluation were ever routed through an approval gate, both
    statements would become false in silence, and the equivalence cases would
    have a hole they do not disclose.

    Swept over the contract's own declared identities and capabilities, plus
    undeclared and empty refs, at decision times inside and outside every
    declared validity window.
    """
    document = authorizer.state.document
    identities = [str(item["id"]) for item in document["agent_identities"]]

    # EVERY DECLARED CAPABILITY, not only the referenced ones. Building the
    # corpus from `agent_identities[*].capability_refs` alone would omit a
    # capability that is declared but held by nobody -- which is exactly the
    # shape that carries `required_approval_refs`, and so exactly where an
    # approval-gated capability path would first appear.
    capabilities = sorted(
        {str(item["name"]) for item in document.get("capabilities", ())}
        | {
            str(ref)
            for item in document["agent_identities"]
            for ref in item.get("capability_refs", ())
        }
    )
    assert identities and capabilities, "the contract declares no identities or capabilities"
    assert set(capabilities) >= {
        str(item["name"]) for item in document.get("capabilities", ())
    }, "the sweep no longer covers every declared capability"

    seen: set[str] = set()
    for identity in [*identities, "identity.not.declared", ""]:
        for capability in [*capabilities, UNDECLARED_CAPABILITY, ""]:
            for decision_at in (DECISION_AT, DECISION_AT_LAPSED, "2025-01-01T00:00:00Z"):
                decision = authorizer.evaluate(
                    CapabilityRequest(identity_ref=identity, capability_ref=capability),
                    context=_context(decision_at),
                )
                assert decision.effect is not DecisionEffect.APPROVAL_REQUIRED, (
                    "a CapabilityRequest produced APPROVAL_REQUIRED for "
                    f"({identity!r}, {capability!r}, {decision_at!r}) -- the "
                    "documented reachability argument is now false, and the "
                    "equivalence cases must be widened to cover the effect"
                )
                seen.add(decision.effect.value)

    assert seen == {DecisionEffect.ALLOW.value, DecisionEffect.DENY.value}, (
        f"the sweep produced effects outside allow/deny: {sorted(seen)}"
    )


def test_the_two_paths_agree_on_a_malformed_request_only_by_both_refusing(
    authorizer: Authorizer,
) -> None:
    """The disclosed edge of the equivalence claim: refusal SHAPES differ.

    Equivalence is claimed over governed capability requests with well-formed
    refs. Outside that domain the two paths still both fail closed, but they do
    not do so identically: the direct path returns a Nornyx DENY decision, while
    the AuthZEN path refuses at the mapping boundary and returns no decision at
    all. Pinned so the claim's domain stays visible rather than being read as
    equivalence over every possible CapabilityRequest.
    """
    for identity, capability in (("", HELD_CAPABILITY), (RESEARCHER, "")):
        request = CapabilityRequest(identity_ref=identity, capability_ref=capability)
        context = _context()

        direct = authorizer.evaluate(request, context=context)
        assert direct.effect is DecisionEffect.DENY, (
            "the direct path stopped failing closed on a malformed ref"
        )

        with pytest.raises(AuthZENMappingError):
            evaluate_authzen_capability(
                authorizer, capability_request_to_authzen(request, context=context)
            )


# ---------------------------------------------------------------------------
# Fail-closed behaviour, still enforced on the real authorizer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "mutate,expected",
    [
        (
            lambda p: p["context"]["nornyx"].pop("observed_subject_revision"),
            "context.nornyx.observed_subject_revision",
        ),
        (lambda p: p["context"]["nornyx"].pop("decision_at"), "context.nornyx.decision_at"),
        (lambda p: p["context"].pop("nornyx"), "context.nornyx must be an object"),
        (
            lambda p: p["context"]["nornyx"].update({"profile": "other.profile.v1"}),
            "unsupported Nornyx AuthZEN profile",
        ),
        (lambda p: p["subject"].update({"type": "other.subject"}), "unsupported subject.type"),
    ],
    ids=["no_revision", "no_decision_at", "no_nornyx_context", "wrong_profile", "wrong_subject_type"],
)
def test_the_bridge_fails_closed_before_reaching_the_authorizer(
    authorizer: Authorizer,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Any,
    expected: str,
) -> None:
    """Incompatible or absent semantic context is refused BEFORE the authorizer runs.

    Asserted against the real authorizer rather than the codec alone: a decoder
    that failed closed in isolation but was bypassed by the bridge would pass a
    codec-only test.

    "Before reaching the authorizer" is measured, not inferred from the name. A
    bridge that decoded, evaluated, and only then refused would raise the same
    exception with the same message, so ``evaluate`` is counted and required to
    be zero. Each expectation is also the distinguishing part of its own
    refusal message -- ``"context.nornyx"`` alone appears in three of the five
    and so could not tell them apart.
    """
    payload = capability_request_to_authzen(
        CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY),
        context=_context(),
    )
    mutate(payload)

    reached: list[Any] = []
    real_evaluate = Authorizer.evaluate

    def counting_evaluate(self: Authorizer, request: Any, *, context: Any) -> Decision:
        reached.append(request)
        return real_evaluate(self, request, context=context)

    monkeypatch.setattr(Authorizer, "evaluate", counting_evaluate)

    with pytest.raises(AuthZENMappingError) as raised:
        evaluate_authzen_capability(authorizer, payload)
    assert expected in str(raised.value), (
        f"refused, but not for {expected!r}: {raised.value!r}"
    )
    assert reached == [], (
        "the bridge called Authorizer.evaluate before refusing, so the refusal "
        "is not happening at the mapping boundary this test names"
    )


# ---------------------------------------------------------------------------
# Local execution boundary: evaluation needs no network after state load
# ---------------------------------------------------------------------------

#: Every socket-module entry point this suite claims to block, with a probe that
#: reaches it. `getaddrinfo` is the load-bearing one: `create_connection`
#: resolves the module-global `socket` and so is already refused once `socket`
#: is patched, but name resolution is a separate C entry point that a
#: `socket`-only patch leaves wide open.
_BLOCKED_ENTRY_POINTS = (
    ("socket", lambda: socket.socket()),
    ("getaddrinfo", lambda: socket.getaddrinfo("localhost", 80)),
    ("create_connection", lambda: socket.create_connection(("127.0.0.1", 9), timeout=0.1)),
)


def _assert_every_blocked_entry_point_refuses() -> None:
    """Prove the block is live for EVERY name claimed, not for one of them.

    Without this, the block is a setup step nobody checks: an offline test can
    assert that decisions are unchanged while no block is in force at all, and
    a patch list can grow entries that never refuse anything. Both were true of
    this module before this control existed -- measured, not supposed: with
    `_block_network` reduced to a no-op the five-case sweep passed, and with
    only `socket.socket` patched all fifteen tests passed.
    """
    for name, probe in _BLOCKED_ENTRY_POINTS:
        try:
            probe()
        except AssertionError as exc:
            if "network access attempted" in str(exc):
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - any real attempt means unblocked
            raise AssertionError(
                f"socket.{name} is not blocked by this test: it reached a real "
                f"network attempt and raised {type(exc).__name__}"
            ) from exc
        raise AssertionError(
            f"socket.{name} is not blocked at all -- it returned normally, so an "
            "offline claim resting on this block is unmeasured"
        )


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every socket-module entry point a caller could reach the network by.

    Blocks the constructor, name resolution, and the convenience connector, and
    then PROVES each one refuses before returning. A helper that installs
    patches without demonstrating they took effect is exactly the control that
    cannot fail.

    BOUNDED CLAIM: this blocks network use through the ``socket`` module, which
    is the path CPython's networking stack and every stdlib client take. It does
    not constrain a C extension that opens a descriptor without importing
    ``socket``, nor a module holding a pre-bound ``from socket import ...``
    reference taken before the patch.
    """

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("network access attempted after authoritative state load")

    for name, _probe in _BLOCKED_ENTRY_POINTS:
        monkeypatch.setattr(socket, name, refuse)
    _assert_every_blocked_entry_point_refuses()


def test_a_real_authorizer_evaluates_both_paths_with_the_network_blocked(
    authorizer: Authorizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary local evaluation completes deterministically without the network.

    The authorizer is loaded BEFORE the block, which is the deployment pattern
    #96 describes: authoritative state is validated and loaded, and thereafter
    decisions are local. The block is proved live rather than assumed -- an
    inert patch would let this pass over a network call that never happened to
    occur.
    """
    request = CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY)
    context = _context()
    expected_direct, expected_mapped = _both_paths(authorizer, request, context)

    _block_network(monkeypatch)

    with pytest.raises(AssertionError, match="network access attempted"):
        socket.socket()

    direct = authorizer.evaluate(request, context=context)
    mapped = evaluate_authzen_capability(
        authorizer, capability_request_to_authzen(request, context=context)
    )

    assert direct == expected_direct, "the direct decision changed once the network was blocked"
    assert mapped == expected_mapped, "the AuthZEN decision changed once the network was blocked"
    _assert_equivalent(direct, mapped)


def test_evaluation_after_load_opens_no_file(
    authorizer: Authorizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of "local": no file is read either.

    The documentation states that an ordinary decision after ``load_authorizer``
    reads no file and opens no connection, under a heading that says "measured,
    not asserted". Only the connection half was measured. This measures the
    other half rather than leaving a true sentence standing on nothing.

    ``open`` is counted rather than refused: refusing it would break the test
    runner around the assertion instead of the code under test.
    """
    import builtins
    import io

    request = CapabilityRequest(identity_ref=RESEARCHER, capability_ref=HELD_CAPABILITY)
    context = _context()
    payload = capability_request_to_authzen(request, context=context)

    opened: list[Any] = []
    real_open = builtins.open

    def spy(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    try:
        authorizer.evaluate(request, context=context)
        evaluate_authzen_capability(authorizer, payload)
    finally:
        monkeypatch.undo()

    assert opened == [], (
        "an authorization decision opened "
        f"{opened!r} after the authoritative state was already loaded"
    )


def test_every_equivalence_case_still_decides_identically_offline(
    authorizer: Authorizer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Determinism offline is asserted across the whole case set, not one ALLOW.

    A single offline ALLOW would leave open whether the denial paths reach for
    anything external -- revocation lookup being the obvious candidate.
    """
    online: dict[str, tuple[Decision, dict[str, Any]]] = {}
    for label, identity, capability, decision_at, revision, _effect, _code in EQUIVALENCE_CASES:
        online[label] = _both_paths(
            authorizer,
            CapabilityRequest(identity_ref=identity, capability_ref=capability),
            _context(decision_at, revision),
        )

    _block_network(monkeypatch)

    for label, identity, capability, decision_at, revision, _effect, _code in EQUIVALENCE_CASES:
        direct, mapped = _both_paths(
            authorizer,
            CapabilityRequest(identity_ref=identity, capability_ref=capability),
            _context(decision_at, revision),
        )
        assert (direct, mapped) == online[label], (
            f"{label} decided differently with the network blocked"
        )
        _assert_equivalent(direct, mapped)
