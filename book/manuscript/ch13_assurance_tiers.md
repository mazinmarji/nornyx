---
chapter: 13
part: III
title: "Assurance Tiers"
---

# Assurance Tiers

> **Opening scenario.** Northstar's Risk & Audit chief is reading two documents. The first is a vendor proposal claiming that its platform "enforces your AI governance policy and provides full audit evidence." The second is Northstar's own platform team's internal write-up of the Atlas and Forge pilots, which claims that "policy is enforced and evidence is validated in CI." The two sentences are nearly identical. Behind them sit completely different mechanisms: one is a network gateway the agent cannot route around, the other is a library the agent's own process calls into and could, in principle, skip. Both teams believe they are being accurate. Neither sentence tells the reader which mechanism is in play, what happens if it is absent, or what remains unproven. The chief's problem is not that someone is lying. It is that the English language gives "enforce" one word for three very different guarantees, and procurement, audit, and engineering all need to tell them apart. This chapter supplies the vocabulary.

> **Learning objectives.**
> - State the three assurance tiers and the property that distinguishes each from the one below it.
> - Work each tier through the eight questions and produce the resulting claim boundary.
> - Select a tier for a given surface from the consequence of failure and the adversary in scope.
> - Recognize tier inflation in written claims and rewrite an inflated claim so that it is accurate.
> - Explain why a tier applies to a surface and an evidence package, never automatically to a whole system.

> **Prerequisites.** Chapter 3 (the eight questions; integrity, authenticity, and completeness), Chapter 10 (enforcement models; fail-closed design), Chapter 11 (supplied versus observed evidence), Chapter 12 (locks, ordering, and what digests bind). This chapter formalizes a model previewed in Chapter 4.

## 13.1 Why assurance needs tiers

An <span class="ix" data-ix="assurance">assurance</span> claim is a statement about what a system will not do, offered to someone who cannot verify it directly. "No production deployment happens without a named human approval" is an assurance claim. So is "the agent cannot publish externally." Claims of this form are the currency of audit, procurement, and risk acceptance, and they are useless unless the reader can determine how strong they are.

The difficulty is that strength varies enormously while the wording does not. Consider three systems, each of which will produce the sentence "the agent cannot publish externally." In the first, a reviewed contract declares no external-publication capability, and a static check confirms the declaration is coherent; nothing runs. In the second, a library wrapped around the agent's tool calls evaluates that contract at call time and raises an exception on the publication path; the agent's process calls the library. In the third, all outbound traffic traverses a gateway the agent has no route around, the gateway holds the policy, and the gateway writes its own evidence to a store the agent cannot reach. The three sentences are equally sincere and not remotely equivalent. An attacker who can add a line of code defeats the second and not the third. A misconfiguration defeats the first without leaving a trace anywhere.

<span class="ix" data-ix="assurance tier">Assurance tiers</span> exist to make that difference part of the claim rather than a footnote to it. The model has three levels, and the property that separates them is not sophistication or completeness but *who or what could defeat the control*.

**<span class="ix" data-ix="assurance tier!tier 1">Tier 1 — design-time governance</span>.** The claim rests on declarations that were validated, composed, locked, and approved before anything ran. Nothing at runtime is involved. Defeated by: running something other than what was declared.

**<span class="ix" data-ix="assurance tier!tier 2">Tier 2 — cooperative runtime enforcement</span>.** The claim rests on a component in the execution path that evaluates policy and blocks disallowed calls, where the executing system is the one that chose to call it. Defeated by: not calling it.

**<span class="ix" data-ix="assurance tier!tier 3">Tier 3 — independent enforcement with independent attestation</span>.** The claim rests on a component the governed system cannot bypass, producing evidence the governed system cannot forge or suppress. Defeated by: compromising the enforcement system itself, which is a much harder proposition than the tiers below.

