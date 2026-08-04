# Stage 2 — Developmental Design

## Title

**Governed Agentic Systems**
*Engineering Policy, Enforcement, Evidence, and Assurance — with Nornyx*

Edition note: First Edition (Development). Repository basis: `mazinmarji/nornyx` @ `70d2b40ad79293209b43bdaa375f20badf63bdd7`,
distribution 1.11.0, language/schema 1.0, agentic SPI 1.2, runtime-events 1.1, lock format 1.0.

## Thesis

Agentic AI systems act through tools with real-world consequences, but their behavior is
probabilistic and their instructions are forgeable. Organizations therefore need a *deterministic
governance boundary*: an explicit, versioned, testable model of who may act, on what, under which
conditions, with what evidence, and under whose accountability. This is an engineering discipline
with its own semantics (policy evaluation), architecture (decision/enforcement separation, trust
zones, adapters), artifacts (locks, evidence, approvals), and assurance theory (tiers, coverage,
bypass, audit). Nornyx is used throughout as a concrete, inspectable implementation of the
design-time and cooperative-runtime layers of that discipline — and, just as importantly, as a
case study in *honest claim boundaries*: what a governance layer can guarantee, and what it cannot.

## Audience and prerequisites

Primary: software engineers, agent-system developers, enterprise/platform architects, security
engineers, SRE/operations, governance and risk professionals, auditors, policy authors, technical
product leaders, researchers, graduate students, advanced self-learners.
Assumed: basic software engineering (version control, CI, APIs, YAML/JSON, some Python reading
ability). NOT assumed: AI governance, agent frameworks, policy engines, assurance concepts.

## Reader-need mapping

1. *Why the discipline exists* → Part I. 2. *Principles independent of product* → Parts II–III.
3. *How Nornyx implements them* → Parts IV–V. 4. *Evaluate/integrate/extend/operate/audit* →
Parts VI–VIII + appendices.

## Pedagogical progression (applies inside every chapter)

