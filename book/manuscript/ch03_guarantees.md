---
chapter: 3
part: I
title: "What Governance Can and Cannot Guarantee"
---

# What Governance Can and Cannot Guarantee

> **Opening scenario.** Northstar Services' Risk & Audit division has asked a supplier to demonstrate that the agentic platform it is proposing can be governed. Three weeks later a package arrives: a policy document, a machine-readable contract describing the agents and their permitted actions, and a file of runtime events recording a week of operation. Every event is well-formed. Every hash in the file matches. Every referenced identity exists in the contract, every capability was held at the moment it was used, and one action carries an approval record naming a human approver, bound to the exact revision of the change approved. The package validates without a single error. The reviewer, an audit lead with fifteen years in financial-systems assurance, reads it twice and writes one sentence in her notes: *what, exactly, does this establish?* That is the question this chapter answers — precisely, and with the negative half of the answer given equal weight.

> **Learning objectives.**
> - Distinguish five layers of assertion — declaration, decision, observation, evidence binding, and assurance claim — and state what each establishes and what it leaves open.
> - Reason about integrity, authenticity, and completeness as three independent dimensions, and identify which mechanisms move which dimension.
> - Analyze a signed event record and state exactly which dimension the signature improves and which two it does not touch.
> - Apply the eight questions, this book's recurring analytical frame, end to end to a single governance claim.
> - Explain fail-open and fail-closed behavior and why the failure mode of an enforcing component is part of its guarantee rather than an operational detail.

> **Prerequisites.** Chapter 1 (the four properties of agentic execution) and Chapter 2 (drift, and the four axes on which alignment, prompts, and guardrails do not close the gap). This chapter assumes the conclusion of Chapter 2 — that determinism must live outside the planner — and asks what such a boundary can honestly claim.

## 3.1 Five layers of assertion

The supplier's package looks like one artifact making one statement. It is not. It is five different kinds of statement stacked on top of one another, and the audit lead's unease comes from the fact that reading them as a single claim silently promotes the weakest to the strength of the strongest. Separating the layers is the most useful single habit this book teaches.

A <span class="ix" data-ix="declaration">declaration</span> states what should be true. It is the contract: these agents exist, these are their capabilities, these zones may not exchange these categories of data, this action requires approval by a human in this role. A declaration is a design-time artifact. It can be checked for internal consistency — no dangling references, no capability escalation, no identity that both exists and is revoked — and that checking is genuinely valuable, because an inconsistent declaration cannot be correctly enforced by anything. What a declaration cannot establish is that any runtime behaved accordingly. It is a specification, and Chapter 1 already established that specifications do not bind probabilistic executors.

A <span class="ix" data-ix="decision">decision</span> states what an evaluator concluded for one request. Given this actor, this capability, this target, this context, under this version of this policy, the verdict was *allow*, *deny*, or *approval required*. A decision is a much stronger object than a declaration, because it is a specific conclusion about a specific request, reproducible from its inputs if evaluation is deterministic. What it cannot establish is whether the inputs were true. If the actor identity presented to the evaluator was forged, or the context supplied to it misdescribed the action, the decision is a correct conclusion from false premises — and it will look exactly like a correct conclusion from true premises.

An <span class="ix" data-ix="observation">observation</span> states what a <span class="ix" data-ix="producer">producer</span> reports occurred. The tool ran; the zone was crossed; data of these categories was shared; the node failed on its second attempt. Observations are the only layer that speaks about the world, which makes them indispensable and makes their trust properties the crux of the whole discipline. An observation establishes what the producer *said*. It does not establish that the producer was honest, and — a distinct and frequently overlooked point — it does not establish that the producer said everything. A run in which the agent took forty actions and the producer recorded thirty-nine yields an event stream that is entirely truthful and entirely misleading.

An <span class="ix" data-ix="evidence binding">evidence binding</span> states that a set of bytes corresponds to declared digests, revisions, and versions. The events in the package name a contract digest; that digest matches the contract supplied; the referenced artifact files hash to the values recorded; the policy version in force is the one under review. Binding is what makes the other layers refer to the same universe rather than to four different ones, and it is the layer most amenable to mechanical verification. What binding cannot establish is that the bytes describe reality. A fabricated event, correctly bound, is a correctly bound fabrication.

