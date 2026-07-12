# 14 — Final Independent Architecture Audit

Role: independent, adversarial architecture review board. The design (docs
01–13 + appendix) is examined against Nornyx's declared identity
(contract/checker/generator/governance layer, not a runtime), stable-core
boundaries, governed-package semantics, and the brief's invariants. The board
did not accept the designer's claims at face value; every finding cites the
design text or repository evidence.

## PR 1 closure review

The findings below are preserved as the pre-implementation audit record. PR 1
closes its four blocking findings as follows:

| Finding | Resolution | Evidence and tests | Residual risk |
|---|---|---|---|
| F-01 | Closed | 11 exact current-main goldens, exact and canonical-LF hashes, deterministic double-run tests, guarded approval procedure | Existing writer is platform-newline dependent; only CRLF/LF normalization is allowed until a later approved generator fix |
| F-02 | Closed | Normative existential/universal semantics, prefix binding, edge-case matrix, schema rejection of invalid operators/paths | Evaluator implementation must reuse these fixture ids and may expose implementation defects |
| F-03 | Closed | Normalized approval schema, repository field table, loss-preserving fixtures for all current and legacy shapes | Open ordinary mappings may reveal new role-bearing fields; unknown role fields fail until reviewed |
| F-04 | Closed | Frozen v0.3 schema, separate v1 schema, exact projection fixture, out-of-band loss report, must-preserve failure fixture | Future API implementation must preserve the exact output/report boundary |

F-05 is resolved by parse-then-canonicalize JSON hashing with exact serializer
parameters in doc 05. F-06 is resolved by requiring a lock for every org-tier
resolution. F-09 is resolved by the scanner integration appendix: PR 1 may
proceed independently, while scanner hardening must merge before Change
Governance integration. F-10 through F-13 are incorporated in composition,
resource-limit, lock-schema, and identity rules. F-07 remains a standing module
freeze after PR 6. F-08 is resolved in favor of removing root mirrors when
built-ins migrate.

PR 1 readiness is determined only after the full validation matrix passes. No
runtime loader, composition, migration, or new profile is implied by this
closure review.

## Original findings