<figure class="nx-fig" id="fig-13-1">
  <div class="fig-body">
    <div class="tiers">
      <div class="tier" data-name="Tier 1 — Design-time">
        <ul>
          <li>Validated, composed contract</li>
          <li>Deterministic generated artifacts</li>
          <li>Lock over source, packs, schemas, artifacts</li>
          <li>Revision-bound human approval</li>
          <li>Evidence: checker diagnostics, digests, lock verification</li>
          <li>Bypassed by: running something not declared</li>
        </ul>
      </div>
      <div class="tier" data-name="Tier 2 — Cooperative runtime">
        <ul>
          <li>Everything in Tier 1, plus:</li>
          <li>Decision point in the execution path</li>
          <li>Wrapped surfaces named in a coverage inventory</li>
          <li>Deny path demonstrated, not assumed</li>
          <li>Evidence: runtime records bound to the approved revision</li>
          <li>Bypassed by: calling the surface without the wrapper</li>
        </ul>
      </div>
      <div class="tier" data-name="Tier 3 — Independent">
        <ul>
          <li>Everything in Tier 1 for the same revision, plus:</li>
          <li>Enforcement the subject cannot route around</li>
          <li>Authenticated producer identity</li>
          <li>Verified attestation; protected evidence capture</li>
          <li>Evidence: independently owned and controlled</li>
          <li>Bypassed by: compromising the enforcement system</li>
        </ul>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 13.1 — The three assurance tiers.</b> The teaching purpose is the last bullet of each column. Tiers are ordered by what defeats them, and each tier's bypass is the previous tier's residual risk made concrete. Note that Tier 3 does not require Tier 2: an independently enforced surface can qualify without a cooperative wrapper, because the wrapper is one way to reach enforcement, not the definition of it.</figcaption>
</figure>

One structural rule prevents most of the misuse to come. A tier attaches to a *claim about specific surfaces*, supported by a *specific evidence package* — never automatically to an application, a deployment, a framework, or a product. A system routinely contains surfaces at different tiers, and evidence satisfying a higher tier for one surface upgrades nothing else. A system-wide tier may be asserted only when every surface inside an explicitly stated scope meets that tier's criteria. Sections 13.5 and 13.6 return to this rule as the thing tier inflation always violates.

## 13.2 Tier 1 — design-time governance

Tier 1 is where every claim starts, because a claim about runtime behavior that does not correspond to a reviewed declaration is not a governance claim at all — it is an observation.

The tier's material is the artifact set of Parts II and III: a contract that parses and validates against closed schemas; composed profiles and modules with per-element provenance; deterministically generated control artifacts; a lock binding source, packs, schemas, records, and artifacts as in Chapter 12; and approvals that are bound to an exact, immutable subject revision and that expire. The evidence is the checker's deterministic diagnostics, the digests, the lock verification result, and the approval records.

What Tier 1 guarantees is easy to state and easy to overstate. It guarantees that *the declarations are coherent, complete against the schema, unchanged since review, and approved*. It says nothing whatever about what runs. A contract can be valid, locked, and fully approved, and be violated on the first tool call, because at Tier 1 nothing is watching. This is not a defect to be apologized for; design-time governance is doing real work — it is the only tier at which a control can be reviewed by a human before any harm is possible, and it is the layer that gives every higher tier something specific to enforce.

The prohibition that follows is the one organizations break most often. A Tier 1 evidence package may not be described using the words *prevents*, *blocks at runtime*, or *enforces*, and a passing contract check may not be presented as evidence that agents behaved correctly.

> **Nornyx in practice.** This three-tier framing is not an interpretation imposed by this book; it matches the repository's own architectural decision record, ADR-0040, and the terminology in this chapter is deliberately aligned with it. That record is explicit about the vocabulary: "The word 'guarantee' is deliberately avoided: Tier 1 does not guarantee runtime behavior, and Tier 3 is not delivered by Nornyx alone. These are **assurance tiers with claim boundaries**, not product guarantees" (`docs/decisions/ADR-0040-governance-assurance-tiers.md`). At the snapshot, the record is marked *Proposed (design only)* — the vocabulary and the eligibility criteria are fixed, but emitting machine-readable tier labels in reports is named as a follow-on milestone rather than existing behavior. Tier 1 eligibility is stated as five conjunctive conditions: a valid contract, a deterministic check pass, a valid lock where a lock is required, all applicable approval requirements satisfied and verified, and an exact bound subject revision.

## 13.3 Tier 2 — cooperative runtime enforcement