An <span class="ix" data-ix="assurance claim">assurance claim</span> states what an evaluator believes may reasonably be concluded, within named assumptions. It is the only layer written by a person for other people, and the only one that can be wrong in the specific way organizations get hurt by: by being broader than its support. "The report is bound to the approved revision and validates against the contract in force" is an assurance claim of the right shape. "The system was compliant last quarter" is a claim of the wrong shape, because it collapses declaration, decision, observation, binding, producer honesty, and coverage into a single word.

Figure 3.1 stacks the layers in the order that support flows through them.

<figure class="nx-fig" id="fig-3-1">
  <div class="fig-body">
    <div class="layers">
      <div class="layer authority" data-note="Written by a person; can exceed its support">Assurance claim — what may reasonably be concluded, under named assumptions</div>
      <div class="layer" data-note="Mechanically verifiable; says nothing about truth">Evidence binding — these bytes correspond to these digests, revisions, and versions</div>
      <div class="layer untrusted" data-note="Producer-supplied; honesty and completeness are assumptions">Observation — what a producer reports occurred</div>
      <div class="layer" data-note="Correct conclusions from possibly false premises">Decision — what the evaluator concluded for one described request</div>
      <div class="layer" data-note="Design-time; checkable for consistency, not for adherence">Declaration — what rules, identities, and relationships are defined</div>
    </div>
  </div>
  <figcaption><b>Figure 3.1 — The five assertion layers.</b> Support flows upward, and each layer inherits every assumption below it. The observation layer is drawn as untrusted because it is the only layer whose content originates outside the governance machinery. The teaching purpose is that an assurance claim is never stronger than the weakest layer beneath it, and that the weakest layer is almost always observation.</figcaption>
</figure>

Table 3.1 states each layer's question and, in the column that matters most, what it does not establish.

| Layer | Question it answers | What it establishes | What it does *not* establish |
|---|---|---|---|
| Declaration | What rules, identities, and relationships are defined? | Internal consistency of the intended model | That any runtime followed it |
| Decision | What did the evaluator conclude for this described request? | A reproducible verdict from stated inputs under a stated policy version | That the request's identity, context, or description was authentic |
| Observation | What does the producer report happened? | The content of the producer's report | That the producer was honest, or that the report is complete |
| Evidence binding | Do these bytes match the declared digests, revisions, and versions? | That the artifacts under review are the ones referred to | That the bytes describe reality |
| Assurance claim | What conclusion is justified within stated assumptions? | A scoped, defensible statement | Anything outside its named scope, producers, and dependencies |

**Table 3.1 — The five assertion layers.** The teaching purpose is the right-hand column. Most governance overclaiming happens by reading a row's third column and quoting it without its fourth.

> **Key idea.** Each layer adds value and each has a distinct proof surface. Confusing them is the single most common cause of governance overclaiming, and it is a *technical* error, not a rhetorical one: it produces architectures in which nobody is assigned to close the gap that the confusion hid.

## 3.2 Integrity, authenticity, and completeness

Beneath the layer model lies a smaller and sharper distinction, and getting it wrong is what makes the layer confusions possible. Three properties are routinely bundled together under words like "verified" or "trusted." They are independent, in the strict sense that any one can hold while the other two fail.

<span class="ix" data-ix="integrity">Integrity</span> asks whether content changed after it was recorded. A cryptographic <span class="ix" data-ix="digest">digest</span> answers it: recompute the hash, compare, and detect any mutation. Integrity is the cheapest of the three to obtain and the one most often mistaken for the other two.

<span class="ix" data-ix="authenticity">Authenticity</span> asks who produced the content. A digest does not answer it, because anyone can compute a digest over anything. A digital signature over a key bound to an identity does answer it, to the extent that the key management, the identity binding, and the signing environment are themselves sound.

