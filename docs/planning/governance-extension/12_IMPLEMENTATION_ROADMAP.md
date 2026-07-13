# 12 - Implementation Roadmap

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

- `nornyx.change.v1` with additive `id`/`type` compatibility;
- `change_control` module;
- lifecycle, revision, approval, rollback, closure, exception, and separation
  checks;
- governed-package delegation to the shared change validator;
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
final expanded suite passes 532 tests with 12 platform skips on Windows; Linux
CI passes all 544 tests, including real symlink cases. Ruff, public-boundary,
key examples, source/sdist/wheel build, Twine checks, and an isolated
no-network installed-wheel probe pass. Setuptools license metadata emits a
nonblocking deprecation warning with a 2027 deadline.

## Stage I - Program Closure

Status: implemented; corrected candidate verified and awaiting human review.

Reports 16-22 reconcile every roadmap item to an unambiguous final status. The
release candidate was prepared without publication and no mandatory roadmap
remainder exists. Report 22 records the superseding PR #30 review, all four
corrections, fresh Linux evidence, and a new exact `GO` audit.
The approval of candidate `2189bb3` was superseded by the later PR #30
blocking review. Corrected implementation commit `5417b1a` has fresh Linux
evidence and independent audit; human approval of that corrected candidate is
not yet recorded. No operational release action is authorized.

## Rollback and Review

Each stage is a logical commit or PR-sized group with its own tests. Reverting a
stage must restore the prior green state. Do not continue past an unresolved
Critical or High finding. Any core-language revision, compatibility break,
arbitrary-expression requirement, network/external execution requirement, or
evidence that cannot bind to a governed revision is a stop condition requiring
human review.
