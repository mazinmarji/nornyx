---
chapter: 4
part: I
title: "Core Concepts and Vocabulary"
---

# Core Concepts and Vocabulary

> **Opening scenario.** Northstar Services' architecture review board convenes to decide what to build. Six proposals are on the table, and every one of them claims to solve "AI governance." The identity team proposes extending the corporate identity and access management system to issue credentials to agents. The platform team proposes routing all model traffic through a gateway that inspects prompts. A security architect proposes adopting a general-purpose policy engine already used for Kubernetes admission control. The data-platform team points out that the workflow engine already has approval steps. A vendor has demonstrated a compliance-management product that produces control evidence for auditors. And two engineers, who have read the last three chapters, argue that none of the six addresses the problem, while conceding they cannot yet say why in terms the board would accept. The board chair asks for a vocabulary: a map of what each of these things actually does, what problem each was designed for, and where the remaining gap is. This chapter is that map.

> **Learning objectives.**
> - Define policy-as-code, governance-as-code, and controls as executable contracts, and explain what distinguishes each from the others.
> - Separate design-time from runtime governance and explain why a complete discipline requires both.
> - Define the policy decision point and policy enforcement point, and distinguish evaluation from enforcement.
> - Distinguish evidence from assurance, and cooperative from independent enforcement, and state what an assurance tier claims.
> - Define, in preview form, agent identity, capability, trust zone, delegation, and approval.
> - Position governed agentic systems neutrally against twelve neighboring technology families, using dimensions rather than verdicts.

> **Prerequisites.** Chapters 1 through 3. In particular this chapter assumes the reachability–authorization gap (Chapter 1), the four drift types (Chapter 2), and the five assertion layers and eight questions (Chapter 3). No Nornyx knowledge is required or used.

## 4.1 Policy-as-code, governance-as-code, and executable contracts

Three phrases circulate in this space and are frequently treated as synonyms. They are not, and the differences between them determine what an organization actually gets.

<span class="ix" data-ix="policy-as-code">Policy-as-code</span> means expressing authorization rules in a machine-evaluable language rather than in prose, so that the rules can be versioned, reviewed, tested, and evaluated by a program. The idea is older than the phrase — the extensible access control markup language formalized the pattern in a standard form two decades ago [@xacml] — and it is now widely realized in languages such as Rego and Cedar [@opa; @cedar]. Policy-as-code answers one question well: *given a described request, what is the verdict?* It says nothing about where the description came from, whether the requester is who it says it is, what happens to the verdict, or what record survives.

<span class="ix" data-ix="governance-as-code">Governance-as-code</span> is the larger claim: that the *whole control apparatus* — not only the authorization rules but the identities, the capabilities, the trust boundaries, the approval requirements, the evidence obligations, and the relationships among them — is expressed in versioned artifacts from which downstream representations are derived rather than hand-maintained. The distinction matters because Chapter 2's drift taxonomy is a taxonomy of failures in everything *except* the authorization rule. A policy engine with perfect rules, embedded in an organization whose protected-path lists disagree across four artifacts, has solved the smallest part of the problem.

A <span class="ix" data-ix="control!as executable contract">control expressed as an executable contract</span> is the unit that makes governance-as-code concrete. A control in the traditional sense — the sense used by audit functions — is a statement of the form "production changes require approval by a qualified reviewer." As an executable contract, that statement acquires four additional elements: precise terms (what is a production change; who is qualified), an evaluation procedure (how the condition is checked, by which component), a failure behavior (what happens when the condition is not met, and what happens when the checking component itself fails), and an evidence obligation (what record is produced, bound to what). A control that lacks any of the four is still a control in the audit sense and is not executable, which is exactly the state Chapter 2 diagnosed.

> **Key idea.** The move from prose control to executable contract is not primarily about automation. It is about *making the control's terms and failure behavior explicit*. Most informal controls fail not because nobody executes them but because nobody ever settled what they meant at the boundaries — and the boundaries are where agentic systems live.

## 4.2 Design-time and runtime governance

Governance acts at two distinct moments, and conflating them produces both false comfort and unnecessary despair.

