---
chapter: 30
part: VI
title: "Governing Software-Development Agents"
---

# Governing Software-Development Agents

> **Opening scenario.** Pull request #1847 against `northstar/payments-api` is Forge's work: a fix to a failing settlement migration, proposed on a branch, tests green. It touches one file under `auth/` — a session-validation helper moved during the refactor — and that path is on the security-sensitive list, so the merge lane demands an approval from a security reviewer in addition to the ordinary one. The engineer who instructed Forge to fix the migration is himself a security reviewer, and he approves his own request at 15:12. At 15:13 the lane refuses the merge anyway, citing the separation-of-duties assignment: the initiating engineer is the maker of this change, whatever the commit metadata says, and a maker cannot be its checker. He is mildly annoyed for about a minute, until he reads the refusal's reason string and recognizes it as a rule he voted for in the design review three months earlier. This chapter is that design review, reconstructed in full: every decision Northstar made to let a probabilistic planner work on a payments codebase without ever holding the keys to it.

> **Learning objectives.**
> - Design the identity and capability set for a software-development agent: which actions are freely allowed, which are gated on human approval, and why the boundary sits where it does.
> - Build the agent's delivery contract on the repository's real bundled example, distinguishing quoted real blocks from clearly labelled illustrative extensions.
> - Specify the approval context — what a human reviewer must be shown — for each gated action class, and wire maker–checker separation so that directing an agent counts as making.
> - Trace two fail-closed behaviors end to end: a drift gate blocking the merge lane, and a stale approval invalidated by a force-pushed revision.
> - Apply the five-test rule to a single gate, and write a governance claim in the eight-element format this book uses for complete worked examples.
> - State honestly what the repository's separation-of-duties machinery contains and where it runs, and name what a cooperative layer cannot prevent and which surrounding platform controls carry the remainder.

> **Prerequisites.** Chapter 5 (identity and capability), Chapter 9 (approval bindings, maker–checker, invalidation — this chapter builds on those semantics and does not restate them), Chapter 14 (bypass and coverage), Chapter 15 (the five-test rule), Chapter 17 (the contract language), Chapter 19 (the authorization interface), Chapter 28 (the authoring workflow), and Chapter 29 (the pipeline lanes Forge runs in). Thread B has been accumulating since Chapter 2; this chapter is its full design.

## 30.1 Why the development agent is the canonical case

Of the five Northstar threads, Forge is the one this book treats as the showcase, and the reason is structural rather than dramatic. A <span class="ix" data-ix="software-development agent">software-development agent</span> occupies the most dangerous position an agent can hold — its outputs are *executable*, so a bad action does not merely produce a wrong answer but changes what the system will do forever after — and simultaneously the most governable position, because software delivery is the one domain where organizations already operate a dense lattice of controls: version control, branches, reviews, protected branches, continuous integration (CI), release tags. Governance for Forge does not have to be built on bare ground. It has to be *mounted on* existing machinery, and the design question is where each obligation attaches.

That framing yields the design method for the whole chapter. For every action Forge might take, ask three questions in order. Is the action **reversible and observable** — can a human see it and undo it before consequence? Then it can be freely allowed, because the review that matters happens after the fact at zero marginal cost. Is the action **consequence-bearing but mediated** — does it pass through a chokepoint the platform already controls, like a merge to a protected branch? Then gate it there, with an approval bound the way Chapter 9 specified. Is the action **consequence-bearing and unmediated** — reachable without any chokepoint, like an outbound network call from a test process? Then the governance layer can only declare and detect, and the honest design says so in the coverage inventory rather than pretending a gate exists.

> **Key idea.** The <span class="ix" data-ix="allowed set">allowed set</span> is not "low-risk actions." It is *actions whose worst outcome is a bad proposal* — and a proposal, by construction, is an artifact a human will judge before it becomes consequence. Everything Forge may do freely (read, branch, test, open a pull request) shares one property: it adds reviewable material to the world without changing what any production system does. The gated set is everything that converts a proposal into a consequence. Keeping that line crisp is worth more than any individual rule, because every future capability request can be adjudicated against it in one sentence.

## 30.2 Identity, capabilities, and the decision table

