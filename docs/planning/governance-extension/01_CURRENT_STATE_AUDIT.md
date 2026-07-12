# 01 — Current State Audit (Repository Truth Report)

Status: planning document. Grounded in `main` @ `5fc1806` ("ci: publish only from
release events (#22)", v1.4.0). Verified by direct inspection, not by prior
conversation summaries. Where a claim could not be verified it is marked
**unverified**.

## 0. Branch-state caveat

`main` is `5fc1806`. A branch `codex/governed-package-scanner-hardening`
(`4f0fcea`, one commit ahead of main) contains the governed-package scanner
(`nornyx/package_scanner.py`, `package scan` / `package evidence import` CLI,
scan-backed validation rules). **It is not merged.** This plan targets `main`;
wherever the scanner branch is relevant (change governance, evidence records,
supply-chain module) the design notes both states so it composes cleanly after
merge.

## 1. Classification of observed behavior

### 1.1 Implemented behavior (code-enforced, on main)

| Area | Evidence |
|---|---|
| `.nyx` parsing (YAML-compatible, custom SafeLoader that preserves `on:` keys) | `nornyx/parser.py` (`NornyxSafeLoader`) |
| Policy `ref` resolution — offline, fail-closed, compiles refs to inline rules | `nornyx/parser.py:_resolve_policy_refs` (shipped 1.3.0, PR #15/#16) |
| Semantic checking of core blocks, graph/contract consistency | `nornyx/checker.py` (~850 lines, fully hard-coded rules) |
| Deterministic artifact generation (LF-forced writes, sorted hashes) | `nornyx/generator.py:_write`, `_artifact_hashes` |
| Drift gate comparing committed generated dir to fresh generate | `nornyx/repo_drift.py`, `nornyx drift` |
| Governed package profile: validate/generate/register/radar, hash locks | `nornyx/governed_package.py` (1.4.0) |
| Starter generation for 11 profile names | `nornyx/profiles.py:profile_document` (hard-coded template with conditionals) |
| Profile-pack catalog **in Python**, with self-validation | `nornyx/profiles.py:DOMAIN_PROFILE_PACKS`, `validate_profile_pack_catalog` |
| Versioned language schemas 0.1 / 0.2 / 1.0 + report schemas | `nornyx/schemas/*.json`, `nornyx/schema_model.py` |
| CLI: `check`, `generate`, `init --profile`, `profiles`, `drift`, `package *`, etc. | `nornyx/cli.py` |

### 1.2 Declarative metadata only (data exists, nothing evaluates it)

- `profiles/*.yaml` (11 files at repo root). **Verified: not loaded anywhere.**
  `grep` across `nornyx/`, `scripts/`, `tests/` finds no loader. They mirror
  `DOMAIN_PROFILE_PACKS`; `tests/test_cli_dx.py::test_v03_domain_profile_metadata_files_match_pack_contract`
  enforces mirror equality — i.e., **Python is authoritative, YAML is a synced copy**.
- `profiles/*.yaml` are **not shipped in the wheel**: `pyproject.toml`
  `[tool.setuptools.package-data]` includes only `nornyx/examples/*.nyx` and
  `nornyx/schemas/*.json`. An installed `nornyx` has no profile YAML at all.
- `extensions/{mcp,a2a,opentelemetry-genai}.yaml` — protocol metadata only.
  Repository-wide reference inspection found no consumer in `nornyx/`,
  `scripts/`, or `tests/`; one historical goal document merely names the path.
- Pack `validation_rules` are **prose strings** ("generated starter document
  passes nornyx check") — never parsed or evaluated. Purely descriptive.
- `PROFILE_COMPATIBILITY_MATRIX` — surfaced in the conformance report only.
  `nornyx check` never consults it; declaring two conflicting profiles in a
  contract is not detected at check time.

### 1.3 Hard-coded behavior (would require Python changes for any new domain)

- Profile names: `PROFILE_NAMES`, `BASE_PROFILE_NAMES`, `DOMAIN_PROFILE_NAMES`
  constants; CLI `init --profile` choices derive from them.
- Starter content: one ~150-line Python-built document with `if profile in {...}`
  branches (`profiles.py:376–531`).
- All checker rules: `checker.py` — block names, required fields, graph
  relation vocabulary are Python literals.
- Pack catalog: `DOMAIN_PROFILE_PACKS` dict.
- Pack stability/compat metadata: `PROFILE_STABILITY`, `PROFILE_COMPATIBILITY_MATRIX`.
- Governed-package validation: `governed_package.py:validate_governed_package`.

### 1.4 Advisory behavior

- Conformance report (`profile_conformance_report`) — reports issues, gates nothing.
- Radar (`package radar`) — proposal-only, explicitly `proposal_only: true`.
- Compatibility matrix — advisory strings ("requires_review_with").

### 1.5 Planned/documented but not implemented

- `docs/02_ARCHITECTURE.md` "v1.0 architecture" shows an AST → semantic analyzer
  → harness runtime → connector adapters pipeline. What exists is the v0.1
  pipeline (parser → checker → generator) plus report/planning modules. The
  runtime stages are **plans, not code** (harness_runtime.py plans manifests, it
  does not execute).
- `docs/05_SECURITY_MODEL.md` "Required future checks" — explicitly future.
- `docs/03_ROADMAP_TO_v1_AND_BEYOND.md` — roadmap language.

### 1.6 Stale or contradictory documentation

| Item | Contradiction | Recommended resolution |
|---|---|---|
| `docs/40_NORNYX_DOMAIN_PROFILES_v0_3.md` says packs are "documented in `schemas/domain_profile_pack.schema.json`" and YAML files exist | Readers reasonably infer YAML packs are consumed; they are not. Dual source of truth. | This plan (PR 2/PR 4) makes packs authoritative and Python a loader. Document the interim honestly. |
| `docs/02_ARCHITECTURE.md` v1.0 pipeline | Describes runtime stages that do not exist and are core non-goals elsewhere (no execution) | Amend doc to mark the runtime stages as historical aspiration superseded by the "contract/checker/generator/governance layer, not a runtime" identity. |
| Starter docs write goal scope `profiles/<name>.yaml` into generated contracts (`profiles.py:513`) | Points users at repo-root files that don't exist in installed distributions | Fix in PR 4 when packs move into the package. |
| `README`/docs `nornyx profiles` "List built-in Nornyx profiles" prints bare names only | Fine, but docs 43 imply richer conformance surface; no `profiles inspect` exists | Addressed by CLI design (doc 11). |

### 1.7 Version inconsistencies

- `domain_profile_pack.schema.json` pins `version: const "v0.3"` and
  `core_surface: const "v0.2"` — the schema **cannot describe any future pack
  version** without a breaking edit. Language schemas are at 1.0; packs frozen
  at v0.3 referencing a v0.2 core surface. This is the single largest schema
  blocker for a declarative system (see doc 05 / ADR-0026).
- Package distribution version (1.4.0) is deliberately independent of language
  version (1.0) — documented in CHANGELOG; not a defect, but the pack spec must
  declare compatibility against the **language/core surface**, not the package version.

### 1.8 Architectural duplication

1. **Pack data duplicated**: `DOMAIN_PROFILE_PACKS` (Python) ↔ `profiles/*.yaml`
   (mirrors) — with a test whose only job is keeping the duplication in sync.
2. **Change semantics duplicated in embryo**: `governed_package.changes`
   (`{id, type, expected_artifacts}`) vs. goals/approval semantics in core
   contracts. Not yet incompatible, but two places to grow a "change" concept
   (doc 07 reconciles).
3. **Safety non-goals duplicated**: `PROFILE_NON_GOALS` (profiles.py),
   `SAFE_BOUNDARY` (governed_package.py), prose non-goals in docs 40/47.
   Three hand-maintained lists expressing one boundary.
4. **Hash/write utilities duplicated** across `generator.py`,
   `governed_package.py` (and `package_scanner.py` on the pending branch).

## 2. Answers to the brief's explicit question

**"Are profile YAML files loaded as the runtime source of truth?" — No.**
Verified three ways: (a) no import/loader references them; (b) the sync test
treats Python as the reference and YAML as the copy; (c) the wheel does not
contain them, yet installed `nornyx init --profile ai_coding` works — proving
the YAML files cannot be on the runtime path.

## 3. Existing assets the design must build on (not replace)

- Policy `ref` (`<path>#<Name>`) — the proven, shipped pattern for offline
  declarative reuse with fail-closed errors. The module/profile reference
  mechanism should feel like this, not like a new invention.
- Deterministic generation + drift gate — composition output must round-trip
  through the same discipline (byte-stable, hashable, drift-checkable).
- Governed package locks (`package_lock.json`) — precedent for pack integrity
  hashes (doc 05 §7).
- `validate_profile_pack_catalog` — the seed of a pack validator; its checks
  (safety non-goals present, core concepts not exceeded, required blocks
  minimum) become schema + monotonicity rules in the new system.

## 4. Inventory of public surface that must not break

- CLI: `nornyx init --profile <name> [--name] [--out] [--force]`,
  `nornyx profiles` (prints 11 names, exit 0), `nornyx check`, `nornyx generate`,
  `nornyx drift`, `nornyx package {generate,validate,register,radar}`.
- Python API (imported by tests, presumed by users): `PROFILE_NAMES`,
  `write_profile`, `profile_document`, `profile_pack`, `profile_pack_catalog`,
  `profile_compatibility_matrix`, `validate_profile_pack_catalog`,
  `validate_profile_conformance`, `profile_conformance_report`.
- File formats: existing `.nyx` files (0.1/0.2/1.0), `profiles/*.yaml` v0.3
  shape, generated starter output. Before PR 1, `test_cli_dx.py` checked starter
  validity but did not preserve exact output; PR 1 adds current-main goldens for
  all 11 public names.

## 5. PR 1 repository-grounded corrections

- `write_profile()` uses default text newline translation. Current-main starter
  bytes are CRLF on Windows and LF on POSIX; cross-platform byte identity was
  not previously true. PR 1 records exact and canonical-LF hashes and permits
  only that normalization.
- Ordinary approvals are open named mappings (`name`, usually `required_for`).
  Governed-package gates use `id`, `required_evidence`, and
  `eligible_approver_roles`; Python also recognizes `approver_roles`,
  `approvers`, and `eligible_approvers` aliases. Contract references, goal
  prose, and boolean approval-required flags are separate legacy shapes.
- The scanner-hardening branch adds evidence/adapter/approval requirements but
  does not modify profile generation or `governed_package.changes`.
- Root and bundled v0.3 profile schemas are identical and strict; their
  `additionalProperties: false` rule prohibits embedding v1 projection
  provenance inside a legacy object.

Cross-references: problem framing → doc 02; target architecture → doc 03;
pack spec → doc 05; migration of every item in §1.3 → doc 11.