<span class="ix" data-ix="completeness">Completeness</span> asks whether everything relevant is present. Neither a digest nor a signature answers it. Completeness is a property of the *relationship between the record and the world*, and no property of the record alone can establish it. It can only be approached architecturally: by placing the recording function somewhere the actor cannot avoid, so that omission requires defeating a component rather than declining to call one.

Figure 3.2 sets the three side by side with the mechanisms that move each.

<figure class="nx-fig" id="fig-3-2">
  <div class="fig-body">
    <div class="tiers">
      <div class="tier" data-name="Integrity">
        <ul>
          <li>Question: did content change?</li>
          <li>Moved by: digests, content addressing, locks</li>
          <li>Cheap; verifiable offline</li>
          <li>Silent about: who wrote it, what is missing</li>
        </ul>
      </div>
      <div class="tier" data-name="Authenticity">
        <ul>
          <li>Question: who produced it?</li>
          <li>Moved by: signatures, attested identity, key management</li>
          <li>Costs an identity infrastructure</li>
          <li>Silent about: whether the content is true, what is missing</li>
        </ul>
      </div>
      <div class="tier" data-name="Completeness">
        <ul>
          <li>Question: is everything relevant present?</li>
          <li>Moved by: mandatory interception, unavoidable recording paths</li>
          <li>Costs an architectural position, not a cryptographic primitive</li>
          <li>Silent about: whether recorded content is accurate</li>
        </ul>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 3.2 — Three independent dimensions of evidentiary strength.</b> Each column names the question, the mechanism class that improves it, and what it stays silent about. The teaching purpose is that the three are bought with different currencies: integrity with computation, authenticity with identity infrastructure, completeness with architectural position.</figcaption>
</figure>

The practical discipline that follows is simple to state and hard to maintain: **name both the achieved property and the missing one**. "The event stream is hash-bound to the reviewed contract revision" is precise, and its precision is what makes it defensible under challenge. "The event stream proves the system complied" is not merely optimistic; it is a category error, because compliance is a statement about the world and a hash is a statement about bytes.

## 3.3 Worked example: the signed event record

Take a concrete record and work the analysis through, because the abstract distinction survives contact with practice only if we can apply it to an artifact. Listing 3.1 shows one event from the supplier's package, in the shape such records commonly take.

```json
{
  "event_id": "e-0f42",
  "event_type": "tool_invoked",
  "mission_id": "m-2026-06-12-004",
  "sequence": 17,
  "actor_ref": "identity.refund_agent",
  "capability_ref": "issue_refund",
  "timestamp": "2026-06-12T09:41:07Z",
  "contract_digest": "sha256:6b1d…",
  "policy_decision": "allow",
  "approval_ref": "approval.refund_over_limit",
  "approver": {"role": "TreasuryOfficer", "actor_type": "human"},
  "output_digest": "sha256:9c02…",
  "signature_ref": "sig-77a1",
  "producer": {"type": "framework_adapter", "id": "adapter-1"}
}
```

**Listing 3.1 — One runtime event record.** Illustrative — the field names follow the shape of records used later in this book, but this instance is constructed for analysis. The record asserts that a refund tool ran, under a held capability, with a policy decision of *allow*, backed by a human approval, and it carries a reference to a signature over its content.

Suppose everything checks. The digests recompute correctly. The signature verifies against a key that genuinely belongs to the adapter that produced the record. The approval reference resolves to an approval record naming a human in a role the policy recognizes, bound to the exact revision of the refund request. Ask the three questions.

*Integrity* is improved, and improved twice. The digests establish that the record has not been mutated since it was written, and the signature makes mutation detectable even by a party who could recompute the digests. Anyone holding the record can verify it offline, indefinitely.

*Authenticity* is improved, and this is the dimension the signature exists to move. Before the signature, the record's claim to come from `adapter-1` was a string in a field, assertable by anyone who could write a file. After it, that claim is cryptographically bound to control of a key. Note the precise form of what has been gained: not that the event happened, but that *this producer said it*. Authenticity converts an anonymous assertion into an attributable one, which matters enormously for accountability and not at all for truth.

*Completeness* is not improved at all. The signature says nothing about the events that are not in the file. If the producer recorded thirty-nine of forty actions, all thirty-nine are now signed, and the fortieth is exactly as absent as before.