<span class="ix" data-ix="governance!design-time">Design-time governance</span> acts before the system runs, on artifacts. It asks whether the declared model is internally consistent, whether an agent's declared capabilities exceed what its role permits, whether a policy composition weakened an inherited constraint, whether the generated control artifacts still match their source, whether a lock still verifies. Its verdicts are computed by ordinary deterministic software over files, which means they inherit every property Chapter 1 said deterministic software still has: they are reproducible, testable, reviewable, and enforceable in continuous integration and continuous delivery (CI/CD). Design-time governance is where the four drift types are caught.

<span class="ix" data-ix="governance!runtime">Runtime governance</span> acts while the system runs, on requests. It asks whether *this* proposed action, by *this* actor, in *this* context, is permitted, and it records what was decided. Its verdicts must be produced in the execution path, under latency constraints, from inputs supplied by the running system.

The two are complementary in a way worth stating precisely. Design-time governance can establish properties of the *model* with high confidence and can establish nothing about behavior. Runtime governance can establish properties of *observed behavior* with confidence bounded by producer honesty and coverage, and can establish nothing about the actions it did not see. Neither subsumes the other, and an organization that has only one of them has a specific, nameable gap rather than a general weakness. Figure 4.1 places both on the lifecycle.

<figure class="nx-fig" id="fig-4-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Author contract</div><div class="arr">→</div><div class="node">Check consistency</div><div class="arr">→</div><div class="node">Compose and lock</div><div class="arr">→</div><div class="node">Derive artifacts</div><div class="arr">→</div><div class="node">CI gate</div></div>
      <div class="flow"><div class="node">Agent proposes action</div><div class="arr">→</div><div class="node">Evaluate</div><div class="arr">→</div><div class="node">Record decision</div><div class="arr">→</div><div class="node">Execute or refuse</div><div class="arr">→</div><div class="node">Evidence stream</div></div>
    </div>
  </div>
  <figcaption><b>Figure 4.1 — Design-time and runtime governance on one lifecycle.</b> The upper row acts on artifacts before deployment; the lower row acts on requests during execution. The teaching purpose is that the two rows are joined only by shared versioned artifacts — the contract and its digest — which is why binding decisions to a policy revision is load-bearing rather than bookkeeping.</figcaption>
</figure>

## 4.3 Decision and enforcement: PDP and PEP

The most important architectural distinction in this book is between deciding and enforcing, and it has a standard vocabulary that predates agentic systems by decades. The authorization framework literature names two roles [@rfc2904; @xacml].

A <span class="ix" data-ix="policy decision point">policy decision point</span> (PDP) evaluates a described request against policy and returns a verdict. It is a pure function of its inputs when evaluation is deterministic: the same described request under the same policy version yields the same verdict, anywhere, at any time, by anyone with the inputs. A PDP has no side effects on the world; it does not permit anything, it *concludes* something.

A <span class="ix" data-ix="policy enforcement point">policy enforcement point</span> (PEP) sits in the path of the action and makes the verdict consequential. It intercepts the proposed action, obtains a verdict, and either permits the action to proceed or prevents it. The PEP is where governance touches reality, and therefore where all of Chapter 3's uncomfortable questions apply: what path can avoid it, what does it do when it cannot reach the PDP, what record does it leave.

<span class="ix" data-ix="evaluation">Evaluation</span> and <span class="ix" data-ix="enforcement">enforcement</span> are worth separating in your vocabulary permanently, because they have different properties, different failure modes, and different assurance value. Evaluation can be made deterministic, tested exhaustively for the inputs that matter, reproduced offline by an auditor years later, and reasoned about formally. Enforcement cannot be any of those things; it is a position in a system, and its strength is a property of that position. A perfect PDP behind a PEP that half the code paths bypass yields a system with excellent verdicts and poor guarantees. Conversely, an unavoidable PEP consulting a crude PDP yields weak verdicts that actually bind. Most real architectures need to improve both, and the eight questions of Chapter 3 exist partly to keep the two from being reported as one number.

Listing 4.1 makes the *described request* concrete, because it is the object the rest of this book is really about. Note what it contains beyond a conventional access-control request: a mission and a position within it, a provenance tag on the context that produced the proposal, and the policy revision under which the verdict is to be computed.