| ID | Sev | Component | Finding / evidence | Failure scenario | Required correction | Blocks? |
|---|---|---|---|---|---|---|
| F-01 | High | Migration (doc 11 §2) | "Byte-identical starter output" is asserted, not demonstrated. Today's starters are built imperatively (`profiles.py:376–531`, dict-order-dependent YAML dump); fragment reassembly will almost certainly reorder keys/blocks. | PR 4 lands with "close enough" diffs, golden tests get regenerated to match the new output, and the compatibility guarantee silently becomes fiction. | Capture golden baselines from *current main* before any refactor (PR 2 task). If byte-equality proves unattainable, the divergence must be enumerated in CHANGELOG and approved explicitly — pre-commit to this decision procedure now. | Blocks PR 4 acceptance |
| F-02 | High | Rule language (doc 05 §5) | `[]` path traversal has **no defined quantifier**. `when: changes[].risk_tier equals high` — any element or all elements? Same ambiguity in `require`. | Author intends "every high-risk change needs approval"; engine implements "if any change is high-risk, require approvals somewhere" — rule passes when it should fail. Silent governance weakening, the worst failure class. | Specify before PR 3: `when` conditions match **existentially** (any element), `require` requirements bind **universally over the elements selected by `when`'s path prefix** — and add per-element diagnostics. Encode in schema `$comment` + evaluator tests for both quantifiers. | Blocks PR 3 |
| F-03 | High | Rule operators (doc 05 §5.2) | `references_role` is underspecified against reality: approvals shapes differ (`approvals[].name` + `required_for` in starters; `eligible_approver_roles`/`approver_roles`/`approvers`/`eligible_approvers` in governed packages — see `APPROVER_FIELDS`, governed_package.py:53). | The same rule means different things under different profiles; or trivially never matches, giving false confidence. | Define a normalized role-resolution table (which fields, which blocks) as part of the operator spec; reuse `APPROVER_FIELDS` as the seed; conformance-test against both shapes. | Blocks PR 3 |
| F-04 | High | Compat API (doc 11 §2) | `profile_pack()` promises a v0.3-shaped projection from v1 packs, but v1 drops const fields (`version: v0.3`, `core_surface: v0.2`) that `validate_profile_pack_catalog` and `test_cli_dx` assert verbatim. Lossy projection + strict legacy validator = contradiction. | PR 2 either breaks the public validator or fakes constants ("v0.3") on packs that are not v0.3 — misrepresenting provenance in a governance tool. | Decide now: projection emits literal legacy constants **and** a `projected_from: nornyx.profile_pack.v1@<ver>` marker field; legacy validator tolerates the extra key (verify `additionalProperties` impact — the v0.3 schema sets `additionalProperties: false`, so the marker must live outside schema-validated output or the projection must be exact). Resolve the exact mechanism in PR 1, with tests defined before code. | Blocks PR 2 |
| F-05 | Medium | Integrity hash (doc 05 §7, §1) | Canonical form for `content_hash` is specified for encoding (UTF-8/LF) but not for *what is hashed* ("body excluding integrity block") — textual excision is brittle (comments, ordering). | Two implementations compute different hashes for the same pack; locks break spuriously; users learn to ignore lock failures. | Define: hash = SHA-256 over `json.dumps(parsed_pack_minus_integrity, sort_keys=True, ensure_ascii=False)` — parse-then-canonicalize, never text surgery. Matches existing `stable_evidence_id` practice on the scanner branch. Specify in PR 1. | Blocks PR 2 |
| F-06 | Medium | Org tier (doc 05 §6) | Org directory comes from an env var — a mutable, unaudited trust root. Lock is only a warning when absent. | Attacker with env control (CI config PR) points `NORNYX_ORG_PROFILES` at a hostile dir; no lock ⇒ only a warning; composed governance silently changes. | When any pack resolves from the org tier, missing lock escalates to **error** (fail-closed per invariant). Env-var tier must also be printed in every `resolve`/`check` provenance output. | Blocks PR 3 |
| F-07 | Medium | Scope control (doc 03) | 5 MVP modules + change_control + architecture_conformance = 7 modules before any external author exists. The brief's own risk list names "governance-module proliferation". | Modules become the new profiles.py — a growing pile only maintainers touch, each with rules nobody composes twice. | Freeze the module namespace after PR 6 until at least one non-builtin profile pack exists in the wild; record as a standing condition in the roadmap. | No |
| F-08 | Medium | Mirrors (doc 11 §1) | "Generated exports or removed" hedges. Generated exports recreate the exact dual-source drift this project exists to kill, minus one test. | `profiles/*.yaml` drift returns; docs link to stale exports. | Decide **removal** in PR 4; keep `nornyx profiles inspect --json > file` as the export path. Only reverse with an identified concrete consumer. | No |
| F-09 | Medium | Dependency risk (doc 12 PR 0) | Plan depends on an unmerged external branch (`codex/governed-package-scanner-hardening`) for adapter patterns and settled package surface; that branch had known defect history (determinism, MCP regex) per session evidence. | PR 5/6 build against a moving or abandoned branch; change reconciliation done twice. | PR 0 is a *decision*, not necessarily a merge: merge it, or explicitly declare PR 5/6 target the pre-scanner surface. Decision must be recorded before PR 3 completes (not PR 5 — module block schemas reference evidence shapes). | Blocks PR 5, PR 6 |
| F-10 | Low | Override mechanism (doc 06 §4) | `overridable: [field...]` is a small permission language; growth pressure is predictable (nested fields, wildcards). | Merge semantics complexity creeps until unauditable. | Cap in spec: scalar fields only, inside `defaults` only, no wildcards; any extension requires an ADR. | No |
| F-11 | Low | Resource limits (doc 05 §8) | Caps exist for pack size/depth but not for rule count or composed-model size. | 10k-rule pack makes `check` effectively hang — availability, not integrity, but still a DoS on the governance path. | Add caps: ≤200 rules/pack, ≤2000 rules composed, evaluator step budget; stable `PACK_LIMIT_EXCEEDED`. | No |
| F-12 | Low | Determinism claim (doc 13) | Lock file asserted timestamp-free "by design" — but doc 05 §7 lock example has no `generated_at`, while every existing Nornyx lock (`package_lock.json`) includes one. Inconsistent precedent may cause an implementer to add it back. | Locks non-reproducible; repeat of the scanner-branch defect. | State explicitly in the lock schema: no time fields, and add the double-run byte-equality test to the schema's acceptance criteria. | No |
| F-13 | Low | Identity (doc 04) | Reverse-DNS ids are unvalidated free text beyond the builtin-namespace check. | Confusable ids (`org.acme.arch-governance` vs `org.acme.arch_governance`) in one org. | Constrain id grammar in schema: lowercase, `[a-z0-9_.]`, segments dot-separated; document. | No |