And a fourth property, which the three dimensions deliberately keep separate from all of them: *truthfulness* is not improved either. The producer is the one asserting that the tool ran. A producer that fabricates an event and then signs it has produced a record that is intact, attributable, and false. The signature raises the cost of fabrication in one specific way — the fabrication is now attributable to a keyholder, which is a real deterrent in an organization with consequences — but it does not make fabrication detectable. Nothing in the record can, because the record is the producer's own testimony about itself.

Table 3.2 records the analysis in the form worth reusing.

| Property | Before signature | After signature | Why |
|---|---|---|---|
| Integrity | Established by digest, forgeable by whoever can rewrite both | Established and non-repudiable | Signature binds content to a key |
| Authenticity | Asserted in a field; anyone can write it | Established, to the strength of the key management | This is the dimension the signature exists to move |
| Completeness | Unknown | Unknown | Omission leaves no trace in a record that is not there |
| Truthfulness of content | Depends on producer honesty | Depends on producer honesty | The producer is the source; self-testimony cannot self-validate |

**Table 3.2 — What a signature does and does not buy.** The teaching purpose is the bottom two rows: a signature is the correct mechanism for one dimension and irrelevant to two others, and the two it leaves open are the two that matter most when an agent is the subject.

The architectural consequence is worth stating now, because it motivates a great deal of Parts II and III. Completeness cannot be bought with cryptography; it must be bought with position. If the only component that can record an action is the same component that chooses to call the recorder, completeness is a matter of that component's cooperation. If the recording sits on a path the actor cannot avoid — a gateway the traffic must traverse, a sandbox boundary, an identity system that must mint a credential before the action can occur — then omission requires defeating a component rather than skipping a call. That difference is the entire content of the distinction between <span class="ix" data-ix="cooperative enforcement">cooperative</span> and <span class="ix" data-ix="independent enforcement">independent</span> enforcement, and Chapters 10 and 13 build on it.

> **Assurance boundary.** As implemented at the snapshot this book describes, Nornyx's runtime-evidence validation is explicit about exactly this boundary, and embeds the limitation in every report it produces: validated evidence proves conformance of supplied records only; hash validity proves content binding, not event truth; and the toolchain does not observe, operate, or monitor the runtime. Its agentic-network documentation states the residual risks in the same terms used above — evidence is supplied rather than observed, so omission and fabrication lie outside the proof surface; a cooperative producer can falsely claim a new occurrence, since validation establishes structural consistency rather than independent execution truth; and structural signature *references* in the event schema are not cryptographic verification, which the project does not claim to perform. These are not disclaimers appended to a marketing document. They are the <span class="ix" data-ix="proof boundary">proof boundary</span> of the product, and a governance layer that did not state them would be less trustworthy, not more.

## 3.4 The eight questions

We now have enough to state the analytical frame this book uses for the rest of its length. Whenever a governance claim is made — by a vendor, by a colleague, by an architecture document, or by you — <span class="ix" data-ix="eight questions">eight questions</span> establish whether it is defensible. They are ordered so that each exposes a different failure mode, and answering them in order tends to surface problems in the order they will bite.

1. **What exactly is guaranteed?** State the guarantee as a proposition with a subject, an action, a condition, and a scope. "Secrets are protected" is not a guarantee; "no capability declared in this contract may transmit values tagged `credentials` to a target outside the declared zone" is.
2. **Which component enforces it?** Name the component, singular. If the answer is a list, the guarantee is the conjunction of several guarantees and each needs its own pass through these questions.
3. **What evidence supports it?** Name the artifact, the producer, and the mechanism by which the artifact is bound to the thing it describes.
4. **What assumptions are required?** Enumerate what must be true for the guarantee to hold: producer honesty, key management, correct configuration, framework version, that the agent runs only where you think it runs.
5. **How can it be <span class="ix" data-ix="bypass">bypassed</span>?** Describe the shortest path an actor could take to perform the guarded action without triggering the enforcing component. If you cannot describe one, you have not looked hard enough; every cooperative control has at least one.
6. **What happens when the enforcing component fails?** Distinguish failing *closed* from failing *open*, and check whether the failure behavior was designed or inherited.
7. **What level of independence does the claim rest on?** Does enforcement depend on the governed component's cooperation, or on a component the governed system cannot avoid? Chapter 4 previews the vocabulary — assurance tiers — and Chapter 13 formalizes it; here the question is simply whether the claim survives an uncooperative actor.
8. **What remains unproven?** State the <span class="ix" data-ix="residual risk">residual</span> explicitly. A claim with no stated residual is not a stronger claim; it is a less honest one.