Forge's identity follows the pattern Chapter 5 established for Atlas: a namespace and subject distinct from any framework's internal naming, with framework bindings resolving the runtime's agent key to the governed identity. For Northstar's design: namespace `northstar.engineering`, subject `forge`, identity class `local_agent`, authority `non_human`, `can_approve: false` — the last two being, in the agentic-network schema Nornyx ships, constants that an identity declaration cannot set otherwise **[implemented]**, so an approving Forge is unrepresentable before any check runs.

The capability set falls out of Section 30.1's method. Table 30.1 is the <span class="ix" data-ix="decision table!agent capabilities">decision table</span> the rest of the chapter elaborates: every Forge action class, its decision domain, who must approve, and the evidence each action class must produce. The action classes and their dispositions are Thread B's canon; the role names and evidence identifiers are Northstar's illustrative design, built to the field shapes the repository's schemas define.

| Action class | Decision | Approver (eligible roles) | Maker–checker constraint | Evidence required per action |
|---|---|---|---|---|
| Inspect: read repository, history, issues | allow | — | — | none beyond trace |
| Propose: create branch, commit to own branch | allow | — | — | `patch.diff`, `changed_files.zip` |
| Test: run the suite in an isolated runner | allow | — | — | `test_report.json` |
| Open pull request | allow | — | — | PR body generated from evidence set |
| Merge to protected branch | approval-required | `code_reviewer`; plus `security_reviewer` when the diff touches `auth/`, `crypto/`, or CI workflow files | approver ≠ Forge, ≠ the engineer who initiated the task | full evidence set + `approval_log.json`, approval bound to exact head revision, 24-hour expiry |
| Production deployment | approval-required | `release_manager` | requester ≠ approver | release manifest digest, deployment record |
| Release publication | approval-required | `release_manager` via the release lane only (Chapter 29) | tag-to-version binding; environment reviewer | signed run log, version-location tests green |
| Secrets access | deny (no capability declared) | escalation is a policy change, not an approval | — | denial recorded |
| Destructive change: schema drop, force-push, data deletion | deny by default; narrow, expiring exception possible (Chapter 28) | exception approver ≠ requester | `SOD_SELF_APPROVAL` class of checks | exception record with closure evidence |

**Table 30.1 — Forge's action classes: decisions, approvers, and evidence.** Illustrative design following the case-study canon; field shapes follow the repository's approval and exception schemas. Three readings matter. The *deny* rows are not approval-required rows with a strict approver — secrets access has no declared capability at all, so under deny-by-default semantics there is nothing an approval could attach to, and widening it means a reviewed contract change travelling Chapter 28's lifecycle. The evidence column is *per action class*, not per gate: proposal-class actions produce evidence nobody gates on, because the evidence's consumer is the eventual merge reviewer, not an enforcement point. And the security-sensitive path condition modifies the approver set rather than the decision — the merge is approval-required either way; the diff's content decides who may say yes.

Note what the <span class="ix" data-ix="security-sensitive path">security-sensitive-path</span> rule is *not*, because this is where designs quietly overclaim. It is not a Nornyx rule. Chapter 28 showed that the contract's rule strings match tokens in agent-step text, and no shipped matcher inspects a diff for path prefixes. The path condition is enforced where diffs are visible: in the merge lane's own logic and in the platform's code-ownership configuration, both outside the contract. The contract *declares* the requirement — so it is reviewable, versioned, and driftable — and the lane implements it. Declaring in one place and enforcing in another is not a defect; failing to know which place does which is.

## 30.3 The delivery contract

Forge's contract is patterned on the repository's bundled delivery example, and it is worth quoting the real blocks before extending them, because the example already contains most of the load-bearing declarations. Listing 30.1 is real repository text.

```yaml
policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm
      - deny production_write_without_approval
      - require tests_if_code_changed
      - require evidence_if_harness_completed
      - require supply_chain_check_if_dependency_added
# ...
harnesses:
  - name: DevHarness
    context: RepoContext
    flow:
      - agent: Architect
        action: plan
      - agent: Builder
        action: implement
      - tool: tests
        action: run
      - eval: RegressionEval
        action: run
      - evidence: DevEvidence
        action: pack
    repair:
      - on: test_failure
        agent: Builder
        action: repair
        max_attempts: 3
    gate:
      - require: tests.pass
      - require: security.pass
      - require: human_approval_before_merge

approvals:
  - name: HumanMergeApproval
    required_for:
      - production_deploy
      - policy_change
      - self_modification
```

