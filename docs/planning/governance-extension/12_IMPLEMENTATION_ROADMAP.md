# 12 - Implementation Roadmap

Status: **historical implementation roadmap with residual remediation recorded
in the containing commit and externally verifiable final-head gates.**

## Audit Evidence History

- Audited base: `95952226999327458c6fea81cb32d82539bcae5b`.
- Original NO-GO candidate: `35ee69359599af7887f6b9b58ae0a4cd06a48d25`.
- Main remediation implementation anchor:
  `81899aaac5e54781dfe9c8002f557a874854c8b8`.
- Historical exact-head CI candidate:
  `3a0e840c3229dbf58959df1e3a161318bffd94ac`; this is not the final approved
  candidate.
- Historical hosted CI run: `29373272295`, conclusion `success`.
- Historical Windows evidence on the `81899aa`/`3a0e840` lineage:
  `913 passed, 45 skipped`.
- Historical Linux evidence bound to `3a0e840` and run `29373272295`:
  `958 passed, zero skipped`.
- Historical wheel evidence: `12 profiles`, `6 modules`,
  `network_attempts=[]`, `network_used=false`.
- A later independent audit of `3a0e840` returned historical `NO-GO` and
  reopened `AUD-011-R1`, `AUD-017-R1`, `AUD-021-R1`, and `PRMETA-001`.
- Residual path and network remediation is anchored at
  `1319613697b0e94d177ebe2c879f73107c366c7e`; documentation reconciliation is
  implemented in the commit containing this record, whose SHA is intentionally
  not embedded.
- External final-head verification must resolve the containing commit from Git
  and GitHub, run hosted CI on that exact head, and bind a fresh independent
  audit to the same head.
- Human authorization is not granted. PR #30 remains draft; merge, release,
  tagging, publication, and deployment remain unauthorized.

## Reconciled Status

The original PR 1 through PR 4 sequence shipped across Nornyx 1.5.0-1.5.2:
pack schemas, loader, registry, deterministic locks, composition, the closed
rule evaluator, approval normalization, profile migration, scanner hardening,
and symlink trust-root corrections are implemented. The old roadmap text that
described those components as future work is historical, not current state.

The authoritative baseline and gap table are in
`15_CURRENT_IMPLEMENTATION_INVENTORY.md`. Work continues in independently
testable stages; no stage permits a release, tag, publication, deployment, or
operational action.

## Stage A - Program Reconciliation

Status: implemented.

- verify current implementation and green baseline;
- reconcile stale planning and ADR statuses;
- accept the bounded block-schema and fixed structural-check ADRs;
- establish the exact closure matrix and implementation sequence.

Acceptance: no implementation starts without an explicit owner for every new
schema and relational check.

## Stage B - Foundational Modules

Status: implemented.

- `human_approval`;
- `evidence_integrity`;
- `separation_of_duties`;
- `exception_management`;
- bounded block-schema composition and fixed checks required by them.

Acceptance: modules are packaged, integrity-locked, deterministic, local-only,
monotonic, documented, and covered by unit/integration/adversarial tests.

## Stage C - Generalized Change Governance

Status: implemented.

- strict top-level `nornyx.change.v1` for explicitly selected change control;
- `change_control` module;
- lifecycle, revision, approval, rollback, closure, exception, and separation
  checks;
- exact governed-package 1.x compatibility projection at the package boundary;
- explicitly approved golden migration only if unavoidable.

Acceptance: every existing governed-package example retains meaning and all
new lifecycle/staleness diagnostics fail closed.

## Stage D - Architecture Governance

Status: implemented.

- `architecture_conformance` module;
- `architecture_governance` optional profile;
- declaration and evidence schemas;
- bounded report import only, with no external tool execution;
- starter, examples, docs, and revision/freshness tests.

Architecture Radar is `rejected_with_ADR` by ADR-0030 for this program. Any
re-entry is a separately approved future proposal with the evidence conditions
defined there.

## Stage E - GSA and Candidate Decisions

Status: implemented.

Complete Governance Surface Analysis for Nornyx and for supply chain, data
protection, lifecycle, release, and incident response. Each candidate receives
one final ADR placement: module, profile-local control, external evidence
contract, existing-tool ownership, rejected, or not required.

The completed matrices, dogfood analysis, priority tuples, and exact placement
statuses are in docs 17-18 and ADR-0031. GSA remains a documented method with
validated advisory templates; runtime schema and CLI tooling were not justified.

## Stage F - Approved Later Modules

Status: implemented with no additional module.

Implement only candidates that prove reuse by at least two profiles, reconcile
duplicated existing semantics, close a high-priority control gap, or provide a
stable evidence contract required by an existing feature.

No candidate passed that gate. Supply-chain controls remain in governed-package
scanning and external evidence integration; release control is superseded by
existing release tooling and shared modules; the other candidates are not
required after GSA. The catalog is frozen at six modules by ADR-0031.

## Stage G - Profile Integration

Status: implemented.

Map each of the 11 existing profiles and `architecture_governance` to only the
modules justified by its GSA matrix. Preserve one primary profile plus modules.

The 11 established profiles retain empty required-module lists to preserve
their starters and contracts. Doc 17 records explicit project-level module
recommendations; `architecture_governance` remains the sole profile with a
required module because it was introduced with that contract.

## Stage H - Full Hardening

Status: implemented.

- stable CLI/API and diagnostics;
- malicious pack/schema/evidence/exception corpus;
- compatibility corpus and approved migration records;
- deterministic/permutation/resource tests;
- build, wheel install, documentation execution, and Linux symlink tests;
- public-boundary and repository-specific assurance.

Reports 19-20 and the formal compatibility manifest record the results. The
historical `81899aa`/`3a0e840` lineage passed the Windows and Linux results
recorded above, and run `29373272295` passed exact-head checkout, candidate
diff, build, Twine, wheel, and example gates. The later audit reopened the three
AUD R1 items and PR metadata. Their implementation is recorded here without
transferring the historical run to the containing commit.

## Stage I - Program Closure

Status: residual remediation implemented; external final-head verification required.

Reports 19-22 and the candidate record distinguish historical commit-bound
evidence from external dynamic verification. The machine-readable remediation
ledger is the finding-level authority. No operational release action is
authorized.

## Rollback and Review

Each stage is a logical commit or PR-sized group with its own tests. Reverting a
stage must restore the prior green state. Do not continue past an unresolved
Critical or High finding. Any core-language revision, compatibility break,
arbitrary-expression requirement, network/external execution requirement, or
evidence that cannot bind to a governed revision is a stop condition requiring
human review.