```json
{
  "actor": {"identity": "northstar.engineering/forge", "authority": "non_human"},
  "capability": "repo.merge",
  "target": {"repository": "northstar/payments-api", "branch": "main"},
  "context": {"origin": "pull_request_body", "authority_rank": "untrusted"},
  "mission_id": "m-2026-06-18-002",
  "sequence": 4,
  "policy_revision": "c81d2f4"
}
```

**Listing 4.1 — A described action, the unit of abstraction of this discipline.** Illustrative — not drawn from the repository; field names are chosen for readability rather than to match any implementation. Every field is something a decision point may need and a conventional authorization request does not carry: the actor is declared non-human, the context is tagged with where it came from and how far it may be trusted, and the request is positioned within a mission so that sequence-dependent rules can be evaluated.

Figure 4.2 shows the sequence in the arrangement this book uses throughout.

<figure class="nx-fig" id="fig-4-2">
  <div class="fig-body">
    <div class="seq">
      <div class="seq-cols" data-cols="Agent|Enforcement point|Decision point|Evidence|Tool"></div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">proposed action (actor, capability, target, context)</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">described request + policy version</div>
      <div class="msg" data-from="3" data-to="2" data-kind="return">verdict: allow | deny | approval-required</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record decision, bound to revision</div>
      <div class="msg" data-from="2" data-to="5" data-kind="call">execute (only on allow)</div>
      <div class="msg" data-from="2" data-to="1" data-kind="deny">refuse (on deny or approval-required)</div>
    </div>
  </div>
  <figcaption><b>Figure 4.2 — Evaluate, record, execute.</b> The ordering is deliberate: the decision is recorded before the action runs, so that a crash between recording and execution leaves a decision without an action rather than an action without a decision. The teaching purpose is that the enforcement point owns the ordering guarantee, and that this ordering is a design commitment rather than an implementation convenience.</figcaption>
</figure>

## 4.4 Evidence, assurance, and the independence of enforcement

Three more pairs complete the core vocabulary.

<span class="ix" data-ix="evidence">Evidence</span> is a record produced to support a later claim, bound to the artifacts and versions it refers to. <span class="ix" data-ix="assurance">Assurance</span> is the degree of justified confidence that a claim holds, given the evidence and the assumptions. The distinction is the one Chapter 3 built: evidence is an artifact, assurance is a judgment about what that artifact supports. An organization can have abundant evidence and low assurance — a great many signed records from a producer nobody can hold accountable — and, less commonly, thin evidence and high assurance, where the architecture makes the guarded action structurally impossible so that little needs to be recorded. Throughout this book, "evidence" is never called "proof" when it was supplied by the system under examination.

<span class="ix" data-ix="cooperative enforcement">Cooperative enforcement</span> means the governed component must choose to route its actions through the enforcement point. An in-process wrapper around a framework's tool interface is cooperative: it works when the calling code calls the wrapped surface and does nothing when the calling code calls the underlying function directly. <span class="ix" data-ix="independent enforcement">Independent enforcement</span> — also called authoritative or mandatory enforcement — means the enforcement point occupies a position the governed component cannot avoid: a network gateway the traffic must traverse, a sandbox boundary the process cannot escape, an identity system that must issue a credential before the resource will answer. The distinction is not about quality of implementation. A meticulously engineered cooperative control and a sloppy mandatory one make claims of different *kinds*, and only the second survives question 7 of Chapter 3.

An <span class="ix" data-ix="assurance tier">assurance tier</span> names the strength of that structural position, so that claims can be compared. This book uses three, and previews them here only far enough to make the rest of Part I readable; Chapter 13 formalizes them, and Chapter 14 supplies the coverage and bypass analysis that makes a tier claim testable.

- **Tier 1 — design-time.** Claims about artifacts: the declared model is consistent, composition did not weaken an inherited control, the generated artifacts match their source, the lock verifies. Evidence is the artifacts and the checker's output. The claim survives an inattentive team and says nothing about runtime.
- **Tier 2 — cooperative runtime.** Claims about observed behavior over surfaces the integration covers: every recorded invocation of a wrapped surface was allowed by a decision under a named policy revision. Evidence is a producer-supplied stream. The claim survives a buggy actor and not a motivated one.
- **Tier 3 — independent enforcement.** Claims that hold regardless of the governed component's cooperation, because the enforcement point cannot be bypassed from inside. Evidence includes records from a producer the governed component does not control. This is the tier most organizations want and the tier that costs the most architecturally, because it requires owning a position in the execution path.