**Listing 30.1 — The real bundled delivery blocks Forge builds on.** From `examples/governed_delivery_control_plane.nyx` (abridged; the full file also declares the constitution, context taint, skills, traces, evals, evidence set, and budgets). Two details reward attention. The repair loop is bounded — `max_attempts: 3` — which is the contract-level form of Chapter 12's attempt semantics: retries are expected, and their count is declared rather than emergent. And the gate names are free text the checker does not resolve (Chapter 28, Listing 28.3): `human_approval_before_merge` is a declaration the merge lane must implement, not a behavior this file causes.

Northstar extends the example in three places, and the extensions are illustrative — they use real field shapes from the repository's schemas but are this book's design, not repository text. First, the approval block is upgraded from the example's minimal three-line form to the full eight-binding form Chapter 9 taught, on the shape the repository's richer examples use:

```yaml
# Illustrative — Northstar's extension; field shape follows the repository's
# approval schemas, values are the case study's.
approvals:
  - name: ForgeMergeApproval
    required_roles: [code_reviewer]
    eligible_roles: [code_reviewer, security_reviewer, platform_owner]
    denied_actor_types: [ai_tool, execution_surface, autonomous_agent,
                         model, connector, generated_output]
    required_evidence: [test_report.json, security_report.md, approval_log.json]
    required_for: [merge_protected_branch]
    timing: before_merge
    accountable_authority: platform_owner
    revision_binding: {kind: git, revision: "git:<head revision>", exact: true}
    invalidation_conditions: [revision_change]
    expires_at: "<issue time + 24h>"
  - name: ForgeSecurityPathApproval
    required_roles: [security_reviewer]
    eligible_roles: [security_reviewer]
    denied_actor_types: [ai_tool, execution_surface, autonomous_agent,
                         model, connector, generated_output]
    required_evidence: [security_report.md]
    required_for: [merge_touching_sensitive_paths]
    timing: before_merge
    accountable_authority: security_owner
    revision_binding: {kind: git, revision: "git:<head revision>", exact: true}
    invalidation_conditions: [revision_change]
    expires_at: "<issue time + 24h>"
```

**Listing 30.2 — Forge's merge approvals, fully bound.** Illustrative extension of the bundled example. The 24-hour expiry follows the repository's own human-approval module, which sets `expires_after: PT24H` and `exact_revision_required: true` as composed defaults **[implemented]**; Northstar restates them per approval so the contract is legible without resolving the composition.

Second, the policy block is retargeted through a `ref` to `northstar-governance`'s canonical `SafeDeliveryPolicy` rather than carrying a copy — the mechanism Chapter 8 introduced and Chapter 28's Charter scene defended. Third, a `separation_of_duties` block is added; Section 30.7 examines exactly what machinery stands behind it. The generated artifacts — `AGENTS.md`, `policy.yaml`, and the rest — are committed under `.nornyx/`, and the drift gate of Chapter 29 runs over the full set in both lanes.

## 30.4 Approval context and the merge flow

Chapter 9's Table 9.2 stated what any approval interface must present. For Forge's merge gate, Northstar makes it concrete: the reviewer's screen assembles, from the evidence set, *the diff against the last approved revision* (not against the branch point — the difference is what changed since a human last judged, which after a repair loop is not the same thing); the exact head revision the approval will bind; the full action list the approval unlocks, which for `ForgeMergeApproval` is merging this revision and nothing else; the test and security reports with their status; the identity of the *initiating engineer*, displayed as prominently as Forge's own identity, because the maker–checker rule is about them; the expiry the record will carry; and the negative-scope statement — this approval does not attest to deployment safety, dependency licensing, or anything about paths outside the diff.

The last two rows exist because of failures, not theory. The initiating-engineer row is what makes the opening scenario's refusal explicable to its subject in one read: the interface had shown him, at approval time, that he was listed as the maker. Figure 30.1 places the whole flow, including the two refusal paths this chapter traces.

