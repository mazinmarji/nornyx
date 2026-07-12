# 10 — Security Threat Model (Pack and Module Framework)

Assets: contract integrity, composed-model integrity, approval semantics,
evidence requirements, generated artifacts, the safety boundary itself.
Adversaries: malicious pack author (local or org tier), compromised org share,
tampered install, careless author (accidental weakening).

## Threats and mitigations

| ID | Threat | Mitigation (normative requirement) | Test (doc 13) |
|---|---|---|---|
| T-01 | Malicious local pack weakens denials/approvals | Monotonic merge: no removal syntax exists; composer invariant re-asserts deny/evidence supersets (doc 06 §5); core checker rules not exceptable | adversarial merge tests |
| T-02 | Path traversal via pack path or `requires_modules` | Ids are identifiers, never paths; explicit paths canonicalized (`resolve()`) and must stay within source-tier root | traversal fixtures |
| T-03 | Symlink escape (pack file or `.nornyx/profiles` entry symlinked outside repo) | Reject symlinked pack files/dirs at load (`PACK_SYMLINK_REJECTED`) | symlink fixtures (skip on no-symlink Windows) |
| T-04 | YAML alias bombs / deep nesting / huge docs | 512 KB size cap pre-parse; alias-expansion and depth caps in loader; parse under try with stable error | abuse-case corpus |
| T-05 | Duplicate identity / namespace squat (`nornyx.builtin.*` from non-builtin tier) | Reserved-namespace rejection; same-tier duplicate id fatal; cross-tier shadowing reported in provenance and resolution trace | registry tests |
| T-06 | Dependency cycles | Topological sort with cycle ⇒ fatal `PACK_CYCLE` naming the cycle | cycle fixtures |
| T-07 | Compatibility downgrade (pack claims old core to skip checks) | `compatible_core` checked against the *running* core; rules always evaluated under current engine; no per-version rule-skipping semantics exist | version tests |
| T-08 | Rule-language injection (operator smuggling, regex, paths escaping doc) | Closed operator enum in JSON schema; restricted `matches_id` grammar (no regex); path grammar without parent/root escapes; unknown operator ⇒ load failure, never skip | schema + evaluator tests |
| T-09 | Arbitrary file read/write via pack content | Packs are data; only the engine reads files, only from resolved pack paths; starter renderer writes only to user-specified out path (existing `write_profile` discipline) | loader tests |
| T-10 | Template injection in starter fragments | No templating: fragments are literal data; substitution is engine-owned (project name into fixed fields) | injection-attempt fixtures |
| T-11 | Remote references / hidden network | No URL-bearing fields in schema; loader has no HTTP capability at all (no import of any network module — asserted by a static test that greps the packs/ package imports) | offline-guarantee test |
| T-12 | Profile-supplied executable code | Data-only format; safe loader (no python tags); no entry points (ADR-0024); no plugin API | — (structural) |
| T-13 | Approval bypass (pack marks approvals optional / adds `ai_tool` approver) | `denied_approver_types` core-injected and union-only; approval requirements accumulate-only | adversarial fixtures |
| T-14 | Evidence-requirement removal | Union-only evidence merging; composer invariant | adversarial fixtures |
| T-15 | Untrusted org tier | Org tier is opt-in configuration; provenance labels every element with source tier; lock hashes pin content; `profiles resolve` prints the trace | provenance tests |
| T-16 | Tampered pack after approval / stale lock / version substitution | Lock verification: content hash + version + tier all must match; mismatch fatal (doc 05 §7) | lock tests |
| T-17 | Ambiguous precedence | Single documented precedence; resolution trace output; same-tier ambiguity fatal | precedence tests |
| T-18 | Nondeterministic generation via packs | Deterministic merge order; fragments sorted; LF-canonical hashing; current-main canonical-LF and same-platform byte tests, then renderer byte-equality tests (lesson learned from the scanner-branch determinism defect) | golden tests |

## Blanket requirements (restating brief as normative)

Data-only packs; safe parsing; size/complexity limits; canonical path
validation; local-only loading by default (and in v1: always); explicit trust
and provenance; deterministic resolution; pack hashes; fail-closed conflicts;
stable diagnostic codes (`PACK_*`, `RULE_*`, `EXC_*` namespaces); no template
execution; no arbitrary expressions in rules.

## Residual risks (accepted, documented)

- A malicious *project-tier* pack committed to the repo is trusted like any
  other repo file — Nornyx cannot defend a repo against its own maintainers;
  mitigation is code review + lock diffs (visible in PRs).
- Prose fields (`purpose`, rule `message`, `migration_guidance`) could carry
  prompt-injection content aimed at AI assistants reading reports. Mitigation:
  render as inert text, never as instructions; documented in pack-authoring guide.
- Hash lock protects integrity, not intent — an approved-then-audited-bad pack
  needs human review; locks make swaps visible, not packs good.