intuition → formal concept → architecture → implementation (Nornyx where applicable) →
verification → limitations → advanced consequences. General problem always precedes Nornyx
vocabulary. Every Nornyx claim carries a status: **[implemented]** (code+tests at snapshot),
**[guidance]** (documented target architecture), **[extension]** (author's design, not in repo).

## The recurring reasoning framework ("the eight questions")

Introduced in Ch. 3, used throughout: What exactly is guaranteed? Which component enforces it?
What evidence proves it? What assumptions are required? How can it be bypassed? What happens when
the enforcing component fails? Which assurance tier does the claim support? What remains unproven?

## Recurring analogy — REMOVED (post-review decision)

An earlier draft carried a bounded telecom analogy (VoIP → IMS/VoLTE layering) in Ch. 2, 10, 26,
32, 37. It was removed in final review: it required niche background knowledge, and every lesson
it carried (functional decomposition, decision/enforcement separation, mandatory boundary
elements, layered policy, conformance-driven adoption) is taught directly with primary sources
from the field itself. The book now uses no extended cross-domain analogy; small local analogies
remain where they genuinely clarify.

## Part and chapter structure

Deviations from the commissioning outline (recorded in the change log): "Runtime Adapter
Conformance" merged into Ch. 25 with coverage; "Hyperscaler and Platform Strategy" merged into
Ch. 37 (adoption); capstone chapters 40–42 of the outline consolidated into two (40–41) to avoid
padding. Final count: 41 chapters, 8 parts, 11 appendices + instructor guide.

### Part I — Why Governed Agentic Systems Are Needed
1. **From Deterministic Software to Agentic Behavior** — control expectations engineers inherit;
   what breaks when the "program" is a probabilistic planner with tools; case-study universe intro.
2. **The Governance Gap** — scattered informal controls as an unprotocoled distributed system;
   governance debt; drift taxonomy (control/policy/configuration/framework-adapter); why model
   alignment, prompts, and guardrails do not close the gap. Telecom analogy #1.
3. **What Governance Can and Cannot Guarantee** — assertion layers (declaration/decision/
   observation/evidence binding/assurance claim); integrity vs authenticity vs completeness;
   the eight questions; fail-open vs fail-closed introduced conceptually.
4. **Core Concepts and Vocabulary** — the discipline's map: PDP/PEP, policy-as-code,
   governance-as-code, controls as executable contracts, design-time vs runtime governance,
   cooperative vs authoritative enforcement, assurance tiers (preview), relationship map to IAM,
   RBAC/ABAC, API gateways, service meshes, workflow engines, orchestration, guardrails, prompt
   filters, model safety, OPA/Cedar, AI gateways, observability, DevSecOps, compliance platforms
   (first comparison table).

### Part II — Foundations of Executable Governance
5. **Identity, Capabilities, and Authority** — agent identity vs framework identity; capability ≠
   permission ≠ authority; least privilege and object-capability heritage; scoped authority.
6. **Trust Zones and Boundaries** — zones as declared boundaries (not network segments);
   transitions, sharing, never-share; context origin/authority/taint; prompt injection as
   authority confusion; confused deputy.
7. **Policy Semantics and Deterministic Evaluation** — what a policy language must define;
   decision domains (allow/deny/approval-required); default-deny; determinism of evaluation;
   closed schemas; comparison with OPA/Rego and Cedar semantics.
8. **Policy Composition, Provenance, and Inheritance** — composing profiles/modules/overlays;
   precedence; provenance; the "silent weakening" problem; canonicalization and semantic identity.
9. **Approvals, Exceptions, and Human Accountability** — approval as a bound record (role, actor
   type, revision, expiry, invalidation, revocation); exceptions/waivers; maker–checker; informed
   approver; approval fatigue; stale approvals.
10. **Enforcement Models and Fail-Closed Design** — PDP/PEP separation; in-process cooperative,
    gateway, sandbox, IAM-boundary, mesh models; failure behavior of the enforcement point;
    fail-open catastrophes; telecom analogy #2 (control plane vs media plane).

### Part III — Evidence and Assurance
11. **Runtime Evidence as an Engineering Artifact** — evidence vs logs vs telemetry; producers and
    trust; evidence contracts; retention and privacy tension.
12. **Integrity, Replay, Ordering, and Determinism** — hashing, content addressing, locks as
    binding structures; ordering and dependency checking; replay detection; the
    mission/operation/occurrence/attempt identity hierarchy (general form).
13. **Assurance Tiers** — tier model formalized (T1 design-time, T2 cooperative runtime, T3
    independent enforcement); tier claims vs deployment consequence; mapping claims to tiers.
14. **Bypass, Coverage, and Negative Controls** — coverage inventories; wrapper bypass; negative
    testing as a first-class control; unsupported-surface inventories as security information.
15. **Testing Governance Claims** — conformance suites; allow/deny/failure/bypass/evidence tests;
    failure injection; property-based thinking for policy invariants; governance CI.

### Part IV — Nornyx Architecture and Language
16. **Nornyx in Context** — system context diagram; what Nornyx is (executable specification and
    control-plane language) and is not (runtime, IdP, secrets manager, deployment engine);
    version axes; ecosystem positioning.
17. **The Nornyx Policy Model** — the `.nyx` contract walked block by block from real examples:
    project, contexts (authority/taint), policies (rule atoms), agents, skills, harnesses, gates,
    evidence, approvals; `ref` for shared policy; checker semantics.
18. **Profiles, Modules, Locks, and Digests** — domain profiles; governance modules; composition
    and provenance in implementation; the agentic-network lock and profiles lock; digest scheme.
19. **The Authorization SPI** — SPI 1.2; `load_authorizer`; AuthorizerState frozen views;
    single-interpretation principle; split-brain hazard; M2-D legacy shim as a compatibility study.
20. **Evidence Architecture** — runtime-events 1.0/1.1; explicit occurrence mode; envelope
    binding; validation pipeline; resume/cumulative evidence; strict mode; proof boundary.
21. **Diagnostics and Generated Artifacts** — generator outputs; determinism mechanisms;
    diagnostic codes as API; drift gate mechanics; workspace checks.

### Part V — Framework and Runtime Integration
22. **Designing an Adapter Boundary** — adapter contract; surface binding; normalization;
    evaluate-record-execute; exactly-once locality; coverage inventory as API.
23. **CrewAI Integration** — wrapped `BaseTool._run` surface; worked governed tool; A/B
    governance benchmark evidence; uncovered surfaces; bypass demonstration.
24. **LangGraph Integration** — sync StateGraph node coverage; occurrence-aware retries, loops,
    parallel branches, interrupts, resume; worked graph; uncovered surfaces.
25. **Adapter Conformance and Coverage** — conformance reports; the test obligations behind a
    "wrapped" label; framework version pinning and framework-adapter drift.
26. **External Policy Engines and Enforcement Providers** — projecting contracts to OPA/Cedar/
    platform PDPs; gateway/sandbox/mesh PEPs; what Tier 3 requires; telecom analogy #3
    (interworking). Status labels critical here: mostly [guidance]/[extension].
27. **MCP and Tool-Governance Boundaries** — MCP packages as untrusted inert input (package scan/
    radar/register [implemented]); contract-only protocol declarations; documentation-MCP pattern
    [guidance]; A2A declarations.

### Part VI — Engineering Governed Systems
28. **The Policy Authoring Workflow** — authoring lifecycle; review of semantic + generated
    diffs; usability and friction; policy testing before merge.
29. **CI/CD Integration** — reference CI; drift gates; lock verification in pipelines; evidence
    validation as a build step; release gating; SLSA/SSDF connections.
30. **Governing Software-Development Agents** — Case Study B (Forge) in depth: inspect/propose/
    test/PR allowed, merge/deploy/release/secrets/destructive gated; maker–checker; fail-closed.
31. **Multi-Agent Governance** — Case Study C (Ledger): planning/analysis/execution/approval/audit
    agents across zones; delegation limits; separation of duties; escalation; evidence chains.
32. **Enterprise Governance Hierarchies** — Case Study E (Charter): org → business unit → app →
    agent → mission policy; inheritance without silent weakening; workspace manifests
    [implemented] vs hierarchy engine [extension]. Telecom analogy #4.
33. **Operations, Observability, and Incident Response** — running governed systems; evidence
    stores; monitoring the governance layer itself; incident reconstruction; degraded modes.

### Part VII — Risk, Standards, and Adoption
34. **Threat Modeling Governed Agentic Systems** — assets incl. claims; attacker models; contract/
    composition/lock/approval/evidence/adapter threat trees; mitigations and residual risk.
35. **Mapping Controls to Standards** — NIST AI RMF, NIST SSDF, ISO/IEC 42001, 23894, 27001, EU AI
    Act, OWASP LLM/agentic, SLSA, zero trust; interpretive mappings, not compliance claims.
36. **Audit and Evidence Packages** — audit questions; the reconstruction chain; worked audit of a
    case-study decision; evidence preservation; auditor-facing packaging.
37. **Enterprise Adoption and Platform Strategy** — maturity ladder; organizational friction;
    build/buy/platform; hyperscaler-native enforcement points; multi-tenant isolation;
    procurement and claims. Telecom analogy #5.
38. **Limitations, Open Problems, and Research Directions** — the honest chapter: what Nornyx and
    the discipline do not solve; distributed truth; producer honesty; performance; semantics
    usability; research agenda.

### Part VIII — Capstone
39. **Capstone: Designing the Complete Northstar System** — full design integrating all five case
    studies; tier selection by consequence; claim register.
40. **Capstone: Implementation, Verification, and Assurance Review** — build + failure injection +
    audit reconstruction; assessment of the resulting claims.
41. **Lessons, Trade-offs, and Future Architecture** — synthesis; when NOT to deploy governance
    machinery; the road to authoritative enforcement.

### Appendices
A. Nornyx language syntax reference · B. CLI and API quick reference · C. Diagnostic-code guide ·
D. Schema catalogue · E. Example policy collection · F. Conformance checklist ·
G. Security-review checklist · H. Glossary · I. References · J. Repository-to-book traceability
matrix · K. Index. Plus: Instructor and Self-Study Guide (review answers, exercise guidance,
capstone rubric, learning paths).

## Case-study strategy

One fictional enterprise — **Northstar Services** — carries five continuing threads (bible in
`03_case_study_bible.md`): **A/Atlas** research assistant (intro Ch. 1; identity Ch. 5; policy
Ch. 7; enforcement/denial Ch. 10; evidence Ch. 11, 20; audit Ch. 36); **B/Forge** development
agent (Ch. 2, 9, 15, 29, 30); **C/Ledger** financial workflow (Ch. 6, 12, 31, 34); **D/Gateway**
framework comparison (Ch. 22–25, 14); **E/Charter** hierarchy (Ch. 8, 32, 37). All threads
converge in Part VIII.

## Chapter template (mandatory unless a section is genuinely inapplicable)

Opening scenario → Learning objectives → Prerequisites (chapter refs) → body with progressive
disclosure → worked example(s) → Nornyx-in-practice (status-labeled) → failure/bypass analysis →
design trade-offs → misconceptions box → summary → review questions (4–6) → exercises (2–3) →
further reading (citation keys). Length: 4,000–6,500 words per chapter (Part I chapters may run
shorter; capstone longer).

## Quality gates per chapter (Stage 7 pre-check)

Teaches a coherent concept; builds on stated prerequisites; Nornyx claims match fact packs with
paths; limitations explicit; examples consistent with case bible; figures necessary, numbered,
captioned, referenced in text; exercises answerable from the chapter; not a manual; general
knowledge vs Nornyx implementation clearly separated.