<figure class="nx-fig" id="fig-30-1">
  <div class="fig-body">
    <div class="seq">
      <div class="seq-cols" data-cols="Forge|Merge lane (CI)|Decision surface|Reviewer (human)"></div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">opens PR #1847; evidence set attached</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">check · drift · lock · evidence gates (Ch. 29)</div>
      <div class="msg" data-from="3" data-to="2" data-kind="return">green; merge is approval-required</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">approval context: diff, head revision, maker, scope, expiry</div>
      <div class="msg" data-from="4" data-to="2" data-kind="deny">self-approval refused: approver = initiating engineer (maker)</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">re-routed to an independent security reviewer</div>
      <div class="msg" data-from="4" data-to="2" data-kind="return">approval record bound to head 9f3c1a7, 24 h expiry</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">evaluate merge with approval record</div>
      <div class="msg" data-from="3" data-to="2" data-kind="deny">head moved (force-push): revision binding fails; refusal recorded</div>
      <div class="msg" data-from="2" data-to="1" data-kind="deny">merge blocked; re-approval of the new revision requested</div>
    </div>
  </div>
  <figcaption><b>Figure 30.1 — Forge's merge approval flow, with both refusal paths.</b> The teaching purpose is the two distinct denials. The first happens at approval <em>collection</em>: the maker–checker rule rejects the initiating engineer before any record exists. The second happens at approval <em>use</em>: a record that was valid when issued fails its revision binding at the moment of enforcement, because the subject moved underneath it. Chapter 9 taught these as different mechanisms (constraint on eligibility versus invalidation); this figure shows them landing at different points in one real lane, which is why implementing only one of them leaves a hole the other was built for.</figcaption>
</figure>

The <span class="ix" data-ix="maker–checker!initiator mapping">maker–checker wiring</span> deserves one paragraph of precision, because the naive implementation misses the case that matters. "Forge cannot approve" is free — it falls out of the non-human constants and the denied actor types, enforced at five independent layers as Chapter 9 documented **[implemented]**. The binding constraint is the second clause: *the human who directed the agent cannot approve its output*. No commit metadata records direction, so Northstar makes it recordable by construction: every Forge task carries an <span class="ix" data-ix="initiator identity">initiator identity</span> from the task-submission system into the evidence set, and the merge lane treats that identity as the change's author for every separation-of-duties purpose. That mapping — task initiator becomes SOD author — is the single most important line of integration code in the whole design, and no shipped tool provides it, because no shipped tool knows how Northstar submits tasks.

## 30.5 Fail-closed, twice

Thread B's canon specifies Forge's fail-closed posture: if the policy artifacts drift or the lock fails verification, CI blocks the merge lane entirely. Chapter 29 showed the first behavior mechanically — the hand-edited `policy.yaml`, the `[CHANGED]` report, exit codes 1 and 2, the lane refusing everything until the artifacts are regenerated from the contract or the contract change is reviewed. What that scene looks like from the governance perspective is worth stating once: *the bypass attempt was a write to a generated artifact*, the classic move of someone routing around a policy by editing its compiled output, and the drift gate converts it from a quiet success into a loud integrity failure. The remediation is also the review: either the edit was wrong (regenerate and move on) or the edit was right (make it in the contract, where it gets a reviewer).

The second behavior is the <span class="ix" data-ix="stale approval!revision binding">`9f3c1a7` scene</span>, and since Chapter 9 established its semantics, this chapter can run it through the actual decision surface. Listing 30.3 shows the merge lane's evaluation step, written against the real authorization interface from Chapter 19.