Two properties of this list are deliberate. First, questions 5, 6, and 8 have no positive answers — they exist to extract information the claimant is not motivated to volunteer, which is why they are on the list rather than in a footnote. Second, the questions apply identically to your own systems and to systems you are evaluating. An engineer who can answer all eight about her own design has produced something an auditor can use; one who cannot has produced something that will be discovered later, by someone else, under worse conditions.

## 3.5 The eight questions applied

Frames are learned by use, so we apply all eight to a single claim, end to end. Take the claim the supplier's package most plausibly supports:

> *Every refund above the approval threshold executed by the refund agent during the recorded week was authorized by a policy decision under contract revision `9f3c1a7`, and each such execution carries an approval record naming a human in the `TreasuryOfficer` role bound to that revision.*

**1. What exactly is guaranteed?** Something narrower than it first appears. The claim is about executions *that appear in the event stream*, not about executions. It asserts a property of records, and the leap to a property of the world is exactly the leap the remaining questions probe.

**2. Which component enforces it?** The authorization component consulted by the framework adapter before each tool call, together with the recording component that emits the events. Note that this is already two components with different failure modes, and that the claim's phrasing hides the join.

**3. What evidence supports it?** The event stream, produced by `adapter-1`, bound to contract revision `9f3c1a7` by a digest carried in every event, validated against the contract and against ordering and referential rules. The approval records are separate artifacts referenced by identifier and bound to the same revision.

**4. What assumptions are required?** That the adapter is the only path by which the refund tool can be invoked; that the adapter was not modified; that the producer recorded every invocation it observed; that the approval records were created by the humans they name; that the framework version in production is the version the adapter was tested against; and that the clock used for expiry evaluation is the one whose timestamps appear in the stream.

**5. How can it be bypassed?** Trivially, in at least three ways. Application code can call the underlying refund function directly rather than through the governed tool wrapper. An operator can invoke the payment API outside the agent process entirely. And an execution path the adapter does not cover — an asynchronous variant, a subgraph, a batch job — reaches the same effect without passing the enforcement point. None of these bypasses is exotic; the first is a one-line change.

**6. What happens when the enforcing component fails?** This must be answered separately for each of the two components in question 2. If the authorization component raises an error, does the adapter deny the action or let it through? If the recorder fails after the action has run, is the action rolled back, or is there now an executed action with no record? The second case is the one that quietly destroys the claim, because the resulting evidence file is complete-looking and incomplete.

**7. What level of independence does the claim rest on?** None. Every element depends on the governed component choosing to route through the adapter. The claim survives a buggy actor and does not survive a motivated one.

**8. What remains unproven?** That the recorded executions are all the executions. That the producer's reports are true. That the approving humans were informed, or were the humans the identifiers name. That the contract in force during the week was the contract supplied for review — unless something independent binds deployment to revision.

Having done this, we can restate the claim in a form that survives scrutiny: *within the surfaces routed through the governed adapter, and assuming a non-adversarial producer, every recorded refund above the threshold was allowed by a deterministic decision under revision `9f3c1a7` and carries a human approval bound to that revision; the stream establishes nothing about actions taken outside those surfaces.* The sentence is longer, and it is the one a professional can sign.

> **Misconception.** *"Applying the eight questions to our own system will make our claims look weak."* It makes them look *bounded*, which is different, and it is the difference between an assurance statement and a marketing statement. In practice the exercise usually strengthens the engineering: question 5 generates a work item, question 6 finds a fail-open path nobody had considered, and question 8 turns an unexamined assumption into a documented dependency that a consumer of the system can decide about. The alternative is not a stronger claim; it is the same weak claim, undiscovered until it fails.