Tier 2 adds a decision point that runs. A component sits in the execution path of specific, named surfaces; on each call it evaluates the contract, and on a denial it prevents the call from proceeding. This is genuine enforcement, and it changes what the system does: a Tier 2 denial stops work that a Tier 1 declaration merely disallowed on paper.

The qualifier that must accompany every Tier 2 claim is <span class="ix" data-ix="cooperative enforcement">cooperative</span>. The component is in the path because the executing system arranged for it to be there. A call written to invoke the underlying surface directly does not pass through the wrapper, is not evaluated, is not denied, and — this is the part that surprises people — produces *no record of having happened*. A total bypass may leave no trace at all in the governance layer's evidence, which means the absence of a denial record is not evidence that nothing was denied, and the absence of any record is not evidence that nothing occurred.

Two consequences shape how Tier 2 must be claimed. First, the claim's scope is exactly the set of surfaces actually wrapped, which means a <span class="ix" data-ix="coverage inventory">coverage inventory</span> — an enumerated list of wrapped, unsupported, and unwrapped surfaces — is not documentation but a component of the claim. Chapter 14 treats coverage as a first-class engineering artifact and shows why the *unsupported* list is security-relevant information rather than an embarrassment. Second, the deny path must be demonstrated rather than assumed. A wrapper that has only ever been exercised on allowed calls has not been shown to deny anything, and "we configured it to deny" is a Tier 1 statement wearing Tier 2 clothing. The minimum is at least one allow control and one deny control exercised on a declared wrapped surface.

Tier 2 also inherits an evidence limitation from Chapter 11 that it cannot repair: the producer is self-declared. The records are supplied by a component inside the governed system, so omission and fabrication remain outside what validation can detect, however rigorous the ordering and replay checks of Chapter 12 are.

> **Nornyx in practice.** As implemented at the snapshot, the cooperative layer consists of adapters that wrap named framework surfaces — a synchronous tool method in one framework, a synchronous graph node in another — and evaluate through a published authorization interface; a denial blocks the wrapped callable and the resulting runtime events are bound to the approved revision. The repository states the boundary in the same words this section uses: "Adapter enforcement is cooperative; bypassing the adapter bypasses the hook" (`docs/agentic-network/08_SECURITY_BOUNDARIES.md`), and ADR-0040 adds that a total bypass "may leave no Nornyx-generated trace" and that enforcement "covers only declared, wrapped surfaces and cannot prove that no undeclared surface exists." The eligibility criteria are Tier 1 plus a supported adapter version, a declared coverage inventory, deny-path validation, required runtime events present, and successful digest and revision binding — and every Tier 2 claim is required to carry the qualifier "cooperative, declared surfaces only."

## 13.4 Tier 3 — independent enforcement and attestation

Tier 3 changes the trust relationship rather than adding a feature. Enforcement moves to a component the governed system cannot route around, and evidence moves to a producer the governed system cannot influence. Gateways, sandboxes, identity-boundary controls, and service-mesh authorization points are the usual implementations [@istio; @envoy; @nist-zta]; what makes them Tier 3 is not their category but their position.

Independence has an evidence side that is easy to underweight. Enforcement independence alone gives a system that stops disallowed actions and still cannot prove it did. The evidence basis Tier 3 requires is correspondingly demanding: an <span class="ix" data-ix="authenticated producer">authenticated producer identity</span>, so that "this evidence came from the gateway" is verified rather than asserted; a cryptographically verified <span class="ix" data-ix="attestation">attestation</span> over the records; a <span class="ix" data-ix="protected capture path">protected capture path</span>, so that records reach storage without passing through the governed system; binding of the deployed policy to the approved revision, so that the enforcement point is demonstrably running the policy that was reviewed; independently controlled logging, outside the governed system's administrative reach; and demonstrated coverage of the claimed surfaces, because an unbypassed control that sits in front of only half the traffic is a Tier 3 control over half the traffic.

Two clarifications matter for architecture. First, Tier 3 does not require Tier 2 beneath it. An independently enforced surface qualifies on its own, and mandating a cooperative wrapper as well would force redundant enforcement for no assurance gain. Second — and this is the trap — the *affordances* for Tier 3 are not Tier 3. An evidence schema that permits a record to declare an external producer, and that offers a field for a signature reference, allows externally produced evidence to be represented and structurally checked. It does not authenticate the producer, verify the signature, or establish independence. Metadata that says "I am independent" is producer-supplied metadata.