```python
# Illustrative — Northstar's merge-lane step. The names are the real
# nornyx.agentic service provider interface (SPI) 1.2 surface; the
# deployment glue is this book's design.
from nornyx.agentic import (
    load_authorizer, ApprovalRequest, ApprovalAssertion, EvaluationContext,
)

authorizer = load_authorizer(
    "delivery.nyx", "nornyx.agentic_network.lock",
    validation_as_of=pipeline_instant,          # fail-closed: CONTRACT_INVALID /
)                                               # PROFILE_MISSING / LOCK_INVALID / LOCK_STALE

assertion = ApprovalAssertion(
    approval_ref="ForgeMergeApproval",
    claimed_approver_ref="user:s.laurent",
    claimed_actor_type="human",
    role="security_reviewer",
    granted=True,
    action_ref="merge_protected_branch",
    subject_revision="git:9f3c1a7" + APPROVED_TAIL,   # the revision the reviewer read
    expires_at=record_expiry,
    evidence_refs=("test_report.json", "security_report.md", "approval_log.json"),
)
decision = authorizer.evaluate(
    ApprovalRequest(identity_ref="identity.forge", approval=assertion),
    context=EvaluationContext(
        decision_at=pipeline_instant,
        observed_subject_revision=current_head,       # the head being merged NOW
    ),
)
if not decision.allowed:
    fail_merge_lane(decision.code, decision.reason)   # APPROVAL_REVISION_MISMATCH
```

**Listing 30.3 — The stale approval refused at the moment of use.** Illustrative integration over the real SPI. After the 11:40 force-push, `current_head` is no longer the approved `9f3c1a7`: the assertion's bound revision fails the engine's universal revision check and the decision comes back deny with `APPROVAL_REVISION_MISMATCH` — checked, per Chapter 9's ordering, *before* the actor-type, role, evidence, and expiry checks, so the refusal names the binding that actually broke. The engine reads no wall clock; `decision_at` is supplied, so re-running the lane later cannot resurrect the approval by accident. And the refusal is not silent: the decision carries `approval_requested` and `approval_rejected` event intents, so the evidence stream records that a stale approval was presented and refused — which is itself the audit finding, pre-written.

Notice what neither behavior required: nobody watched for the force-push, subscribed to an event, or maintained a cache to invalidate. Both gates simply *re-derive* the governed state at the moment of consequence — regenerate and compare; re-evaluate the binding against the current head. <span class="ix" data-ix="fail-closed!by re-derivation">Fail-closed designs built on re-derivation</span> are dull and slightly wasteful, and they are immune to the entire class of failure where the invalidation signal was lost in transit.

## 30.6 One gate, completely

This book's standard for a fully worked governance example is <span class="ix" data-ix="worked example!eight-element format">eight elements</span>. Here is Forge's protected-branch merge gate in that format, followed by the five-test rule applied to it.

**1. Intended behavior.** A merge of Forge-authored work to a protected branch of `northstar/payments-api` proceeds only when the full evidence set exists, the governance artifacts are drift-free and lock-verified, and a valid approval — human, role-eligible, independent of both Forge and the initiating engineer, bound to the exact head revision, unexpired — accompanies the request.

**2. Policy.** `SafeEditPolicy` by reference from `northstar-governance` (real rule text in Listing 30.1); `ForgeMergeApproval` and `ForgeSecurityPathApproval` (Listing 30.2); the harness gate declarations `tests.pass`, `security.pass`, `human_approval_before_merge`; the separation-of-duties assignment naming the initiating engineer as author.

**3. Integration code.** The merge-lane steps of Chapter 29's Forge case study plus Listing 30.3: identity verification, check, drift, lock-check, evidence validation, then the approval evaluation, with the lane's required-check status as the enforcement hook.

**4. Expected decision.** For the compliant path: allow, with the decision recorded before the merge executes. For each defect: the specific deny — `APPROVAL_REVISION_MISMATCH` for a moved head, `APPROVAL_NON_HUMAN` for a machine approver, `APPROVAL_ROLE_INVALID` for an ineligible role, `APPROVAL_STALE` past expiry, `APPROVAL_EVIDENCE_MISSING` for an incomplete evidence set — and lane-level failure (exit 1 or 2) for drift and lock defects before approval is even evaluated.

**5. Resulting evidence.** The per-action evidence of Table 30.1; the decision events (`approval_requested`, then `approval_granted` or `approval_rejected`); the drift and lock-check reports; the audit package the lane deposits (Chapter 29, rule 6). A refused merge produces *more* recorded material than an allowed one, by design.

**6. Negative test.** The lane's test suite submits: a PR whose approval names the initiating engineer (must refuse at collection); a valid approval followed by a synthetic force-push (must refuse at use with the revision code); an approval asserted by an `ai_tool` actor (must refuse with the non-human code); and a hand-edit to `.nornyx/policy.yaml` (must fail the lane before approval evaluation). Each asserts the code, not merely the failure.

