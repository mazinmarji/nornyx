# 12 — Implementation Roadmap

Sequencing decision: PR 1 may proceed against main. The locally available
scanner-hardening branch does not change profile generation or the existing
`changes` shape. It must merge before the future Change Governance integration
PR so approval/evidence/schema reconciliation targets a settled governed-
package surface. See `appendix_SCANNER_INTEGRATION_DECISION.md`. No branch is
merged by PR 1. The CLI UX is spread across later PRs 2–3.

Common to every PR: CI green, full existing suite passes, no commits to
`main` without review, no version bumps except at release PRs, CHANGELOG entry,
rollback = revert the single PR (each is self-contained).

---

## PR 1 — Architecture decisions, schemas, and test foundations

- **Objective**: finalize docs and ADRs; close F-01 through F-04; add draft
  profile, module, approval-normalization, and timestamp-free lock schemas;
  capture all 11 current-main starter baselines; add schema/specification
  fixtures and tests.
- **Files**: planning docs and appendices, repository ADRs, root and bundled
  draft schemas, golden fixtures, specification fixtures/tests, and a guarded
  baseline-capture script; `docs/40` and `docs/02` truth corrections.
- **Tests**: JSON-Schema meta-validation, root/bundled copy synchronization,
  valid/invalid v0.3 and v1 fixtures, projection, collection semantics,
  approval normalization, module safety, and deterministic starter goldens.
- **Non-goals**: loader/registry code, runtime composition or rule evaluation,
  profile migration, new profiles/modules, or stable core changes.
- **Acceptance**: F-01 through F-04 closed with evidence and tests; audit
  conditions F-05/F-06/F-10/F-11/F-12/F-13 incorporated; full validation green
  or any environment artifact explicitly blocks readiness. **Rollback**:
  revert the specification/test-foundation PR.

## PR 2 — Declarative profile/module loader and registry (built-ins only)

- **Objective**: `nornyx/packs/{loader,registry,lock}.py`; built-in packs
  authored in `nornyx/packs_data/` for the 6 domain profiles; `profiles.py`
  API re-backed by loaded packs; constants preserved (doc 11 §2).
- **CLI**: `nornyx profiles list` (alias of existing `profiles`, adds `--json`),
  `nornyx profiles inspect <name> [--json]`, `nornyx profiles validate <path>`.
- **Security**: loader hardening T-02..T-05, T-09, T-11 (doc 10).
- **Tests**: consume the golden starter baselines captured in PR 1; loader
  abuse corpus; registry precedence with explicit path + `.nornyx/profiles/`.
- **Backward compat**: `nornyx profiles` unchanged; `init` unchanged.
- **Non-goals**: composition, rules, org tier. **Rollback**: revert; constants
  return to dicts.

## PR 3 — Composition engine and constrained rule evaluator

- **Objective**: `nornyx/packs/{compose,rules}.py`; governance modules;
  the 5 MVP module packs (doc 03) authored; `nornyx check` runs composed rules
  when a contract selects a profile/modules; org tier + `profiles resolve
  [--lock]`, `profiles compatibility <p...>`; exceptions block semantics.
- **Schemas**: rule-language portion of pack schema finalized (draft → active).
- **Security**: T-01, T-06..T-08, T-13..T-18 tests.
- **Tests**: deterministic merge (property-based order-invariance where inputs
  are permuted), monotonicity adversarial suite, exception expiry, golden
  resolution traces.
- **Backward compat**: contracts without packs behave identically (explicit
  regression test).
- **Non-goals**: migrating base profiles' starter internals. **Rollback**:
  compose path is behind "contract declares profile/modules AND packs
  resolvable"; revert restores advisory-only.

## PR 4 — Migration of built-in profiles (single source of truth)

- **Objective**: all 11 profiles authoritative as packs; `profile_document`
  rebuilt on fragment renderer; repo-root `profiles/*.yaml` become generated
  exports or removed; packaging gains `packs_data`; deprecation warning on
  dict access (doc 11 §3).
- **Tests**: doc 11 §6 in full.
- **Acceptance**: zero Python profile-content literals remain except the
  renderer skeleton; `git grep DOMAIN_PROFILE_PACKS` shows only the
  compatibility accessor.
- **Rollback**: revert to PR 3 state (packs still load; Python dicts return).

## PR 5 — `change_control` module + governed-package reconciliation

- **Objective**: doc 07 in full; `nornyx.change.v1` block schema; governed
  package profile requires the module; `governed_package.py` delegates
  change-shape validation.
- **Depends**: PR 0 (scanner branch settled), PR 3.
- **Tests**: every existing governed-package example unchanged; new
  change-lifecycle rule fixtures; approval-staleness structural check.
- **Rollback**: module is opt-in; revert detaches it.

## PR 6 — `architecture_governance` profile

- **Objective**: doc 08; `architecture_conformance` module;
  `nornyx.architecture_evidence.v1` schema + importer (report-parsing only,
  scanner-branch adapter pattern); examples + starter.
- **Tests**: evidence revision binding, stale-evidence detection, golden starter.
- **Non-goals**: radar, any code analysis. **Rollback**: profile is opt-in.

## PR 7 — Governance Surface Analysis framework

- **Objective**: doc 09 method as `docs/`; GSA applied to Nornyx itself;
  `nornyx.gsa_report.v1` schema **only if** the dogfood exercise shows tooling
  value — otherwise explicitly record "method only, no tooling" (pre-committed
  decision gate against tool sprawl).
- **Rollback**: docs.

## PR 8 — Hardening and release prep

- **Objective**: full doc 13 matrix green (incl. cross-platform, oversized,
  unicode, adversarial corpus), docs/40+02 rewritten to describe reality,
  migration guide, pack-authoring guide, CHANGELOG, release-readiness report;
  independent re-audit against doc 14 conditions.
- **Acceptance**: doc 14 conditions all closed; release decision (minor bump)
  made by a human, per invariant.