## 3.6 Fail-open and fail-closed

Question 6 deserves separate treatment, because it is the question engineers most often treat as an operational detail and auditors most often treat as the heart of the matter.

A control <span class="ix" data-ix="fail-open">fails open</span> when, on its own failure, the guarded action proceeds. A control <span class="ix" data-ix="fail-closed">fails closed</span> when, on its own failure, the guarded action does not proceed. The distinction is not about how often the control fails; it is about which way the system leans when it does. And it is a *design* property, not an emergent one: a control whose failure behavior was never decided has one anyway, and it is almost always fail-open, because "the check threw an exception and the code continued" is the default shape of hastily written integration code.

Figure 3.3 contrasts the two paths.

<figure class="nx-fig" id="fig-3-3">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Proposed action</div><div class="arr">→</div><div class="node">Decision point (error)</div><div class="arr dashed">⇢</div><div class="node">Action executes</div><div class="arr">→</div><div class="node">No record</div></div>
      <div class="flow"><div class="node">Proposed action</div><div class="arr">→</div><div class="node">Decision point (error)</div><div class="arr deny">⛔</div><div class="node">Action refused</div><div class="arr">→</div><div class="node">Failure recorded</div></div>
    </div>
  </div>
  <figcaption><b>Figure 3.3 — Fail-open and fail-closed under the same fault.</b> The two rows differ only in what happens on the error edge, and the difference determines what the guarantee is worth. The teaching purpose is that a fail-open control's guarantee is conditional on the control working, which makes its availability a security property rather than an operational one.</figcaption>
</figure>

Three consequences follow, and they are worth internalizing before Part II makes them architectural.

First, a fail-open control's guarantee is conditional on the control's availability. That converts an availability problem into a security problem: an attacker who can make the decision point unreachable has disabled the guarantee without ever attacking it. This is why "the policy service was down so we bypassed it" is not an incident about downtime.

Second, fail-closed has a real cost, and pretending otherwise produces systems that get switched off. A fail-closed governance layer means that when it breaks, work stops. Organizations pay that cost willingly for consequences they cannot afford — merges to protected branches, payments above a threshold — and refuse to pay it for consequences they can. The design question is therefore not "should we fail closed?" but "for which decisions, and what is the documented degraded mode for the rest?" Chapter 10 develops the answer; Chapter 33 treats degraded operation.

Third, failure behavior must be *tested*, and tested by injection, because it is the behavior least likely to occur naturally before it matters. A test suite that only exercises allow and deny paths has not tested the third path, which is the one that runs during the incident. Chapter 15 makes failure injection a standing obligation of governance testing.

> **Design checkpoint.** For the most consequential control in a system you work on, answer without checking the code, then check: what happens if the decision component is unreachable? If it returns an error? If it times out? If the recorder fails after the action has run but before the record is durable? If any answer is "I assume it denies," find out — assumed fail-closed is the most common false belief in this discipline.

## 3.7 What can be guaranteed, honestly

Pulling the chapter together: a governance layer built on declarations, deterministic decisions, bound evidence, and cooperative recording can make several genuinely valuable classes of statement.

It can guarantee properties of *artifacts*: that the policy evaluated was this exact version, that the contract reviewed is the contract in force in this repository, that these bytes have not changed since review. It can guarantee properties of *decisions*: that a given described request, evaluated under a given policy version, yields this verdict reproducibly, by anyone holding the inputs — the property Chapter 7 calls <span class="ix" data-ix="deterministic evaluation">deterministic evaluation</span>. It can guarantee properties of *structure*: that no declared identity holds contradictory authority, that no approval was granted by a non-human actor, that no event in a stream references a capability its actor did not hold at that timestamp. And it can guarantee properties of *process*: that the merge lane refuses to proceed when the artifacts drift, that a stale approval is invalidated by a new revision.

It cannot guarantee that the world matched the record. It cannot guarantee that everything was recorded. It cannot guarantee that a producer was honest, that an actor did not take a path the enforcement point does not cover, or that a human approver read what they approved. Each of those requires something outside the layer: mandatory interception, an independent observer, an identity infrastructure, an informed-approver process. Part III names each of these gaps and says what would close it; Chapter 13 organizes the whole set into tiers.