**7. Bypass attempt.** A maintainer with direct write access pushes to the protected branch without opening a pull request. Nothing in this design evaluates that push. Whether it is even possible is a branch-protection setting, outside the governance layer entirely — Section 30.7 completes this analysis.

**8. Assurance boundary.** The decision logic is Tier 1 evidence about declared policy; the blocking is the platform's, at the platform's assurance level; the evidence proves conformance of supplied records to the locked revision, not that the recorded events are complete or true. Every "prevents" in this section is scoped to actions that traverse the lane.

| Test | Forge merge-gate instantiation | What its absence would permit |
|---|---|---|
| Allow | Compliant PR merges exactly once; the allow decision and approval reference are recorded before the merge executes | A lane that logs after merging — a historian, not a gate |
| Deny | Self-approval and non-human approval each refuse with their named code; the branch is untouched (no merge commit exists) | An unrelated lane failure mistaken for enforcement |
| Failure | The merge action itself aborts mid-operation after an allow; the lane records the failure and no success event; the approval is *not* consumed as used | Evidence asserting a merge that never landed |
| Bypass | Direct push to the protected branch: the test asserts it is either impossible (branch protection on) or ungoverned-and-known (inventory row) — whichever the platform config says, the test pins it | The cooperative boundary silently drifting into an assumed mandatory one |
| Evidence | The full stream from the above validates strictly against the locked contract revision | Correct enforcement that cannot be demonstrated to the auditor who asks |

**Table 30.2 — The five-test rule applied to Forge's merge gate.** The bypass row is the unusual one: its assertion is *conditional on platform configuration*, so the test reads the branch-protection state and asserts the corresponding claim — pinning not just behavior but which claim the organization is currently entitled to make. When an administrator relaxes branch protection, this test, not an incident, is what notices.

## 30.7 What the repository provides, and what must surround it

Two honesty obligations close the chapter: what the shipped separation-of-duties machinery actually is, and what no cooperative layer can prevent.

> **Nornyx in practice.** The repository's separation-of-duties support is a schema, a module, and a set of structural checks — not an org chart and not a runtime. The schema (`schemas/separation_of_duties_v1.schema.json`, `nornyx.separation_of_duties.v1`) defines <span class="ix" data-ix="separation of duties!assignments">*assignments*</span>: each names a subject, a risk tier, an `author`, an `approvers` list (matching human-identity patterns — `user:`, `human:`, `person:` prefixes), `evidence_producers`, a `require_evidence_independence` flag, and optional requester/approver pairs for release and exception authority **[implemented]**. The block activates only when the `separation_of_duties` module is composed — it is not part of the minimal profile — and the module's own manifest declares its non-goals: "resolving organizational identity," "changing permissions or role membership" **[implemented]**. The structural checks are real and were exercised for this chapter: setting the example assignment's approver equal to its author yields `SOD_SELF_APPROVAL` ("The author cannot approve their own high-risk change"), and overlapping approvers with evidence producers under the independence flag yields `SOD_EVIDENCE_PRODUCER_SOLE_APPROVER`; the shipped example contracts (`examples/governance_foundations.nyx`, `examples/architecture_governance.nyx`) carry complete assignments. Three scope limits keep the label honest. The self-approval check fires for assignments declared `high` or `critical` — a medium-tier self-approval passes this specific check. The identities are *strings*: nothing verifies that `user:s.laurent` names a real person, one person, or the person who clicked — that is the identity provider's job. And the checks run when contracts are checked, not when merges happen: Northstar's lane enforces the rule at merge time using the contract's assignment as its configuration. The shipped machinery, precisely stated, is a reviewable, driftable, structurally validated *declaration* of who may check whose work — which is exactly the input the enforcing lane needs and could not otherwise version.

The <span class="ix" data-ix="bypass ledger">bypass analysis</span> follows Chapter 14's method: enumerate the paths to consequence that do not traverse the governed lane, and name what carries each. Everything in Table 30.3's right column is a platform control outside the governance layer — configuration of the code-hosting system, not of any contract — and the design is honest only while that attribution is kept.