> **Assurance boundary.** A design-time governance layer can define the contract that a Tier 3 system enforces, accept evidence declaring an external producer, and check that evidence binds to the approved revision. It cannot, by itself, authenticate that producer, verify an attestation, establish a protected capture path, prove evidence completeness, observe the runtime, or prove the producer is independent of the decision-maker. Tier 3 is therefore a declared boundary and a set of integration affordances until an external enforcement and attestation system supplies the rest — a point the repository makes about itself in ADR-0040, adding that any Tier 3 claim "must name the external system that actually enforces and must establish that system's independence out-of-band."

Table 13.1 is the chapter's core: each tier worked systematically through the eight questions.

| Question | Tier 1 — Design-time | Tier 2 — Cooperative runtime | Tier 3 — Independent |
|---|---|---|---|
| **What is guaranteed?** | Declarations are valid, composed, unchanged since review, and approved against an exact revision | Calls on wrapped surfaces are evaluated against that contract; denials stop the call | Actions on covered surfaces cannot proceed without evaluation, and evidence of that is independently produced |
| **Which component enforces it?** | Nothing at runtime; the checker, composer, and lock verifier constrain artifacts only | The in-path decision component, invoked by the executing system | An external gateway, sandbox, identity boundary, or mesh authorization point the subject cannot route around |
| **What evidence proves it?** | Deterministic diagnostics, content digests, lock verification, bound approval records | Allow and deny outcomes on wrapped surfaces; runtime records bound to the revision; coverage inventory | The above plus authenticated producer identity, verified attestation, protected capture, independent logging, demonstrated coverage |
| **What assumptions are required?** | Reviewers read what they approved; the canonicalizer is stable; the repository is controlled | Every consequential surface is wrapped; the wrapper is actually invoked; the producer is honest | The enforcement point is unbypassable in the deployed topology; the attestation keys are protected; the producer is genuinely independent |
| **How is it bypassed?** | Run something other than what was declared; regenerate the lock around weakened inputs | Call the underlying surface directly; act through an unwrapped or undeclared surface | Compromise the enforcement point, its keys, or the network path; find a surface outside its coverage |
| **What if the enforcing component fails?** | Artifacts stop being verifiable; the pipeline gate fails closed, and nothing at runtime changes | Depends on design: fail-closed denies the call, fail-open silently permits it. Availability of the decision component becomes an availability property of the workload | Traffic is blocked or routed around, depending on topology; a fail-open bypass at this tier is a full loss of the claim |
| **Which claims does it support?** | "Declared, reviewed, approved, unchanged"; contract-level statements about intent | "Evaluated and enforced on these named surfaces, cooperatively" | "Enforced independently on these surfaces, with independently produced evidence" |
| **What remains unproven?** | All runtime behavior; the completeness of what was declared | That no undeclared surface exists; that no bypass occurred; that the records are complete or true | That coverage is total; that the external system's own controls hold; that the policy deployed matches the approved revision unless separately bound |

**Table 13.1 — The eight questions applied to each tier.** The teaching purpose is the bottom row. Every tier has a non-empty "unproven" cell, and the discipline of this book is that the cell is published alongside the claim rather than discovered during an incident. Reading across any row shows what buying the next tier actually purchases; reading down the last column shows what no tier removes.

## 13.5 Choosing a tier by consequence and adversary

Tiers cost money and latency and organizational effort, and they are not uniformly worth it. Two variables determine what a surface needs.

The first is <span class="ix" data-ix="consequence of failure">consequence of failure</span>: what happens once if the control does not hold. A research summary filed to the wrong internal folder is recoverable in minutes. A €50,000 payment adjustment submitted without approval is recoverable with effort and embarrassment. A production deployment of unreviewed code to a regulated payments service may not be recoverable at all. Consequence sets the floor.

