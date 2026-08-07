# Stage 1 — Editorial Diagnosis of the Attached Book

Source: *Governed Agentic Systems — Principles, Architecture, and Practice with Nornyx*,
Development Textbook Edition, repository basis Nornyx 1.11.0 / SPI 1.2 / snapshot `70d2b40ad792`,
dated 2026-08-03 (24 PDF pages, 14 chapters, 4 appendices).

## Overall assessment

The attached book is conceptually honest and unusually disciplined about claims for a draft of its
size. Its repository basis (`70d2b40`) matches the current HEAD, so its technical statements are
current, not stale. Its central weakness is not inaccuracy but **compression and coverage**: it is a
~55-page outline of a textbook, not a textbook. Nearly every section states a correct conclusion
without building the reasoning, examples, failure analysis, and practice that would let a reader
*reach* the conclusion. Secondary weaknesses: it assumes the general discipline rather than teaching
it, it under-uses worked examples and code, it has almost no comparative material, no standards
mapping, no bibliography, no index, and only one continuing case study.

## Specific findings

### 1. Sections that read like documentation rather than teaching
- Appendix A is a bare CLI command table with no worked session, no expected output, no failure
  cases — a manual page, not a laboratory.
- Chapter 3's "one source, many projections" presents the generator pipeline as description; there
  is no worked before/after showing an actual generated artifact or a drift failure.
- Chapter 9's coverage table (CrewAI/LangGraph surfaces) is accurate but delivered as a feature
  matrix; the underlying engineering reasoning (why sync-only, why the `_run` seam, what a wrapped
  surface costs) is absent.
- Chapter 13 reads as an internal documentation-program plan (portals, metadata fields, indexes)
  rather than instruction the reader can generalize.

### 2. Repeated content
- The proof boundary of supplied evidence ("conformance, not runtime truth") is restated in
  Chapters 2, 6, 8, 11, and 12 in nearly identical words, each time without deepening. A textbook
  should introduce it once formally, then *use* it with increasing sophistication.
- Tier definitions appear in Chapters 10, 11, and 14 with slight rewording.

### 3. Weak or missing conceptual foundations
- No treatment of why probabilistic systems need deterministic governance boundaries — the book's
  motivating premise is asserted, never developed.
- No comparison with adjacent disciplines (IAM, RBAC/ABAC, OPA/Cedar, API gateways, service meshes,
  guardrails, observability, DevSecOps). Readers cannot place the discipline.
- No formal treatment of policy evaluation semantics (decision domains, default-deny, conflict
  resolution, determinism as a property of the evaluator).
- Delegation vs. handoff is well stated (Ch. 7) but never formalized (no depth limits, no
  attenuation model, no confused-deputy discussion).
- No standards context at all: NIST AI RMF, SSDF, ISO/IEC 42001, EU AI Act, OWASP LLM/agentic
  guidance, SLSA, zero trust — all absent.

### 4. Unexplained terminology
- "Explicit mode", "SPI 1.2", "AuthorizerState", "profile pack", "M2-D", "runtime-events 1.1" are
  used before or without definition. "PDP/PEP" appears first in a chapter title context (Ch. 10)
  with a one-line gloss.

### 5. Insufficient examples
- Exactly one full `.nyx` listing (Listing 3.1, 20 lines) and one Python listing (Listing 9.1,
  6 lines) in the entire book. No generated artifact excerpts, no lock excerpt, no runtime-event
  excerpt, no diagnostic output, no negative test, no CI fragment — despite the repository
  containing real, quotable instances of all of these.

### 6. Missing transitions and difficulty cliffs
- Chapter 7 jumps from general capability/policy concepts (Ch. 5) straight into the full
  agentic-network record model (identities, memberships, zones, revocations) with no intermediate
  scaffolding. Chapter 8 (occurrence/attempt semantics) is the hardest material in the book and
  arrives with no worked event stream.
- Part IV mixes threat modeling, audit, documentation strategy, and adoption maturity — four
  different audiences — with no connective pedagogy.

### 7. Unsupported or under-supported claims
- "Northstar uses cooperative adapters during development and requires an external gateway for
  production" (Ch. 9, 14) — the external-gateway path is architecture guidance; the draft mostly
  labels this correctly (Ch. 10 callout) but Trace B in Ch. 14 narrates gateway enforcement and
  "trusted telemetry" as if operational; needs explicit "architectural extension, not Nornyx
  behavior" framing at point of use.
- Appendix A implies `nornyx drift --out .nornyx` style invocations are the whole CI story; the
  repository's reference CI is richer and should be shown from evidence.

### 8. Overly promotional language
- Minimal — the draft is commendably neutral. Residual issues: the closing "Engineering Standard"
  page is a slogan; "Nornyx Lens" boxes occasionally assert product virtues ("This limitation is
  not a defect in wording; it defines the product boundary") where a textbook should argue rather
  than pronounce.

### 9. Outdated repository facts
- None found: version axes (1.11.0 / language 1.0 / SPI 1.2 / runtime-events 1.1 / lock 1.0 /
  Python 3.10–3.13 / CrewAI 1.15.4 / LangGraph 1.2.2) match the repository at `70d2b40`. All were
  re-verified against source during the Stage 1 repository audit (see
  `10_repository_source_audit.md`).

### 10. Shallow explanations needing full development
- Canonicalization (Ch. 6): two paragraphs for a topic that needs a worked example of semantic
  vs. incidental difference and a discussion of canonicalizer versioning risk.
- Replay fingerprints (Ch. 8): rules stated, never exercised against a concrete event pair.
- Audit reconstruction (Ch. 12): the seven-step chain is excellent but abstract; needs a full
  worked audit with real artifacts.

### 11. Missing counterarguments and limitations
- No treatment of: policy usability and authoring friction, approval fatigue economics, evidence
  retention/PII tension, performance and scaling, multi-tenant isolation, distributed execution,
  remote agents, external connectors, or organizational adoption friction. (Several are named once
  in passing; none are examined.)
- No "when NOT to use a governance layer" discussion; no cost side of the trade-off ledger.

### 12. Diagrams
- Eleven figures exist but are low-information flow boxes; none carry a notation legend; several
  restate adjacent prose. Missing entirely: system-context diagram, policy-composition diagram,
  evidence lifecycle, sequence diagrams, tier comparison that encodes trust assumptions,
  bypass/threat diagrams, CI/CD governance flow, enterprise hierarchy, ecosystem positioning.

### 13. Structural gaps against the target book
- Only one case study (Northstar support/delivery). The target requires five continuing case
  studies including a research assistant, a development agent, a financial multi-agent workflow, a
  framework-integration comparison, and an enterprise hierarchy.
- No exercises with assessable outcomes beyond one-line laboratory prompts; no instructor
  material; no glossary beyond 14 terms; no references; no index; no traceability matrix.

## Disposition

The redesign **retains** from the draft: the claims-discipline framing (assertion layers, proof
boundaries), the tier model, the occurrence/attempt identity treatment, the delegation-vs-handoff
distinction, the audit-reconstruction chain, the failure-injection capstone idea, and the Northstar
fictional enterprise (expanded into a five-thread case-study universe). Everything else is
rebuilt: new part structure, new conceptual foundation (Parts I–III teach the discipline before
Nornyx), full worked examples from repository evidence, comparative and standards material, serious
limitations analysis, and complete editorial apparatus. Chapter-level dispositions are recorded in
the editorial change log (`12_editorial_change_log.md`).