| The cooperative layer cannot prevent | Carried by (outside the governance layer) | Residual if that control is absent |
|---|---|---|
| Direct push to a protected branch, no pull request | Branch protection rules; force-push and deletion restrictions | Any writer merges anything, ungoverned and unevidenced |
| Merging past a red gate | Required-status-checks configuration; "no administrator bypass" setting | The lane becomes advisory for exactly the people with the most power |
| Sensitive-path changes reviewed by the wrong people | Code-ownership rules (e.g., a CODEOWNERS file) requiring owner review per path | The `security_reviewer` condition in Table 30.1 is a wish |
| Hostile regeneration: contract, artifacts, *and* lock rewritten together consistently | Repository history review; protected history; the lock "binds bytes, not producers" (Chapter 12) | Drift and lock gates pass on content an adversary authored |
| Forge acting outside the delivery path (network calls from a test process, writes outside the repo) | Runner sandboxing and egress control; credential scoping — Tier 3 territory (Chapters 26, 33) | The contract's `deny secrets_to_llm` is a declaration with no enforcement point on this path |
| A human lying in an approval (rubber-stamping) | Approval-context design (Section 30.4), gate-rate instrumentation, audit sampling — organizational controls | Records without judgments; Chapter 9's fatigue arithmetic |

**Table 30.3 — Bypass ledger for Forge.** The teaching purpose is the attribution discipline: every row's remedy is real, available, and *not part of the governance layer*, so a claim of the form "Forge cannot X" is true only as "Forge cannot X through the governed lane, and the platform is configured so no other lane exists — verified by the bypass tests of Table 30.2." The fourth row deserves special notice because it is the one the repository itself flags: a consistent lock can be regenerated by a hostile local writer, so detecting unauthorized regeneration is a repository control, not a lock property.

> **Case study — Forge.** The design review closes with the claim-register entries that Chapter 39 will compose. Row: *"Forge-authored changes reach protected branches only with an independent, revision-bound, unexpired human approval."* Component: the merge lane's approval evaluation, plus branch protection and required checks. Evidence: decision events, approval records, the bypass test pinning the branch-protection state. Tier: 2 on the lane, conditional on platform configuration for lane exclusivity. Residual: administrator bypass, hostile regeneration, off-path actions. Row two: *"No policy reaches Forge except through a reviewed contract change."* Component: the drift and lock gates over the full artifact set. Evidence: the drift report, lock-check output, the caught hand-edit from Chapter 29's scene. Residual: a writer who changes contract, artifacts, and lock together — carried by history review. The register is four rows long and every row names what it does not cover, which is why the Risk & Audit chief signs it. Thread B returns in the capstone, where Forge's register composes with Atlas's, Ledger's, and Charter's.

> **Misconception.** *"Once the contract, gates, and approvals are in place, the agent is safe to scale up."* The design in this chapter bounds *consequence*, not competence: it ensures bad proposals die as proposals and consequential actions carry human judgment. It does nothing to make Forge's proposals good, and it measurably increases reviewer load — which Chapter 9's fatigue arithmetic says is the design's real scaling limit. Scaling Forge means scaling the checker population and the per-item review cost, or the gates degrade into the click-through state where every record is green and no judgment occurred. Governance determines who is accountable when the agent is wrong; it does not reduce how often the agent is wrong.