> **Misconception.** *"Tier 3 is simply Tier 2 done properly."* They differ in what an adversary must do, not in engineering care. Defeating a Tier 2 control requires declining to call it; defeating a Tier 3 control requires defeating a component. That is why a tier is a property of *architecture* rather than of code quality, and why claiming a tier is a claim about position, coverage, and producer independence — three things Chapter 14 teaches you to inventory.

## 4.5 Five terms in preview

Five further terms recur from Chapter 5 onward. They are defined properly there; brief definitions here make the positioning section readable and establish the distinctions that the neighboring technologies most often blur.

An <span class="ix" data-ix="agent identity">agent identity</span> is a stable, declared identifier for a non-human actor, distinct from the framework object that happens to implement it and distinct from the credentials of the process it runs in. The distinction matters immediately: three different frameworks may host the same logical agent, and one process may host several agents with different authority. Chapter 5 develops it.

A <span class="ix" data-ix="capability">capability</span> is a named unit of authority to perform a class of action on a class of target, held by an identity. Chapter 5 separates capability from permission and from authority carefully; for now, note only that a capability is *declared and held*, whereas the reachable set of Chapter 1 is merely *available*.

A <span class="ix" data-ix="trust zone">trust zone</span> is a declared boundary within which data of certain categories may move freely and across which movement is constrained. A trust zone is not a network segment; it is a statement about provenance and permitted flow, and its members may share a process. Chapter 6 develops zones and their relationship to prompt injection.

<span class="ix" data-ix="delegation">Delegation</span> is one identity conferring a bounded subset of its authority on another, for a bounded time, to a bounded depth. Delegation is the mechanism by which multi-agent systems either stay governable or quietly accumulate authority; Chapters 5 and 31 treat both cases.

An <span class="ix" data-ix="approval">approval</span> is a record of a human decision, bound to a role, an actor type, a specific revision of the thing approved, and an expiry, and capable of being invalidated when that revision changes. Every element of that sentence is load-bearing, and Chapter 9 spends a chapter demonstrating why an approval missing any one of them provides much weaker accountability than it appears to.

## 4.6 Positioning: twelve neighbors and one gap

The board in the opening scenario is not confused because its members are ignorant. It is confused because governed agentic systems genuinely overlap twelve established technology families, and each overlap is real. The productive way to compare them is by dimension rather than by verdict: what problem the family was designed for, what it takes as its unit of abstraction, where it enforces, what evidence it produces, whether its decisions are deterministic, and how mature it is. Two tables cover the twelve; Figure 4.3 shows where each sits relative to an agent's action.

Tables 4.1 and 4.2 are descriptive, not competitive. Every family in them does its own job better than a governance layer would, and several are prerequisites: a governance layer that cannot authenticate a human approver needs an identity system, and one that cannot see its own operation needs telemetry.

| Family | Problem it addresses | Unit of abstraction | Enforcement point | Evidence produced | Determinism | Maturity |
|---|---|---|---|---|---|---|
| Identity and access management (IAM) | Who is this principal, and what may it access? | Principal, role, resource | Resource-side, at credential use | Authentication and access logs | Deterministic policy evaluation | Very high |
| Role-based / attribute-based access control (RBAC / ABAC) models [@rbac-nist; @abac-nist] | Structuring authorization decisions | Role; attribute of subject, object, environment | Model, not a component | None inherently | Deterministic by construction | Very high |
| Policy engines: OPA, Cedar, XACML [@opa; @cedar; @xacml] | Evaluating authorization rules as code | Described request → verdict | None; a PDP is embedded by a host | Decision logs, if the host records them | Deterministic; analyzable in Cedar's case | High |
| API gateways | Mediating and controlling service traffic | HTTP request/response | In the network path, mandatory for traffic that routes through it | Access logs, rate-limit events | Deterministic rule matching | Very high |
| Service meshes [@istio; @envoy] | Service-to-service identity, encryption, and authorization | Workload identity, connection | Sidecar or node proxy in the data path | Connection-level telemetry and authorization logs | Deterministic | High |
| Zero-trust architecture [@nist-zta] | Removing implicit trust from network position | Subject, resource, per-request access decision | Policy enforcement point in front of every resource | Per-request decision records | Deterministic | High as a doctrine; varies in practice |