The second is the <span class="ix" data-ix="adversary model">adversary</span> in scope, and it is the variable teams most often leave implicit. Tier 2 is a sound choice against *accident*: a planner that wanders outside its charter, a developer who forgets a constraint, a model that follows a malicious instruction in retrieved text. All of those go through the wrapper, because none of them is trying to avoid it. Tier 2 is not a sound choice against an adversary who can modify the agent's code or influence what it imports, because for that adversary the wrapper is one line to delete. If the threat model includes a hostile insider with commit access, or a supply-chain compromise of the agent's dependencies, cooperative enforcement is the wrong instrument regardless of how well it is implemented.

Table 13.2 works the two variables across the book's case studies.

| Surface | Consequence | Adversary in scope | Defensible tier |
|---|---|---|---|
| Atlas files a summary to an internal store | Low; recoverable | Accident; prompt injection | Tier 1 declaration plus Tier 2 on the tool surface |
| Atlas publishes to an external site | High; not recoverable once public | Prompt injection via retrieved content | Tier 2 minimum; Tier 3 at the network egress if external publication is ever reachable |
| Forge opens a pull request | Low; a human reviews it | Accident | Tier 1 plus Tier 2 |
| Forge merges to a protected branch | High; alters production software | Accident, and a compromised agent | Tier 3 at the repository boundary — branch protection is an independent enforcement point |
| Ledger executor submits a payment | Severe; financial and regulatory | Accident, insider, compromised dependency | Tier 3 at the banking interface; Tier 2 alone is insufficient |

**Table 13.2 — Tier selection worked across the case studies.** The teaching purpose is the fourth row: Northstar already owns a Tier 3 control for merges and calls it "branch protection." Independent enforcement is frequently something the organization has rather than something it must buy, and the design task is often to *bind* the existing independent control to the reviewed contract rather than to build a new enforcement point.

> **Design checkpoint.** For each governed surface, write one line: consequence if the control fails once; the adversary you are defending against; the tier that follows; and the tier you actually have. Rows where the last two differ are your risk register, stated in a form a risk committee can act on. Rows where the adversary column is blank are the rows to worry about first, because an unstated adversary defaults to "accident" in every reader's mind.

## 13.6 Tier language in procurement, audit, and the inflation anti-pattern

<span class="ix" data-ix="tier inflation">Tier inflation</span> is the practice of describing a control at a higher tier than its mechanism supports. It is rarely dishonest and almost always structural: the wording is inherited from a slide, the mechanism changed underneath it, and no reviewer had vocabulary precise enough to notice. Three forms recur.

**<span class="ix" data-ix="tier inflation!verb inflation">Verb inflation</span>** uses a Tier 2 or Tier 3 verb for a Tier 1 mechanism. "Our contract prevents secrets from reaching the model" describes a declaration as if it were a control. The repair is to name the mechanism: *declares and validates* at Tier 1, *evaluates and blocks on wrapped surfaces* at Tier 2, *enforces independently* at Tier 3.

**<span class="ix" data-ix="tier inflation!coverage inflation">Coverage inflation</span>** takes a genuine Tier 2 claim about three wrapped surfaces and states it about the application. This is the failure the surface-scoping rule of Section 13.1 exists to prevent, and it is the most consequential of the three, because the sentence is *true of the surfaces it was originally about*.

**<span class="ix" data-ix="tier inflation!evidence inflation">Evidence inflation</span>** presents supplied evidence as though it were observed: "verified," "attested," "proven." A validation report saying `pass` becomes "independently verified" somewhere between the pipeline and the executive summary. Chapter 11's supplied/observed distinction is the antidote, and the practical rule is that the word "independent" requires naming the independent party.

```text
Inflated:      "Nornyx enforces Northstar's AI governance policy and provides
                full audit evidence."

Hedged:        "We use a governance layer to help enforce policy, with
                comprehensive logging."

Tier-accurate: "Tier 1: the support-network contract is validated, locked, and
                approved against revision git:9f3c1a7. Tier 2 (cooperative,
                declared surfaces only): the three tool surfaces listed in the
                coverage inventory are evaluated in-path; allow and deny paths
                are exercised in CI; runtime events bind to that revision.
                Not claimed: any surface outside the inventory; producer
                authentication; completeness of the event stream."
```

**Listing 13.1 — One claim at three levels of honesty.** Illustrative — not drawn from the repository. The hedged version is worse than the inflated one for the reader: it sounds cautious while conveying nothing checkable. The tier-accurate version is longer, and every additional clause is a sentence someone can verify or refute — which is the only property that matters in an audit.