The reason to be this careful is not modesty. It is that the value of a governance layer is precisely its trustworthiness, and a layer that overstates by one degree loses the ability to be relied upon at any degree. The audit lead in the opening scenario will accept a narrow claim she can verify. What she cannot accept, and what will end the supplier's engagement, is a broad claim she catches.

## Summary

Governance artifacts mix five kinds of statement — declaration, decision, observation, evidence binding, and assurance claim — and each has a distinct proof surface, with observation the weakest because it originates outside the governance machinery. Beneath the layers lie three independent dimensions: integrity, answered by digests; authenticity, answered by signatures and identity infrastructure; and completeness, answered by neither, because no property of a record can establish what is absent from it. A signed event record therefore improves authenticity, strengthens integrity, and leaves completeness and truthfulness exactly where they were. The eight questions provide a repeatable frame for testing any governance claim, and their negative questions — bypass, failure behavior, residual — carry most of their value. Failure behavior in particular is a design decision that determines what a guarantee is worth: a fail-open control's guarantee is conditional on its own availability, which turns an operational property into a security one.

- The five assertion layers must be reasoned about separately; an assurance claim is never stronger than the weakest layer beneath it.
- Integrity, authenticity, and completeness are independent and are bought with different currencies: computation, identity infrastructure, and architectural position.
- A signature makes an assertion attributable, not true, and does nothing about omission.
- The eight questions are the book's recurring frame; questions 5, 6, and 8 exist to extract what claimants do not volunteer.
- Fail-closed costs availability and buys guarantees; fail-open is what a system does when nobody decided.

## Review questions

1. A colleague says "the evidence file validates, so the agent behaved correctly." Identify every assertion-layer confusion in that sentence and restate it as a defensible claim.
2. Give an example of an artifact with high integrity, high authenticity, and low completeness, and explain why no cryptographic mechanism improves the third property.
3. A vendor offers to sign every runtime event with a hardware-backed key. Using Table 3.2, state precisely what that buys and what it does not, and name the one organizational benefit of attribution that Section 3.3 identifies.
4. Apply questions 5 and 6 to a control you rely on today. If you cannot describe a bypass path, explain what would have to be true of the control's position for that answer to be credible.
5. Explain why a fail-open control converts an availability incident into a security incident, and describe a decision for which fail-open is nonetheless the right choice.
6. Question 8 asks what remains unproven. Why is a claim with no stated residual weaker, rather than stronger, than one that states several?

## Exercises

1. **Decompose a broad claim.** Take a claim of the form "our agent platform is compliant with our internal AI policy." Decompose it into at least six narrower claims. For each, name the assertion layer it lives at, the evidence producer, the governed surface, and one residual assumption. Mark any claim you cannot decompose this way as unsupportable and say why.
2. **Eight questions, adversarially.** Choose a governance or security product page written by someone else. Answer all eight questions from the published material alone, marking every question the material does not answer. Then write the three questions you would ask the vendor first, ordered by how much they would change your evaluation.
3. **Failure injection on paper.** For a control in a system you know, enumerate every distinct way its enforcing component can fail (unreachable, error, timeout, partial write, wrong version loaded, clock skew). For each, state the current behavior, the desired behavior, and the test that would distinguish them. Identify which failures your existing tests would not catch.

## Further reading

- [@schneider-enforceable] — establishes formally which classes of security policy are enforceable by a runtime monitor at all; the theoretical backstop for question 2 and for the limits of Section 3.7.
- [@clark-wilson] — the origin of the integrity-plus-separation-of-duty framing that underlies the approval material in this chapter and Chapter 9.
- [@merkle] — the foundation of content binding; read it to see exactly what a hash-based structure does and does not assert.
- [@in-toto] — a supply-chain framework built around the same layer distinctions, useful for seeing how another discipline separates attestation from truth.
- [@nist-ai-rmf] — provides the vocabulary organizations use to convert bounded technical claims into governance statements without overclaiming.
