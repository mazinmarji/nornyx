# 10 — Security Threat Model (Pack and Module Framework)

Status: filesystem/lock remediations are implemented and mapped to executable
AUD-001/002/009/010/011/018 regressions; full-program remediation validation
remains in progress. Report 20 is historical and superseded.

Assets: contract integrity, composed-model integrity, approval semantics,
evidence requirements, generated artifacts, the safety boundary itself.
Adversaries: malicious pack author (local or org tier), compromised org share,
tampered install, careless author (accidental weakening).

## Threats and mitigations

| ID | Threat | Mitigation (normative requirement) | Test (doc 13) |
|---|---|---|---|
| T-01 | Malicious local pack weakens denials/approvals | Monotonic merge: no removal syntax exists; composer invariant re-asserts deny/evidence supersets (doc 06 §5); core checker rules not exceptable | adversarial merge tests |
| T-02 | Path traversal via pack path or `requires_modules` | Ids are identifiers, never paths; every unresolved explicit-path component is inspected from an independent trust root before real-path containment | traversal fixtures |
| T-03 | Symlink/reparse escape (contract, pack, governance directory, lock, evidence, report, or artifact) | Anchor-to-target `lstat` inspection rejects live/dangling links, junctions, reparse points, inaccessible components, and wrong types before resolution or enumeration | simulated Windows plus mandatory real Linux symlink fixtures |
| T-04 | YAML alias bombs / deep nesting / huge docs | 512 KB size cap pre-parse; alias-expansion and depth caps in loader; parse under try with stable error | abuse-case corpus |
| T-05 | Duplicate profile/module identity or namespace squat (`nornyx.builtin` / descendants from non-builtin tier) | One global cross-kind id/name namespace; exact reserved-root rejection; local callers cannot claim bundled tier; same-kind exact cross-tier shadowing only | registry, lock permutation, and wheel tests |
| T-06 | Dependency cycles | Topological sort with cycle gives fatal `PACK_DEPENDENCY_CYCLE` naming the cycle | cycle fixtures |
| T-07 | Compatibility downgrade (pack claims old core to skip checks) | `compatible_core` checked against the *running* core; rules always evaluated under current engine; no per-version rule-skipping semantics exist | version tests |
| T-08 | Rule-language injection (operator smuggling, regex, paths escaping doc) | Closed operator enum in JSON schema; restricted `matches_id` grammar (no regex); path grammar without parent/root escapes; unknown operator ⇒ load failure, never skip | schema + evaluator tests |
| T-09 | Arbitrary file read/write via pack content | Packs are data; only the engine reads files, only from resolved pack paths; starter renderer writes only to user-specified out path (existing `write_profile` discipline) | loader tests |
| T-10 | Template injection in starter fragments | No templating: fragments are literal data; substitution is engine-owned (project name into fixed fields) | injection-attempt fixtures |
| T-11 | Remote references / hidden network or device access | URI, UNC, extended/device namespace, DOS device, and remote schema refs are rejected lexically before any filesystem call; network/process APIs remain prohibited | no-probe lexical and offline-guarantee tests |
| T-12 | Profile-supplied executable code | Data-only format; safe loader (no Python tags); no entry points or plugin API; safety constants schema-required | module-security fixtures |
| T-13 | Approval bypass (pack marks approvals optional / adds `ai_tool` approver) | `denied_approver_types` core-injected and union-only; approval requirements accumulate-only | adversarial fixtures |
| T-14 | Evidence-requirement removal | Union-only evidence merging; composer invariant | adversarial fixtures |
| T-15 | Untrusted org tier | Org tier is opt-in configuration; provenance labels every element with source tier; lock hashes pin content; `profiles resolve` prints the trace | provenance tests |
| T-16 | Tampered pack after approval / stale, forged, or unsafe lock / version substitution | Bounded strict lock read plus schema/duplicate validation; selected identities checked before dictionaries; content hash + version + tier all must match; writes refuse links | lock abuse and permutation tests |
| T-17 | Ambiguous precedence | Single documented precedence; resolution trace output; same-tier ambiguity fatal | precedence tests |
| T-18 | Nondeterministic generation via packs | Deterministic merge order; fragments sorted; LF-canonical hashing; current-main canonical-LF and same-platform byte tests, then renderer byte-equality tests (lesson learned from the scanner-branch determinism defect) | golden tests |
| T-19 | Forged/stale governance evidence | Bounded schema, local artifact containment, SHA-256, exact subject revision, freshness, and dependency validation | foundational, architecture, release-evidence, and CLI tests |
| T-20 | Inspection CLI becomes execution surface | Commands are read-only; no lock writes; remote input rejected; subprocess/network APIs remain unused | governance CLI security tests |
| T-21 | Unicode/confusable identity | ASCII identifier grammar enforced by schemas | confusable-identity test |

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

The complete Stage H threat closure and residual-risk evidence is in
`20_SECURITY_ASSURANCE_REPORT.md`.