## Verdict against the brief's risk list

- General-purpose policy language: **contained** (closed operators, one nesting
  level, no expressions) — but F-02 shows the constrained language can still be
  *semantically* dangerous when underspecified. Condition C2 addresses it.
- Plugin execution platform: **avoided** structurally (data-only, no entry
  points, no templates). T-11/T-12 give static enforcement.
- Duplicating specialist tools: **avoided** — evidence-based architecture
  governance, radar deferred.
- Profile fragmentation: partially addressed (single-profile model); module
  proliferation is the live risk (F-07).
- Inconsistent change models: addressed by ADR-0021/doc 07 single-schema
  approach, conditional on F-09.
- Declarative purity, determinism, auditability, evidence/approval integrity:
  design is sound *as specified*; findings are about specification gaps, not
  wrong architecture.

## Original decision

**GO WITH CONDITIONS**

Conditions (all must close before the named PR merges):

- **C1 (before PR 2)**: Resolve F-04 (legacy projection mechanism, exact tests
  first) and F-05 (parse-then-canonicalize hash).
- **C2 (before PR 3)**: Resolve F-02 (quantifier semantics, with adversarial
  tests for both readings) and F-03 (role-resolution table) and F-06 (org tier
  ⇒ lock required).
- **C3 (before PR 3 completes)**: F-09 decision on the scanner branch recorded.
- **C4 (before PR 4)**: F-01 baseline-first procedure executed; F-08 mirror
  removal decided.
- **C5 (standing)**: F-07 module freeze after PR 6; F-10 override cap; F-11
  limits; F-12 lock schema statement; F-13 id grammar — folded into PR 1 spec
  text (cheap now, expensive later).

## Residual risks (accepted)

Project-tier packs are repo-trusted (mitigation: lock diffs in code review);
prose fields as prompt-injection carriers (render-inert guidance); hash locks
prove integrity, not intent.

## Deferred risks

Multi-profile composition pressure (registry keeps plural internally);
entry-point discovery demand from packaged-profile vendors; rule-language
operator growth (ADR-gated); architecture radar heuristics.

## Rejected alternatives worth revisiting

Profile inheritance (`extends:`) — rejected for diamond ambiguity; revisit if
fragment duplication across the 11 built-ins becomes measurably painful.
Python entry points — revisit only with a concrete multi-distribution use case.
Architecture Radar — revisit post-PR 6 with real evidence corpora.

## MVP scope

PRs 1–4 (spec, loader/registry, composition/rules, migration). This alone
delivers the headline: new domains without Python changes, single source of
truth, org distribution, locks.

**Must not enter MVP**: network anything; entry points; multi-profile
composition; overlays; architecture radar; GSA tooling; the six deferred
modules; any rule operator beyond the closed set; `governance analyze`.

## Recommended first implementation PR

PR 1 exactly as scoped in doc 12, with conditions C1/C2/C5 spec text folded in
before it is opened. It is documentation + draft schemas only, independently
reviewable, and forces the contested semantics (quantifiers, projection,
hashing) to be settled where they are cheapest — on paper.