**Table 4.1 — Access-control and network-mediation families.** The dimension that separates all six from the problem of this book is the unit of abstraction: each governs a *principal reaching a resource*, and none has a representation for an action proposed by a probabilistic planner, its provenance, the sequence it belongs to, or the human accountability bound to it.

| Family | Problem it addresses | Unit of abstraction | Enforcement point | Evidence produced | Determinism | Maturity |
|---|---|---|---|---|---|---|
| Guardrails and prompt filters | Blocking harmful or off-policy text | Prompt or completion string | Around the model call | Scoring logs | Probabilistic | Moderate; fast-moving |
| Model safety systems | Reducing the model's propensity to produce harmful output | Model behavior in aggregate | Inside the model | None per action | Probabilistic | High for the models, no per-deployment claim |
| AI gateways | Centralizing model access, cost, keys, and rate limits | Model API request | In front of the model provider | Request and cost logs | Deterministic for routing; probabilistic for content checks | Moderate |
| Orchestration frameworks | Building agent workflows | Agent, task, tool, graph node | None; frameworks execute rather than restrain | Framework traces, if enabled | Not applicable | Moderate; version-volatile |
| Workflow engines | Coordinating long-running business processes with human steps | Process instance, task, approval step | Within the process, for steps routed through it | Process history | Deterministic | Very high |
| Observability [@otel] | Understanding what a system did | Span, metric, log record | None; observability observes | Traces and telemetry | Deterministic collection, sampled | Very high |
| DevSecOps controls [@nist-ssdf; @slsa] | Securing the software supply chain and delivery path | Build, artifact, provenance attestation | CI/CD pipeline and release gates | Attestations, signed provenance | Deterministic | High |
| Compliance-management platforms | Tracking and evidencing organizational controls | Control, policy document, task, ticket | None; they record rather than enforce | Assembled evidence packages | Not applicable | High |

**Table 4.2 — AI-era and delivery-lifecycle families.** Read the enforcement-point column: three of the eight have no enforcement point at all, three enforce over an abstraction that does not include tool actions, and the two that could enforce over model traffic operate on text rather than on described actions.

Several relationships deserve prose, because a table row cannot carry them.

**Policy engines are a component, not an architecture.** Rego and Cedar are excellent at the job they define: deterministic evaluation of a described request against versioned rules, with Cedar adding formal analyzability [@opa; @cedar]. That is the PDP of Section 4.3, and a governed agentic system can and often should project its policy onto such an engine — Chapter 26 works the projection through. What a policy engine does not supply is the description. Somebody must decide what an agent's proposed action *is* in terms the engine can evaluate: which identity, which capability, which zone transition, which occurrence in which sequence, with what provenance for the context that produced it. That modelling work is the substance of Parts II and IV, and it is invariant to which engine evaluates the result.

**IAM and RBAC/ABAC are necessary and insufficient.** Role-based access control gives a mature structure for assigning permissions to roles [@rbac-nist], and attribute-based access control generalizes it to conditions over subject, object, and environment attributes [@abac-nist]. Both assume the requester's identity is authenticated and the request is a resource access. Chapter 1's reachability–authorization gap explains why that is not enough here: the agent process holds the credentials, so every sampled action inherits them, and the interesting distinctions are between actions the same principal takes for different purposes at different points in a sequence. An agent identity needs to be governed *below* the credential, at the action.