Inside an organization the same discipline takes the form of a <span class="ix" data-ix="claim register">claim register</span>: one entry per assurance claim, structured so that the tier and the unproven remainder cannot be dropped in transit. Listing 13.2 gives the shape; Chapter 39 builds a full register for the capstone system.

```yaml
claim_id: NS-ATLAS-002
claim: "Atlas cannot publish to an external site."
tier: 2                       # cooperative, declared surfaces only
surfaces_in_scope: [tool.publish_external, tool.file_internal]
evidence: [contract_digest, network_lock, coverage_inventory, deny_path_test, event_stream]
assumptions: ["all publication paths route through the wrapped tool surface",
              "the event producer does not omit or fabricate records"]
bypass_paths: ["direct call to the underlying client library",
               "any undeclared network egress from the agent process"]
on_component_failure: "fail-closed: the wrapped call is denied"
not_claimed: ["network-level egress control", "producer authentication",
              "completeness of the event stream"]
```

**Listing 13.2 — A claim-register entry.** Illustrative — not drawn from the repository. The last four keys are the ones that make the entry useful: assumptions can be checked, bypass paths can be tested, failure behavior can be injected, and `not_claimed` is what stops the claim from growing a tier on its way to a slide.

For procurement, the practical instrument is a small set of questions that force tier disclosure without requiring the reader to be an engineer: *Which specific surfaces does the control cover, and what is the list?* *What happens if my system calls the underlying function directly — is it blocked, and is there a record?* *Who produces the evidence, and can my system alter or suppress it?* *Show me one denial in your evidence, not one allow.* A vendor at Tier 3 answers all four immediately. A vendor at Tier 2 answers the first two and must qualify the rest. A vendor whose answers are about product categories rather than mechanisms is at Tier 1 and does not know it.

> **Case study — Gateway.** Thread D, which begins in earnest in Chapter 22, exists to make this chapter concrete. Northstar's Engineering Platform takes one logical workflow — a support-refund tool call — and implements it along the paths of Figure 13.2: framework-native and ungoverned; wrapped by a cooperative adapter; bypassed by calling the underlying function directly beneath that wrapper; and, as an architectural extension beyond the current repository, projected onto a mandatory external gateway. The same business function lands in a different column of Table 13.1 on each path. The bypass path is included deliberately, because a governance program that never demonstrates its own bypass has not measured its coverage. Chapters 22 through 25 build the paths; Chapter 14 turns the resulting coverage boundary into an inventory; Chapter 26 develops the external-enforcement path.

<figure class="nx-fig" id="fig-13-2">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow">
        <div class="node">Agent</div>
        <div class="arr">→</div>
        <div class="node untrusted">Refund tool (native)</div>
        <div class="arr">→</div>
        <div class="node">Refund service</div>
      </div>
      <div class="flow">
        <div class="node">Agent</div>
        <div class="arr">→</div>
        <div class="node">Cooperative wrapper ✋</div>
        <div class="arr">→</div>
        <div class="node">Refund tool</div>
        <div class="arr">→</div>
        <div class="node">Refund service</div>
      </div>
      <div class="flow">
        <div class="node">Agent</div>
        <div class="arr dashed">⇢</div>
        <div class="node">Refund tool (called directly)</div>
        <div class="arr">→</div>
        <div class="node">Refund service</div>
      </div>
      <div class="flow">
        <div class="node">Agent</div>
        <div class="arr">→</div>
        <div class="node authority">External gateway ⛔</div>
        <div class="arr">→</div>
        <div class="node">Refund service</div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 13.2 — One workflow at four assurance positions (Thread D preview).</b> Top to bottom: ungoverned; cooperative enforcement in the call path; the bypass that defines the cooperative boundary, which produces no governance record at all; and independent enforcement the agent cannot route around. The teaching purpose is that the business function is identical in all four rows — the tier is a property of the path, not of the workload.</figcaption>
</figure>

