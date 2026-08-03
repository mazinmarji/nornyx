---
chapter: 19
part: IV
title: "The Authorization Interface"
---

# The Authorization Interface

> **Opening scenario.** Northstar Services' Engineering Platform team runs the same governed support network through three code paths. A CrewAI tool wrapper enforces decisions inside the crew process. A LangGraph node wrapper enforces the same decisions inside a graph. And an older in-house layer, written before either wrapper existed, still guards a batch job. All three read the same contract file. All three parse it, compose governance from the same profile and modules, verify the same lock, and reach their own conclusions. On a Tuesday, an operations engineer shortens one delegation's expiry window and commits the change. Two of the three paths reload within seconds. The third holds a composed result it built at process start and will not rebuild until the next deployment. For the next eleven minutes the same agent, asking for the same capability, is allowed by one enforcement point and denied by another. There is no bug in any of the three implementations. The defect is architectural: three components each believed they were entitled to *interpret* governance, and nothing in the system said which interpretation was authoritative. This chapter is about the interface that removes that entitlement.

> **Learning objectives.**
> - Explain the split-brain hazard that arises when more than one component re-reads and re-composes governance state, and why it is an interface problem rather than a caching problem.
> - Describe what an assured construction path is, what stages it must run, and why a plain constructor deliberately carries no assurance.
> - Explain why an authorization interface exposes state as frozen, detached views, and what a consumer may and may not conclude from mutating one.
> - Enumerate the three decision outcomes an agentic authorization engine returns, and state precisely which condition produces approval-required.
> - Trace an approval assertion through an ordered evaluation sequence and explain why the ordering itself is part of the interface.
> - Evaluate a compatibility facade against the single-interpretation principle, and state what "unpackaged" changes about the claims a consumer may make.

