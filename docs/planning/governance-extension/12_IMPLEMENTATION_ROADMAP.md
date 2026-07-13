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

Status: in progress.

- verify current implementation and green baseline;
- reconcile stale planning and ADR statuses;
- accept the bounded block-schema and fixed structural-check ADRs;
- establish the exact closure matrix and implementation sequence.

Acceptance: no implementation starts without an explicit owner for every new
schema and relational check.

## Stage B - Foundational Modules

Status: planned.

- `human_approval`;
- `evidence_integrity`;
- `separation_of_duties`;
- `exception_management`;
- bounded block-schema composition and fixed checks required by them.

Acceptance: modules are packaged, integrity-locked, deterministic, local-only,
monotonic, documented, and covered by unit/integration/adversarial tests.

## Stage C - Generalized Change Governance

Status: planned.

- `nornyx.change.v1` with additive `id`/`type` compatibility;
- `change_control` module;
- lifecycle, revision, approval, rollback, closure, exception, and separation
  checks;
- governed-package delegation to the shared change validator;
- explicitly approved golden migration only if unavoidable.

Acceptance: every existing governed-package example retains meaning and all
new lifecycle/staleness diagnostics fail closed.

## Stage D - Architecture Governance

Status: planned.

- `architecture_conformance` module;
- `architecture_governance` optional profile;
- declaration and evidence schemas;
- bounded report import only, with no external tool execution;
- starter, examples, docs, and revision/freshness tests.

Architecture Radar remains rejected unless separately justified by evidence.

## Stage E - GSA and Candidate Decisions

Status: planned.

Complete Governance Surface Analysis for Nornyx and for supply chain, data
protection, lifecycle, release, and incident response. Each candidate receives
one final ADR placement: module, profile-local control, external evidence
contract, existing-tool ownership, rejected, or not required.

## Stage F - Approved Later Modules

Status: blocked on Stage E by design.

Implement only candidates that prove reuse by at least two profiles, reconcile
duplicated existing semantics, close a high-priority control gap, or provide a
stable evidence contract required by an existing feature.

## Stage G - Profile Integration

Status: planned.

Map each of the 11 existing profiles and `architecture_governance` to only the
modules justified by its GSA matrix. Preserve one primary profile plus modules.

## Stage H - Full Hardening

Status: planned.

- stable CLI/API and diagnostics;
- malicious pack/schema/evidence/exception corpus;
- compatibility corpus and approved migration records;
- deterministic/permutation/resource tests;
- build, wheel install, documentation execution, and Linux symlink tests;
- public-boundary and repository-specific assurance.

## Stage I - Program Closure

Status: planned.

Produce reports 16-21, reconcile every roadmap item to an unambiguous final
status, prepare a human-reviewed release candidate without publishing it, and
run the independent audit in report 22. Completion requires an exact `GO`, no
mandatory roadmap remainder, and no unresolved review thread.

## Rollback and Review

Each stage is a logical commit or PR-sized group with its own tests. Reverting a
stage must restore the prior green state. Do not continue past an unresolved
Critical or High finding. Any core-language revision, compatibility break,
arbitrary-expression requirement, network/external execution requirement, or
evidence that cannot bind to a governed revision is a stop condition requiring
human review.