**Gateways and meshes are the strongest available enforcement positions, and they see the wrong things.** A service mesh authorizes connections between workload identities [@istio; @envoy]; an API gateway authorizes HTTP requests. Both are mandatory for traffic that traverses them, which is precisely the Tier 3 property Section 4.4 named as expensive and desirable. Their limitation is representational: an agent calling a local function, writing a file, or invoking an in-process tool never produces traffic, and even when it does, an HTTP request to a payments API carries no notion of which mission it belongs to, which approval covers it, or whether the data in its body crossed a zone boundary on the way. The productive architecture is therefore not "gateway *or* governance layer" but a governance layer that produces the descriptions a gateway can enforce on — Chapter 26's subject.

**Zero-trust doctrine supplies the posture, not the model.** The zero-trust literature argues that trust should never derive from network position and that every request should be authorized against policy at the point of access [@nist-zta; @beyondcorp]. That is the correct posture for agentic systems, and this book adopts it. What it does not supply is any account of an actor whose requests are generated by a sampler from partially untrusted input; the whole of Chapter 6's work on context provenance and authority exists in that gap.

**Guardrails, model safety, and AI gateways were covered in Chapter 2** and appear here only for placement: they operate on text, produce probabilistic verdicts, and leave no accountability binding. They belong in a defense-in-depth stack and cannot carry a Tier 2 or Tier 3 claim.

**Observability is the closest relative, and the relationship is instructive.** OpenTelemetry standardizes how systems emit traces, metrics, and logs [@otel], and a well-instrumented agent produces rich traces. The difference from evidence is not richness but *purpose and binding*: telemetry is designed to be sampled, aggregated, and expired, and it is not bound to the version of the policy that was in force or to the revision of the thing being changed. Chapter 11 draws the line carefully and argues that evidence and telemetry should be produced by the same instrumentation and treated by different retention and integrity rules.

**Compliance-management platforms sit at the other end.** They model controls, collect artifacts, and produce packages for auditors, which is genuinely useful and entirely downstream. Their evidence is whatever the organization gives them, so their output inherits every weakness in the collection path. A governance layer improves a compliance platform's inputs; it does not replace it, and the platform does not close the gap.

Figure 4.3 arranges the families by where they sit relative to an agent's proposed action, which is the arrangement that makes the remaining gap visible.

<figure class="nx-fig" id="fig-4-3">
  <div class="fig-body">
    <div class="zones">
      <div class="zone" data-name="Inside the planner">
        <div class="node">Model safety</div>
        <div class="node">System prompts</div>
      </div>
      <div class="zone" data-name="Around the text channel">
        <div class="node">Guardrails / prompt filters</div>
        <div class="node">AI gateways</div>
      </div>
      <div class="zone" data-name="At the action boundary — the gap this book addresses">
        <div class="node">Agent identity + capability</div>
        <div class="node">Trust zones and provenance</div>
        <div class="node">Decision point (may be OPA / Cedar)</div>
        <div class="node">Enforcement point + evidence</div>
        <div class="node">Approvals bound to revisions</div>
      </div>
      <div class="zone" data-name="At the resource">
        <div class="node">IAM / RBAC / ABAC</div>
        <div class="node">API gateway</div>
        <div class="node">Service mesh</div>
      </div>
      <div class="zone" data-name="Across the lifecycle (no action-level enforcement)">
        <div class="node">Workflow engines</div>
        <div class="node">Orchestration frameworks</div>
        <div class="node">Observability</div>
        <div class="node">DevSecOps controls</div>
        <div class="node">Compliance platforms</div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 4.3 — Ecosystem positioning by distance from the proposed action.</b> Each band groups families by where they act relative to the moment an agent proposes a tool call. The teaching purpose is that the third band is thinly populated by existing categories: the families above it govern text, those below it govern principals reaching resources, and neither has a representation for a described action carrying identity, capability, provenance, sequence, and human accountability.</figcaption>
</figure>

> **Design checkpoint.** For your own environment, place each of the twelve families on Figure 4.3's bands according to what you actually operate, then answer: which band is empty? For an action your most consequential agent could take, list every component that would evaluate it, in order. If no component in the third band appears in your list, the discipline of this book is describing a gap you have rather than one you might have.