> **Prerequisites.** Chapter 5 (identity, capability, authority), Chapter 9 (approval as a bound record), Chapter 10 (policy decision point and policy enforcement point separation), Chapter 17 (the Nornyx contract's blocks), Chapter 18 (profiles, modules, and the agentic-network lock). This chapter assumes the lock exists and verifies; it asks what a *program* does with a verified contract.

## 19.1 One question, several askers

Chapter 10 separated the component that decides from the component that acts: a <span class="ix" data-ix="policy decision point (PDP)">policy decision point</span> answers "may this happen?" and a <span class="ix" data-ix="policy enforcement point (PEP)">policy enforcement point</span> makes the answer stick. That separation is usually drawn with one decision point and several enforcement points, and the drawing hides an assumption worth making explicit: the several enforcement points are consulting *the same decision procedure applied to the same state*. Break that assumption and the architecture silently becomes something else — several decision points that happen to read the same file.

The opening scenario is that failure in its mildest form. Nothing was corrupted, no policy was weakened, and every component was correct in isolation. What went wrong is that three components each performed the full interpretive pipeline — parse, compose profile and modules into effective governance, verify the lock, index identities and delegations — and therefore each held its own answer to a question the organization believed had one answer. Call this the <span class="ix" data-ix="split-brain hazard">split-brain hazard</span>: whenever *n* components independently derive governance state from a shared source, the system has *n* interpretations, and their agreement is a coincidence maintained by discipline rather than a property maintained by construction.

The hazard has three distinct failure modes, and separating them matters because they call for different remedies.

**Temporal divergence** is the scenario's mode: two interpretations of the same source taken at different instants. It looks like a caching bug and is often "fixed" by shortening a cache lifetime, which reduces the window without closing it.

**Procedural divergence** is subtler. Two components implement the interpretation slightly differently — one applies module composition in dependency order and one in file order; one treats an absent expiry as "never expires" and one as "expired." Both read identical bytes and reach different effective policies. No cache lifetime helps, and the divergence can persist undetected for years because the two components rarely evaluate the same request.

**Assurance divergence** is the mode this chapter cares about most. One component ran the full validation and lock-verification pipeline before deciding; another accepted an already-parsed structure someone handed it. Both return decisions that look identical — same type, same fields, same code — but only one is entitled to the claim "this decision was made against a validated, lock-verified contract." A decision object that cannot tell you which case it came from launders claims.

> **Key idea.** The remedy for all three modes is the same and it is not a cache: exactly one component performs interpretation, and every other component receives the *result* through an interface that offers no way to re-derive it. Consumers become readers of an authoritative interpretation rather than interpreters in their own right.

This is Parnas's information-hiding criterion applied to governance [@parnas-criteria]: the interpretive pipeline is the design decision most likely to change and most damaging to duplicate, so it belongs behind one module boundary. It is also the classical authorization architecture — the AAA framework and the XACML model both place a single context handler between requesters and policy, precisely so that requesters cannot assemble their own view of the policy context [@rfc2904; @xacml].

## 19.2 What the interface must promise, and how it may change

An <span class="ix" data-ix="authorization interface">authorization interface</span> for a governed agentic system carries four obligations. First, **single interpretation**: one construction path produces the authoritative state, and consumers cannot build an equivalent one by other means. Second, **assured construction**: that path runs every validation stage and fails closed, so possessing the object is itself evidence that the stages ran. Third, **immutable state**: what the object holds cannot be altered by any consumer, deliberately or accidentally, because a decision made against mutated state would carry an assurance claim the mutation invalidated. Fourth, **stable typed outcomes**: decisions are values with a closed vocabulary, so that a consumer can branch on them without string matching and a downstream evidence layer can bind them without re-deriving anything.

The fourth obligation implies a fifth that authors of governance libraries often discover late: the interface itself is a versioned artifact with a compatibility policy, because adapters and enterprise integrations are compiled against it. Widening it is cheap; narrowing it breaks deployments that had every reason to trust the surface.

Nornyx's agentic <span class="ix" data-ix="service provider interface (SPI)">service provider interface</span> (SPI) — the Python surface exported by the `nornyx.agentic` package — versions independently of the distribution that ships it, and the three published versions in Table 19.1 illustrate the discipline. **[implemented]**

| SPI | Nornyx release | What it added |
|---|---|---|
| 1.0 | 1.8.0 | The frozen surface itself: an immutable, lock-verified `Authorizer`, typed requests, `Decision` objects, the load and decision code taxonomies, and `EvidenceRecorder`. Claimed for cooperative Tier 2 only. |
| 1.1 | 1.10.0 | Occurrence semantics: `RuntimeOccurrence`, `EvidenceRecorder.for_occurrences`, `max_recorded_attempt`, `resume`, and runtime-events schema 1.1. |
| 1.2 | 1.11.0 | The additive `Authorizer.state` capability returning an `AuthorizerState`. Authorization, approval, evidence, occurrence, replay, and language semantics unchanged. |

**Table 19.1 — Three versions of one interface.** From the repository's changelog entries for 1.8.0, 1.10.0, and 1.11.0; the current value of `SPI_VERSION` in `nornyx/agentic/authz.py` is `"1.2"`. The teaching point is the shape of the progression: every increment is additive, and the one that added the most *surface* (1.2) explicitly added no *semantics*. An interface that governs enforcement earns trust by being boring.

Version 1.2 exists because a consumer needed exactly what this chapter argues for. A legacy compatibility layer had been retaining its own copies of the contract, the composition, and the lock alongside an authorizer built from them — a second source of truth, and therefore a split brain waiting to happen. The remedy was not better documentation; it was publishing the authorizer's own retained state so the second copy became unnecessary. Section 19.7 returns to that layer as a study in its own right.

## 19.3 The assured construction path

The construction path is where "single interpretation" becomes mechanical. In Nornyx there is exactly one function that produces an authorizer with assurance attached: **[implemented]**

```python
load_authorizer(contract_path, lock_path, *, validation_as_of: str) -> Authorizer
```

Reading it left to right: it takes a contract path and a lock path — files, not parsed structures — and a mandatory keyword-only `validation_as_of` timestamp. That the two inputs are *paths* is a design decision, not an ergonomic accident. A function that accepted an already-parsed document could not promise that the document was ever validated; by owning the read, the loader owns the whole pipeline.

Inside, the function runs four stages in order, and each stage's failure is mapped deterministically into a four-member <span class="ix" data-ix="load taxonomy">load taxonomy</span> carried on an `AuthorizerLoadError`:

1. **Load and check.** The contract is parsed, structurally checked, and composed against its governance registry. Any failure here — parser, registry, checker, composition — becomes `CONTRACT_INVALID`.
2. **Resolve governance.** If the contract resolves no governance profile, the load stops with `PROFILE_MISSING`. Governance evaluation then runs as of `validation_as_of`, and any resulting error diagnostic also produces `CONTRACT_INVALID`, with the offending codes listed in the message.
3. **Load the lock.** A lock that cannot be read or parsed produces `LOCK_INVALID`.
4. **Verify the lock.** The lock is verified field by field against the freshly composed document. Any mismatch produces `LOCK_STALE`.

Only if all four stages pass is an `Authorizer` constructed and returned. The taxonomy is small on purpose: a caller wiring a fail-closed startup path needs to distinguish "your contract is wrong" from "your lock is stale" without parsing prose, and four buckets route an operator to the right fix.

The mandatory `validation_as_of` separates two kinds of time that governance systems routinely conflate. It governs *document validation* — whether the approvals and evidence records the contract depends on are themselves valid at that instant — and nothing else. Every temporal question asked later, about identity validity windows, membership status, delegation expiry, revocation effect, and approval staleness, is answered against a separate `decision_at` supplied per evaluation. The engine reads no wall clock at all. Determinism, as Chapter 7 argued in the abstract, requires that every temporal input be explicit; here it is enforced by having no implicit one available.

> **Nornyx in practice.** The mirror-image decision is that the plain constructor still exists and deliberately promises nothing. `Authorizer(document, composition, lock_payload)` accepts three in-memory structures and faithfully retains them; it "does not itself read, validate, compose, or verify files" (`docs/agentic-network/12_AUTHORIZATION_SPI.md`), and validation, composition, and lock verification "are guaranteed **only when the Authorizer was obtained through `load_authorizer`**" (`nornyx/agentic/authz.py`). This is not a loophole left open by neglect: a compatibility layer, a test harness, or an evidence tool sometimes legitimately holds already-validated structures and needs an authorizer over them. What the design refuses to do is *pretend*. **[implemented]**

That refusal is the honest half of an assurance claim. Forbidding direct construction would push the same need into private attribute access, where the capability exists without a documented boundary; making direct construction *look* equivalent would let a consumer claim lock verification it never performed. Naming both paths and grading them differently is the third option, and the one that supports an accurate <span class="ix" data-ix="claim register">claim register</span>.

## 19.4 State as a frozen, detached view

SPI 1.2's `AuthorizerState` answers a question that arises the moment a single authoritative interpretation exists: how does a consumer *read* it without being tempted to rebuild it?

The state object exposes five members: three views — the validated `document`, the effective `composition`, and the verified `lock_payload` — and the two digests the authorizer computed at construction, `contract_digest` and `network_lock_digest`. Two properties make the views safe to hand out.

They are <span class="ix" data-ix="detached view">detached</span>: each access returns a new copy in ordinary Python containers, so a consumer receives a plain `dict`/`list` graph it may traverse, serialize, or mutate at will. And the graph the authorizer *retains* is recursively frozen — mappings read-only, sequences immutable — so the copy is made from a source no one can edit. The consequence is the whole point: mutating a view cannot reach the authorizer, cannot reach a later view, and cannot change a decision or a digest. Listing 19.1 demonstrates it.

```python
from nornyx.agentic import CapabilityRequest, EvaluationContext, load_authorizer

REVISION = "git:feedfacefeedfacefeedfacefeedfacefeedface"
a = load_authorizer("support_network.nyx", "nornyx.agentic_network.lock",
                    validation_as_of="2026-07-17T00:00:00Z")
ctx = EvaluationContext(decision_at="2026-07-17T10:00:00Z",
                        observed_subject_revision=REVISION)

doc = a.state.document                       # a detached plain-dict copy
for identity in doc["agent_identities"]:     # forge a capability grant in the copy
    if identity["id"] == "identity.escalation_agent":
        identity["capability_refs"].append("produce_customer_safe_response")

d = a.evaluate(CapabilityRequest("identity.escalation_agent",
                                 "produce_customer_safe_response"), context=ctx)
print("state is stable    :", a.state is a.state)
print("decision unchanged :", d.effect.value, d.code.value)
```

**Listing 19.1 — Mutating a state view cannot change a decision.** Run against the bundled example `examples/agentic_network_support/support_network.nyx` with a lock built by `nornyx agentic-network lock`. The observed output is `state is stable    : True` and `decision unchanged : deny CAPABILITY_DENIED`, and a freshly requested `a.state.document` does not contain the forged capability.

Three details there are load-bearing. `a.state is a.state` is `True` because the state is the single construction snapshot, not a fresh computation per access. The decision is unchanged because the engine's indexes were derived from that frozen snapshot, not from the view. And the *next* view is clean, which tells us each copy is made from the frozen source rather than from a shared mutable intermediate.

The interface is also explicit about what state access does *not* do. It "performs no file read, governance composition, lock verification, network access, or framework import," and "changing or deleting the source files after `load_authorizer` returns cannot change the state" (`docs/agentic-network/12_AUTHORIZATION_SPI.md`). **[implemented]** For a consumer this collapses a family of hard questions — is the state fresh? did reading it touch the disk? could a deployment have swapped the file underneath us? — into one easy one: when was the authorizer loaded?

> **Misconception.** *"Returning immutable objects would be simpler than returning detached copies."* It would, and it would also be unusable. The composition result is a public governance type that downstream validators serialize, and serialization here is built on deep-copying into ordinary containers; a frozen wrapper would raise from its own serializer. The implementation therefore uses read-only containers that deep-copy back into the exact container type they wrapped (`nornyx/agentic/authz.py`). Immutability that breaks the consumer's existing pipeline is not a safety feature; it is a migration.

## 19.5 The decision surface

With one authoritative state, evaluation becomes narrow. A caller supplies a *request* and a *context*, and receives a *decision*.

<span class="ix" data-ix="request normalization">Request normalization</span> is the first line of defence, and it is a modelling decision more than a validation one. The engine accepts six frozen request types — capability, delegation, handoff, approval, zone crossing, and data share — each carrying only declared identifiers: an identity reference, a capability name, a delegation id, a zone pair, a category tuple. No request type carries a shell command, a file path, a uniform resource locator, or a tool argument, because the engine "authorizes *declared Nornyx concepts only*. It never parses raw shell commands, file paths, URLs, or tool arguments" (`nornyx/agentic/authz.py`). **[implemented]** An adapter's job, developed in Chapter 22, is to map framework reality onto these declared concepts using its own static configuration; what it must never do is forward raw framework arguments into the decision. A governance engine that parses attacker-influenced strings has quietly become a parser with a security boundary attached, which is the architecture Chapter 6's confused-deputy discussion warns about.

Shape checking runs before any lookup: a malformed request, or a context that is not an `EvaluationContext`, is denied with `REQUEST_MALFORMED` rather than raising. <span class="ix" data-ix="fail-closed!in an enforcement hook">Fail-closed</span> here means "deny," not "crash," because a crash inside an enforcement hook is a fail-open path in a caller that catches exceptions.

The context carries two mandatory fields, and the second catches a whole class of deployment error. `observed_subject_revision` must exactly equal the contract's own `subject_revision`; if it does not, every request is denied with `REVISION_MISMATCH` and a `policy_violation` intent. The caller is asserting which revision of the world it believes it is running against, and the engine refuses to decide for a caller that believes something else.

<span class="ix" data-ix="decision outcome">Decisions</span> come in exactly three effects — `ALLOW`, `DENY`, and `APPROVAL_REQUIRED` — over a closed vocabulary of twenty-three decision codes. Chapter 7 argued for three decision domains in the abstract; this is the implemented instance, and the third domain earns its place through one specific condition. `APPROVAL_REQUIRED` is returned when a <span class="ix" data-ix="trust zone!external classification">zone-crossing</span> request targets a zone whose classification is external (`external`, `external_contract_only`, or `contract_only`), a declared gate governs the crossing, and the request carries no approval assertion. It is not a general "we could not decide" outcome. It is the engine reporting a *structural* fact about the destination: this boundary requires a human record, and you did not supply one.

Every decision also carries two structured payloads. The <span class="ix" data-ix="decision basis">decision basis</span> is a tuple of `(kind, ref)` pairs naming what the decision rested on — `membership`, `delegation`, `capability`, `approval`, `zone`, `gate`, `binding`, or `share` — which is how a consumer learns *why* without re-deriving the reasoning. The <span class="ix" data-ix="decision-event intent">event intents</span> are the decision-phase records the caller should emit, drawn from a frozen ten-member set (`capability_requested`, `capability_allowed`, `capability_denied`, the three delegation events, the three approval events, and `policy_violation`). Post-action facts such as `tool_invoked` or `runtime_failed` belong to a disjoint eight-member observation set and can only be recorded *after* acting. The engine cannot fabricate an observation, because it never observes anything. Chapter 20 takes up what an evidence recorder does with both sets.

Figure 19.1 shows the resulting sequence for one governed call.

<figure class="nx-fig" id="fig-19-1">
  <div class="fig-body">
    <div class="seq">
      <div class="seq-cols" data-cols="Framework|Adapter (PEP)|Authorizer (PDP)|Recorder|Tool"></div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">invoke governed surface</div>
      <div class="msg" data-from="2" data-to="2" data-kind="call">bind surface → (identity_ref, capability_ref)</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">evaluate(CapabilityRequest, context)</div>
      <div class="msg" data-from="3" data-to="2" data-kind="return">Decision(effect, code, basis, intents)</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record decision intents</div>
      <div class="msg" data-from="2" data-to="5" data-kind="call">run action — only on ALLOW</div>
      <div class="msg" data-from="5" data-to="2" data-kind="return">result (or exception)</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record observation: tool_invoked / runtime_failed</div>
      <div class="msg" data-from="2" data-to="3" data-kind="deny">on DENY / APPROVAL_REQUIRED: raise, never call the tool</div>
    </div>
  </div>
  <figcaption><b>Figure 19.1 — Evaluate, record, execute.</b> The order is the teaching point and it is a compatibility guarantee, not an implementation detail: the decision is recorded <i>before</i> the protected callable runs, the callable runs exactly once and only on allow, and the post-action observation is a separate record the adapter emits afterwards. Reversing the first two steps would produce evidence that exists only for actions that completed — precisely the records an incident review does not need.</figcaption>
</figure>

Listing 19.2 is the whole surface exercised against the bundled support network. It loads an authorizer, resolves a framework key to a declared identity, and evaluates one request the identity may make and one it may not.

```python
from nornyx.agentic import CapabilityRequest, EvaluationContext, load_authorizer

REVISION = "git:feedfacefeedfacefeedfacefeedfacefeedface"

authorizer = load_authorizer(
    "support_network.nyx",
    "nornyx.agentic_network.lock",
    validation_as_of="2026-07-17T00:00:00Z",
)
context = EvaluationContext(
    decision_at="2026-07-17T10:00:00Z",
    observed_subject_revision=REVISION,
)

print("network_id      :", authorizer.network_id)
print("contract_digest :", authorizer.contract_digest)
print("identity        :", authorizer.resolve_identity("crewai", "escalation_agent"))

for capability in ("escalate_high_value_refund", "produce_customer_safe_response"):
    decision = authorizer.evaluate(
        CapabilityRequest("identity.escalation_agent", capability), context=context
    )
    print()
    print("request  :", capability)
    print("effect   :", decision.effect.value, "/ code:", decision.code.value)
    print("reason   :", decision.reason or "(none)")
    print("basis    :", [(b.kind, b.ref) for b in decision.basis])
    print("intents  :", [i.event_type for i in decision.event_intents])
```

**Listing 19.2 — One allowed and one denied request.** Run against `examples/agentic_network_support/support_network.nyx` after `nornyx agentic-network generate` and `nornyx agentic-network lock`. Listing 19.3 is the observed output.

```text
network_id      : network.governed_support
contract_digest : sha256:3cdf632c08684efa2382a047b474b8f56ea4a83c5ed2f86c05918c29d0ac8eda
identity        : identity.escalation_agent

request  : escalate_high_value_refund
effect   : allow / code: ALLOWED
reason   : (none)
basis    : [('membership', 'escalate_high_value_refund')]
intents  : ['capability_requested', 'capability_allowed']

request  : produce_customer_safe_response
effect   : deny / code: CAPABILITY_DENIED
reason   : Identity 'identity.escalation_agent' neither holds nor validly receives
           'produce_customer_safe_response' at decision_at.
```

**Listing 19.3 — The observed output of Listing 19.2.** The denial's reason names the temporal qualifier explicitly — *at `decision_at`* — because the same request could be allowed at a different instant if a delegation were valid then. Note also that the allowed decision's basis says `membership`: the escalation agent holds this capability directly. Had it arrived through a delegation, the basis kind would be `delegation` and the delegation's identifier would be stamped into the `capability_allowed` intent, so the evidence record would name the authority path rather than merely the outcome.

`resolve_identity` sits deliberately outside the decision surface. <span class="ix" data-ix="identity resolution">Identity resolution</span> maps a framework's own key — a CrewAI agent role, a LangGraph node key — to a declared identity, and raises `IdentityResolutionError` with `IDENTITY_UNKNOWN` or `IDENTITY_AMBIGUOUS` rather than returning a decision, because failing to recognize a caller is a configuration error, not a policy judgment. Conflating the two would let a misconfiguration be logged as a denial — and denials are exactly the records an audit reads as evidence that policy worked.

## 19.6 The approval engine's ordering

<span class="ix" data-ix="approval!evaluation order">Approval</span> is the one request type where the *order* of checks is itself part of the interface, because the code a rejected approval carries tells the operator what to fix. The engine runs the checks in Table 19.2, and returns on the first failure.

| # | Check | Failure code |
|---|---|---|
| 0 | The approval reference is a declared requirement | `REQUEST_MALFORMED` |
| 1 | Assertion `subject_revision` equals the contract revision | `APPROVAL_REVISION_MISMATCH` |
| 2 | If a `revision_binding` is declared, the assertion matches it too | `APPROVAL_REVISION_MISMATCH` |
| 3 | The asserted action is inside the governed action scope | `APPROVAL_ACTION_MISMATCH` |
| 4 | The claimed actor type is exactly `human` and not a denied type | `APPROVAL_NON_HUMAN` |
| 5 | The role is in eligible ∪ required roles | `APPROVAL_ROLE_INVALID` |
| 6 | All required evidence references are present | `APPROVAL_EVIDENCE_MISSING` |
| 7 | Valid at `decision_at` under the earliest applicable expiry | `APPROVAL_STALE` |
| 8 | The record actually grants | `APPROVAL_NOT_GRANTED` |

**Table 19.2 — The approval evaluation order.** From `Authorizer._approval` in `nornyx/agentic/authz.py`. **[implemented]** The ordering is defensible rather than arbitrary: binding checks come before content checks so that an approval for the wrong revision is never examined for role eligibility, and the *last* check is whether the record grants — so a malformed or expired refusal is reported as malformed or expired rather than as a refusal.

Running the sequence against the bundled contract, varying one field at a time, produces the transcript in Listing 19.4.

```text
human owner     allow  ALLOWED
AI approver     deny   APPROVAL_NON_HUMAN         AI systems, tools, models, and
                                                  execution surfaces cannot approve.
unlisted role   deny   APPROVAL_ROLE_INVALID      Role 'delivery_manager' is outside
                                                  the composed approval authority.
wrong revision  deny   APPROVAL_REVISION_MISMATCH Approval subject_revision does not
                                                  match the contract subject_revision.
no evidence     deny   APPROVAL_EVIDENCE_MISSING  The approval does not reference all
                                                  required evidence.
expired         deny   APPROVAL_STALE             The approval is expired at decision_at
                                                  (earliest applicable expiry).
not granted     deny   APPROVAL_NOT_GRANTED       The supplied human approval record
                                                  does not grant approval.
```

**Listing 19.4 — One approval assertion, seven variations.** Observed output from evaluating `ApprovalRequest` against `support_network.nyx`, varying a single field of the assertion each time; the base assertion claims role `network_governance_owner`, actor type `human`, action `approve_agentic_network_contract`, and the contract's own subject revision.

Two rows repay attention. The `AI approver` row is Chapter 9's constitutional invariant implemented at the engine: an assertion whose `claimed_actor_type` is anything other than the exact string `human` is refused with the message "AI systems, tools, models, and execution surfaces cannot approve." The rule holds twice over — non-`human` fails, and membership in the requirement's `denied_actor_types` fails — so no composition of profiles and modules can produce a requirement under which an `ai_tool` approves. The `expired` row shows the temporal rule: the composed requirement here carries a relative expiry of seven days, and the engine takes the *earliest* applicable expiry across the assertion's own `expires_at`, the requirement's absolute expiry, and issuance plus the relative window. Approvals issued after `decision_at` also fail closed, closing the clock-skew and back-dating paths in one rule.

> **Assurance boundary.** Everything in this section is a check on a *claimed* record. The engine does not authenticate the approver, contact an identity provider, verify a signature, or establish that the named human ever saw the change. `claimed_approver_ref` and `claimed_actor_type` are named "claimed" for exactly that reason. What the interface guarantees is that a claim which fails any structural, role, evidence, revision, or temporal requirement cannot produce an allow — and that a claim which passes them all is recorded with the fields that let a later reviewer check the claim against the organization's own identity records. Authenticating approvers is the surrounding platform's obligation, and Chapter 26 takes up what a Tier 3 deployment would need to add.

## 19.7 A compatibility study: the deprecated kernel as a facade

The repository contains a small but unusually clean study in compatibility engineering, and most teams that adopt a governance interface will face the same problem it solves: an older internal layer with its own vocabulary that predates the interface and cannot simply be deleted.

The older layer here is a `GovernanceKernel` from an earlier reference-integration design, with its own method names (`check_capability`, `require_human_approval`, `record_zone_crossing`, `events_payload`) and its own diagnostic strings. It was rebuilt, at the repository's current head, as "a deprecated <span class="ix" data-ix="compatibility facade">compatibility facade</span> over the supported Nornyx agentic SPI" (`integrations/nornyx_reference_adapters/governance_kernel.py`). **[implemented but unpackaged]** The rebuild is instructive on four counts.

**It has one source of authority.** One `Authorizer` is constructed, and its public `Authorizer.state` "is the only source for every legacy compatibility projection this shim exposes. The shim never reads Authorizer private attributes, never retains caller-supplied contract/composition/lock structures as a second source of truth, and never re-reads, re-composes, re-authorizes, or re-verifies policy after the Authorizer has been constructed." That is Section 19.1's principle as an implementation constraint, and it is why SPI 1.2 exists: without a public state accessor the facade's only options were private attribute access or a second copy, and both are split brains.

**Its legacy surfaces are demoted, not preserved.** The old `document`, `composition`, `lock_payload`, and `network` attributes still exist for source compatibility, but they are documented as "**non-authoritative read-only projections**" derived from the authorizer's state on each access, unassignable, and unable to reach the authorizer when mutated. The old *names* survive; the old *authority* does not. That distinction is the whole art of a compatibility facade.

**Its diagnostics are mapped, not renamed.** The facade translates the engine's `DecisionCode` values into twenty-two stable legacy `AN_ADAPTER_*` strings — `AN_ADAPTER_CAPABILITY_DENIED`, `AN_ADAPTER_APPROVAL_NON_HUMAN`, `AN_ADAPTER_LOCK_STALE`, and so on — so existing pipelines that gate on those strings keep working. The repository's migration notes add that these are "compatibility codes only," not new interface guarantees: a mapping table, not a second public taxonomy.

**It is <span class="ix" data-ix="unpackaged code">unpackaged</span>, and that changes what a consumer may claim.** The facade "ships in neither the core wheel nor `nornyx-agentic-adapters`," because the core distribution's packaging configuration includes only the `nornyx*` package tree and `integrations/` sits outside it. The code is real, tested, and merged — the repository's compatibility corpus exercises it — and simultaneously not installable by `pip install nornyx`. A team that vendors it is running repository code, not a released artifact: no version to pin, no changelog entry tying behavior to a release, no deprecation window a published package's policy would guarantee. It also carries a floor the published adapter distribution does not: because it consumes `Authorizer.state` it requires Nornyx 1.11.0 or newer, while the published adapter package keeps its wider `nornyx>=1.10,<2` range.

> **Design checkpoint.** Before you claim a governance behavior in a review, an audit response, or a procurement questionnaire, ask which artifact it lives in. Is it in a published, versioned package with a compatibility policy; in a repository at a named revision; or in a branch? Each answer supports a different sentence. "Nornyx 1.11.0 refuses non-human approvals" is a claim about a released artifact. "The compatibility facade routes every projection through `Authorizer.state`" is a claim about repository code at a revision, and honest phrasing says so.

> **Misconception.** *"A facade over a governance engine is just a thin wrapper, so it inherits the engine's assurance."* Only if it consumes the engine the way this one does. A facade that re-reads the contract to answer a convenience query has reintroduced the split brain the engine existed to remove, and its answers now have two possible provenances that its return type cannot distinguish. The property that matters is not thinness; it is that every projection is derived from the single authoritative state and nothing else.

## Summary

Several components needing one interpretation of governance is the ordinary case, and letting each derive its own produces split brains in three flavours: temporal, procedural, and — most damaging for claims — divergence in whether validation ever ran. The remedy is an interface with one assured construction path. In Nornyx that path is `load_authorizer`, which takes file paths and a mandatory validation instant, runs parse, check, compose, load-lock, and verify-lock in order, and maps every failure into a four-member taxonomy. The plain constructor remains available and is documented as carrying no assurance, which is more honest than either forbidding or disguising it. State is published as detached copies over a recursively frozen snapshot, so a consumer may read and even mutate a view without any possibility of changing a decision or a digest. Evaluation accepts six typed requests over declared concepts only, rejects malformed shapes and revision mismatches before any lookup, and returns one of three effects with a basis and a set of decision-phase intents. Approval runs an ordered sequence in which binding precedes content and the refusal of non-human approvers is unconditional. And the deprecated kernel rebuilt as a read-only facade over that state shows both the technique and its limit: old names may survive, old authority may not.

- One interpreter, many readers — the interface must make re-derivation unavailable, not merely discouraged.
- Assurance travels with a construction path, not with a type.
- Detached views over a frozen snapshot let consumers read freely without weakening any claim.
- Three effects: allow, deny, and approval-required for an unaccompanied external crossing.
- Ordered approval checks make the failure code diagnostic, not merely negative.
- "Merged" is not "released"; unpackaged code supports weaker claims.

## Review questions

1. Distinguish temporal, procedural, and assurance divergence in a split-brain governance deployment. For each, state whether a shorter cache lifetime helps, and why.
2. `load_authorizer` accepts file paths rather than an already-parsed document. Give the assurance argument for that choice, and name one legitimate use case the plain constructor still serves.
3. A colleague proposes making `AuthorizerState.document` return the frozen internal mapping directly, arguing it avoids a copy. State two consequences — one for consumers, one for serialization — and decide.
4. Under what precise conditions does an evaluation return `APPROVAL_REQUIRED` rather than `DENY`? Why is it important that this is a narrow structural condition and not a general "undecidable" outcome?
5. In Table 19.2, why is "does the record grant?" the last check rather than the first? Construct a case where reversing the order would mislead an operator.
6. A vendor states that its integration "uses the Nornyx authorization interface and therefore inherits its lock verification." What two questions would you ask before accepting the claim?

## Exercises

1. Using the repository at the book's snapshot, build a lock for `examples/agentic_network_support/support_network.nyx`, then reproduce Listing 19.2. Now edit one character of the contract without rebuilding the lock and re-run. Record the exception type, the load code, and the message, and explain which of the four load stages produced it.
2. Write a small consumer that takes an `Authorizer` and answers "which capabilities does identity X hold?" using only `Authorizer.state`. Then write a second version that re-reads the contract file itself. Enumerate the concrete divergences the second version can exhibit that the first cannot, and state which of Section 19.1's three modes each belongs to.
3. Design a compatibility facade over a modern engine for a legacy interface of your choosing. Specify: which single object is the source of authority; which legacy names survive and which legacy semantics are demoted to projections; the code mapping; and the sentence you would put in its documentation about what a consumer may claim.

## Further reading

- [@parnas-criteria] — the information-hiding criterion that justifies putting the whole interpretive pipeline behind one module boundary.
- [@rfc2904] — the AAA authorization framework's separation of requesters from the entity that holds policy context, the classical form of this chapter's argument.
- [@xacml] — the context handler in the XACML model, and why requesters are not permitted to assemble their own view of the decision context.
- [@miller-ocap] — the case for immutability and unforgeable references as the substrate of a trustworthy authority model.
- [@nornyx-repo] — the interface documentation (`docs/agentic-network/12_AUTHORIZATION_SPI.md`) and the engine source referenced throughout this chapter.