> **Misconception.** *"Tier 3 is the goal; Tier 1 and Tier 2 are stepping stones to be outgrown."* Tier 3 is strictly more expensive and strictly narrower in what it can express. Independent enforcement points work on the categories they can see — network destinations, API calls, identities — and are usually poor at the semantics governance cares about, such as whether this approval binds to that revision. Tier 1 remains the substrate at every tier, because Tier 3 enforces *something*, and that something is a declaration that had better be reviewed, locked, and approved. The mature architecture is not uniformly Tier 3; it is a system where each surface's tier is chosen deliberately, stated explicitly, and matched to consequence and adversary.

## Summary

Assurance tiers exist because natural language gives one verb to three different guarantees. Tier 1 covers design-time governance: validated, composed, locked, and approved declarations, defeated by running something that was never declared. Tier 2 adds a decision point in the execution path over surfaces named in a coverage inventory, defeated by not calling it — and a total bypass may leave no trace, so absence of records is not evidence of absence of action. Tier 3 relocates enforcement and evidence production to a component the governed system cannot bypass or influence, which demands authenticated producer identity, verified attestation, protected capture, deployment binding, independent logging, and demonstrated coverage; the affordances for accepting external evidence are not themselves Tier 3. Worked through the eight questions, each tier has a non-empty "what remains unproven" cell, and publishing that cell alongside the claim is the discipline. Tier selection follows from consequence of failure and from the adversary actually in scope, and tiers attach to surfaces and evidence packages, never to whole systems — which is precisely what tier inflation violates.

- Tiers are ordered by what defeats them, not by feature count.
- Tier 1 is the substrate at every tier; Tier 3 still enforces a declaration.
- Every Tier 2 claim carries the qualifier "cooperative, declared surfaces only."
- Tier 3 requires independence of both enforcement and evidence production.
- A tier applies to named surfaces and a specific evidence package.
- Cooperative enforcement is sound against accident, unsound against an adversary who can edit the code.
- The repair for an inflated claim is to name the mechanism and publish the "not claimed" list.

## Review questions

1. Three systems each state "the agent cannot publish externally." Assign each of the mechanisms in Section 13.1 to a tier and, for each, name the single change to the environment that defeats it.
2. Why does a total bypass of a cooperative enforcement point often leave no record at all, and what does that imply about reasoning from the absence of denial records?
3. An evidence stream declares an external producer and includes a signature reference. Explain why this does not, on its own, qualify the evidence as Tier 3, and list what would.
4. Using Table 13.2's method, choose a tier for an agent that reads customer support tickets and drafts replies for human sending. State consequence, adversary, and resulting tier, then state what changes if the replies are sent automatically.
5. Rewrite the following as a tier-accurate claim: "Our governed agent platform enforces least privilege and produces verified audit trails." Invent whatever surface names and revisions you need, and include a "not claimed" clause.
6. Why is Tier 3 not simply "better," and give one governance property that is easier to express at Tier 1 than at Tier 3.

## Exercises

1. Take a system you work on and build its tier map: list every surface through which the system can cause an external effect, assign each a current tier with the evidence that supports the assignment, and mark the surfaces where the assignment is a guess. Then write the eight-question row from Table 13.1 for the single highest-consequence surface.
2. Write a one-page claim register entry for one control: the claim sentence, the tier, the surfaces in scope, the evidence artifacts, the assumptions, the bypass paths, the behavior on component failure, and the explicit "not claimed" list. Then have a colleague attempt to defeat the claim on paper and record which cell of your entry was wrong.
3. Design the four procurement questions of Section 13.6 into a short vendor questionnaire, adding at most three of your own. For each question, write the answer you would expect from a Tier 2 vendor and from a Tier 3 vendor, so that the questionnaire is scorable by someone who has not read this chapter.

## Further reading

- [@slsa] — a mature, widely adopted level model for supply-chain assurance; useful for seeing how level definitions are written so that they resist inflation.
- [@nist-zta] — the architectural argument for enforcement points the subject cannot route around, which is the structural content of Tier 3.
- [@schneider-enforceable] — the formal boundary of what execution monitors can enforce, and therefore what any in-path decision point can and cannot deliver.
- [@in-toto] — attestation as a mechanism for the producer-independence property Tier 3 requires and Tier 2 cannot supply.
- [@soc2] — how assurance claims are framed and tested in an audit setting, and why scope statements carry as much weight as control descriptions.