> **Design checkpoint.** For a development agent in your organization — or the one being proposed — write down: the one-sentence allowed-set rule (Section 30.1's "worst outcome is a bad proposal," or your replacement); the decision table in Table 30.1's format, with your role names; the mapping from task initiator to SOD author, and which system records it; the two fail-closed behaviors, and what re-derives state at the moment of consequence; and the bypass ledger, with each row's carrier named and its current configuration verified — not remembered.

## Summary

A software-development agent is the canonical governance case because its outputs are executable and its habitat is already dense with mountable controls. Forge's design starts from one line — freely allow only actions whose worst outcome is a bad proposal — and derives the rest: inspect, propose, test, and open pull requests are allowed; merge, deployment, release, secrets, and destructive changes are gated or denied, with the approver set tightened on security-sensitive paths. The contract builds on the repository's real bundled delivery example, extending its minimal approval into fully bound records and referencing the canonical org policy rather than copying it, with all extensions labelled as this book's design. Approval context makes the maker–checker rule enforceable by displaying the initiating engineer as the maker, and the one indispensable integration line maps task initiator to separation-of-duties author. Fail-closed behavior appears twice, both times by re-derivation rather than notification: the drift gate converts a hand-edit of a generated artifact into a lane-blocking integrity failure, and a force-push past an approved revision surfaces as `APPROVAL_REVISION_MISMATCH` at the moment of use, with the refusal itself recorded as evidence. The merge gate survives the eight-element format and the five-test rule, including a bypass test whose assertion is conditional on platform configuration. The repository's separation-of-duties machinery is honestly a schema, a module, and structural checks over declared assignments — exercised live for this chapter — while identity truth, merge-time enforcement, branch protection, required checks, and code ownership are the surrounding platform's controls, named as such in the bypass ledger. The design bounds consequence and allocates accountability; it does not make the agent good, and its scaling limit is reviewer attention.

- The allowed/gated line is "adds reviewable material" versus "converts a proposal into a consequence."
- The human who directed the agent is a maker; record the initiator or maker–checker has a hole shaped like your best engineers.
- Fail-closed by re-derivation beats fail-closed by notification: no signal to lose.
- A refused merge produces more evidence than an allowed one.
- Declared in the contract, enforced in the lane, carried by the platform — keep the three attributions straight.
- Scaling an agent scales its checkers, or it scales nothing.

## Review questions

1. Using Section 30.1's three questions, classify these Forge actions and justify each in one sentence: rebasing its own proposal branch; adding a new third-party dependency to a proposal; commenting on a colleague's pull request; deleting its own stale proposal branches.
2. The opening scenario's engineer approved a change he initiated but did not write. State which clause of the maker–checker rule set catches this, why commit metadata cannot, and what single piece of recorded data makes the rule enforceable.
3. Trace the `9f3c1a7` scene through Listing 30.3: name the field of the assertion and the field of the context that diverge, the decision code produced, why that code appears rather than `APPROVAL_STALE`, and what two event intents the refusal records.
4. Table 30.2's bypass test asserts a claim *conditional on platform configuration*. Explain what this test detects that a fixed-assertion test would miss, and describe the organizational event it is most likely to catch.
5. A vendor states: "our development agent cannot access secrets." Using Table 30.3, write the two-sentence honest version of that claim for Forge, naming the enforcement each sentence relies on.
6. The chapter claims a refused merge produces more evidence than an allowed one, by design. Explain why that asymmetry is desirable, and which Chapter 9 failure mode it defends against.

## Exercises

1. **Write the decision table for your repository.** Produce Table 30.1 for a real repository your team owns, assuming an agent with Forge's allowed set. For every approval-required row, name the eligible roles by actual role name, the evidence artifacts your current tooling can already produce, and the ones it cannot. The gaps in the last column are your integration backlog; estimate each.
2. **Run the eight elements against one existing gate.** Take a gate your organization already operates — a deployment approval, a schema-migration review — and write it out in the eight-element format of Section 30.6. Elements 6 (negative test) and 7 (bypass attempt) will likely be empty; write one of each and run them. Report what the bypass attempt found, and whether the claim you would have made last week survives it.
3. **Verify the bypass ledger.** For a protected branch in a repository you can administer, check — in the platform's settings, not from memory — each of Table 30.3's first three rows: can anyone push directly, can an administrator merge past a red required check, and does path-based ownership review exist for your sensitive paths. Write the three claims your current configuration entitles you to make, in Chapter 14's qualified form, and file a change request for the largest gap between the claim you want and the claim you have.

## Further reading

- [@clark-wilson] — well-formed transactions and separation of duties; the integrity model Forge's maker–checker wiring and SOD assignments instantiate.
- [@saltzer-schroeder] — separation of privilege and least privilege as design principles; the fifty-year-old argument behind Table 30.1's deny rows.
- [@nist-ssdf] — secure-development practices; useful for mapping Forge's lanes onto a framework a security assessor already speaks.
- [@owasp-agentic] — threat framing for agentic systems; read its agent-autonomy threats against Table 30.3's ledger to see which are carried and which are residual.
- [@anthropic-agents] — a practitioner account of agent design; its emphasis on simple, inspectable agent loops complements this chapter's emphasis on inspectable authority around them.