The chapter's conclusion is deliberately modest. Nothing above says the twelve families are inadequate at their jobs; each is better at its job than any governance layer will be. The claim is narrower and, we think, harder to argue with: the *unit* that agentic systems make consequential — a described action, proposed by a probabilistic planner, carrying an identity, a capability, a provenance, a position in a sequence, and a human accountability — is not the unit of abstraction of any of the twelve. Parts II and III construct that unit and the machinery around it; Parts IV and V examine one implementation of the design-time and cooperative-runtime portions; and Chapter 26 returns to this table to show how the constructed unit is projected onto the enforcement positions that gateways, meshes, and platform policy engines already own.

## Summary

Policy-as-code makes authorization rules machine-evaluable; governance-as-code extends versioned, derived artifacts to identities, capabilities, boundaries, approvals, and evidence obligations; and a control becomes an executable contract when it acquires precise terms, an evaluation procedure, a failure behavior, and an evidence obligation. Governance acts at two moments — design time, over artifacts, where drift is caught, and runtime, over requests, where behavior is constrained and recorded — and neither subsumes the other. The decision point evaluates and the enforcement point enforces; evaluation can be made deterministic and reproducible, while enforcement's strength is a property of position. Evidence is an artifact and assurance is a judgment about what it supports. Cooperative enforcement requires the governed component's participation; independent enforcement does not, and the difference is what the three assurance tiers name. Against twelve neighboring technology families, the distinguishing feature of this discipline is not superiority but unit of abstraction: none of the twelve represents a described action carrying identity, capability, provenance, sequence position, and human accountability.

- Policy-as-code is a component; governance-as-code is an architecture; an executable contract is the unit that connects them.
- Design-time governance catches drift; runtime governance constrains and records behavior; both are required.
- PDP and PEP have different failure modes and different assurance value and should never be reported as one number.
- Assurance tiers name structural independence, not engineering quality.
- The twelve neighboring families each solve their own problem well; the gap is at the action boundary, and it is a modelling gap before it is a tooling gap.

## Review questions

1. Distinguish policy-as-code from governance-as-code using one of Chapter 2's four drift types that policy-as-code alone cannot address.
2. A team has a deterministic PDP with a comprehensive rule set and a PEP that roughly half the code paths bypass. A second team has a crude PDP behind an unavoidable PEP. Which system supports the stronger claim, and about what?
3. Explain why a control that lacks a defined failure behavior is not an executable contract, referring to Chapter 3's question 6.
4. Give one governance property that a service mesh can enforce and a cooperative in-process wrapper cannot, and one that the wrapper can express and the mesh cannot. What does the pair imply for architecture?
5. Using Table 4.2, explain why observability data and evidence should be produced by the same instrumentation but governed by different retention rules.
6. State, in one sentence each, what a Tier 1, Tier 2, and Tier 3 claim asserts about an adversary.

## Exercises

1. **Place your stack.** Inventory the components in your environment that correspond to the twelve families, and place each on Figure 4.3's bands. For the single most consequential action an agent in your environment could take, write the ordered list of components that would evaluate it. Identify the first band at which nothing appears, and write two sentences on what an attacker or a mistake could do in that band today.
2. **Contract-ify a control.** Take a control written in prose in your organization ("access to production data requires approval"). Rewrite it as an executable contract with all four elements from Section 4.1: precise terms, evaluation procedure, failure behavior, and evidence obligation. Note every ambiguity you had to resolve, and identify which of them a reasonable colleague would resolve differently.
3. **Draw the boundary.** Choose one family from Table 4.1 and one from Table 4.2 that your organization already operates. For each, write a paragraph stating what it would take for that component to enforce an agentic governance decision, what it would need to be told, and what it still could not see. Conclude with the one integration you would build first.

## Further reading

- [@xacml] — the canonical formulation of the decision/enforcement separation and its vocabulary; read it for the architecture even if you never use the language.
- [@cedar] — a modern authorization language designed for analyzability; the clearest available statement of what deterministic, verifiable policy evaluation buys.
- [@abac-nist] — the reference treatment of attribute-based access control, and useful for seeing exactly which attributes an agentic action needs that conventional models do not carry.
- [@nist-zta] — the doctrine this book adopts for posture; read Sections 2 and 3 for the per-request access-decision model.
- [@otel] — the observability specification, useful for understanding what your instrumentation already emits before you design an evidence contract in Chapter 11.
