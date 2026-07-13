# Changelog

All notable changes to the Nornyx package are recorded here. The package
distribution version is independent of the Nornyx **language/schema** version
(still 1.0): a package patch can ship without changing the contract language.

## Unreleased

### Added
- Declarative governance runtime for local profile/module loading, deterministic
  monotonic composition, closed rule evaluation, approval normalization,
  timestamp-free locks, and exact v1-to-v0.3 projection with separate reports.
- Pack-aware `nornyx check`, explicit local profile initialization, and
  `profiles list`, `inspect`, `validate`, `resolve`, and `compatibility`
  subcommands. Discovery remains offline and data-only. A `project.profile`
  value that does not match any governance pack keeps passing `nornyx check`
  exactly as before (a `PACK_NOT_RESOLVED` warning is printed); explicit
  `project.modules` selections remain fail-closed.
- Every composed approval requirement carries the non-removable core denials
  (`ai_tool`, `execution_surface`). The prohibition is intrinsic to approval
  normalization: any document or pack declaring either as an eligible or
  required approver normalizes as invalid
  (`APPROVAL_CORE_DENIED_ACTOR_ELIGIBLE`) and `references_role` fails closed.
- Rule evaluation fails closed on malformed documents: structural errors while
  resolving a `when` condition — including operator/value type mismatches such
  as `equals` on a list or `contains` on a scalar — surface as diagnostics
  instead of silently skipping the rule. Ordinary missing-path non-matches
  remain silent. `all` conditions join across shared ancestor collections:
  predicates traversing the same collection at any depth must be satisfied by
  the same ancestor element. Pre-normalized approval payloads are not trusted
  blindly: an invalid resolution or a core-denied actor in the role lists
  makes `references_role` fail closed.
- Profile locks reject duplicate entry ids (`PACK_LOCK_DUPLICATE_ID`); packs
  are capped at 200 rules and compositions at 2000
  (`PACK_LIMIT_EXCEEDED`); duplicate item ids inside one pack are fatal
  (`PACK_DUPLICATE_ID`) — merge-by-id applies only across layers.
- `nornyx profiles resolve` discovers project-local `.nornyx/{profiles,modules}`
  packs, verifies an existing `nornyx.profiles.lock` (mismatch exits 2), and
  only rewrites the lock when `--lock` is passed. Composed `required_blocks`,
  evidence, and approval requirements remain advisory in this release: pack
  rules carry enforcement, and independent structural diagnosis of contract
  content is deliberately deferred for backward compatibility.
- Authoritative packaged v1 data for all 11 built-in profiles while preserving
  the existing starter golden hashes and legacy Python API shapes.
- Governed package hardening: built-in deterministic package scanner, normalized
  evidence records, claim-vs-evidence reports, risk scoring, scanner-backed
  manifest/lock metadata, and portal-ready JSON/Markdown reports.
- `nornyx package scan`: inventories package contents, hashes files, detects
  hooks, MCP configs, secret-like patterns, endpoints, dangerous commands,
  scripts, and claim mismatches without executing package payloads.
- External evidence adapter import framework with Syft-like SBOM and
  Gitleaks-like secret report parsers. External tools remain optional and are
  not executed by default.
- Governed-package validation rules for scanner-observed hooks, MCP configs,
  secret-like content, claim mismatches, required adapter failures, and critical
  external evidence.

### Notes
- Nornyx still does not claim packages are safe. It inventories, risk-surfaces,
  evidence-binds, hash-locks, and approval-gates untrusted packages.

## [1.4.0] - 2026-07-09

### Added
- **Governed Package Profile**: a standalone, product-neutral profile for
  declaring, validating, generating, locking, registering, and discovering inert
  governed package contracts.
- `nornyx package generate`: contract-first generation of inert governed package
  artifacts, including manifest, lock, provenance, safety, evidence, approval,
  and agent-assignment documentation.
- `nornyx package register`: artifact-first registration for existing artifact
  directories, with manifest, provenance, registration report, and hash lock.
- `nornyx package radar`: proposal-only discovery that scans a folder and
  suggests governable package candidates without executing, approving,
  installing, deploying, uploading, or copying secret-like values.
- Public-boundary policy documentation and a local scan helper for keeping
  public repository content product-neutral.

### Fixed
- Published root schemas now stay synchronized with bundled package schemas for
  governed package top-level contracts.
- Public-boundary local term files are ignored by the boundary scan itself while
  still contributing local-only scan terms.
- Radar suggested-contract output no longer collides with the radar report path.
- Registered existing packages re-check source artifact hashes during validation
  when the registered source directory is available.
- The governed package JSON schema is pinned to the Python validator contract in
  tests so shipped schema metadata cannot silently drift.

### Notes
- Generated governed packages remain inert by default. Nornyx does not execute,
  install, approve, deploy, store secrets, or operate runtime systems.
- The Nornyx **language/schema** version is unchanged (still 1.0); this is a
  package release.

## [1.3.0] - 2026-07-01

### Added
- **Policy `ref`** — a policy can reference a canonical definition instead of
  copying its rules: `ref: <path>#<PolicyName>`, resolved at load time from a
  local `.nyx` contract or a workspace manifest. The canonical rules live in one
  place, so there is nothing to drift; the ref compiles into inline `rules`, so
  the checker, generator, and drift gate see a normal policy. Fully backward
  compatible; the frozen v0.1 language surface is unchanged. Two bundled examples
  (`org_policies.nyx`, `governed_service.nyx`).

## [1.2.0] - 2026-06-29

### Added
- `nornyx --version`: top-level flag that prints the installed package version.
  Thanks @hass-nation (#7 → #13).
- `nornyx workspace-check --quiet`: print only the failing members on drift,
  staying silent on a clean pass — handy for CI logs. Thanks @hass-nation (#10).
- A third bundled example contract, `release_guardrails.nyx` (CI/release
  governance), shipped with the package and covered by the example checks.
  Thanks @hass-nation (#11).

### Changed
- Clearer error when a contract file does not exist: `check` now reports
  "contract file not found: <path>" instead of a generic read error.
  Thanks @hass-nation (#8).
- Documented `nornyx complete` (shell/editor completion) in the README.
  Thanks @hass-nation (#9).
- CI now runs the test suite on every push and pull request (new `ci.yml`);
  the manual-only `nornyx-safe-dev-quality.yml` is unchanged.

## [1.1.10] - 2026-06-29

### Changed
- Adoption polish (no code change): README badges (PyPI, Python, CI, license) and
  a top-line `pip install nornyx`; expanded PyPI project links (Documentation,
  Changelog, Case study).

## [1.1.9] - 2026-06-28

### Fixed
- `workspace-check --write` silently did nothing (1.1.7/1.1.8) on contracts whose
  policy list is a YAML block sequence at the key's own indent — which is exactly
  what `nornyx init` and `yaml.safe_dump` emit (`policies:` then `- name:` at
  column 0, and `deny:`/`- x` at the same indent). Block-boundary detection now
  treats `- ` items at the key indent as inside the block, and rule-item
  consumption handles same-indent sequence items. Found by a cold-start trial.

## [1.1.8] - 2026-06-28

### Added
- Workspace sync robustness: regression coverage for flow-style `rules: [..]`,
  `deny:`/`require:`-form members, and files with multiple policies (only the
  named policy is rewritten). `workspace-check` now nudges to `--write` when a
  drift is syncable, and `docs/USE_IN_YOUR_REPO.md` shows a scheduled sync job.

## [1.1.7] - 2026-06-28

### Added
- `nornyx workspace-check --write` (sync mode): propagates each canonical policy
  from the workspace manifest *into* every member contract, so the org policy is
  maintained in one place instead of hand-copied. The rewrite is surgical — it
  replaces only the matched policy's rule block and preserves comments and other
  blocks, keeping members self-contained. Members that don't declare the policy
  (or missing files) are left for a human, not invented.

## [1.1.6] - 2026-06-28

### Added
- `nornyx drift <contract> --out <dir>`: a **full-output** drift gate that
  compares every generated artifact by hash against a committed directory. The
  previous "diff `AGENTS.md`" guidance was blind to `policy.yaml` changes
  (`AGENTS.md` doesn't render policy rules), so a policy edit could pass a green
  gate. `nornyx drift` catches added, removed, and changed artifacts.
- `nornyx workspace-check --manifest nornyx.workspace.yaml`: cross-repo policy
  consistency. A workspace manifest declares canonical policies once and lists
  member contracts; the check fails if any member's named policy diverges from
  the org standard. Closes the gap where two repos could carry divergent copies
  of the "same" policy and each still pass its own gate.

### Changed
- `docs/USE_IN_YOUR_REPO.md` and README now recommend `nornyx drift` (whole-set)
  instead of diffing only `AGENTS.md`, and document the workspace check.

## [1.1.5] - 2026-06-27

### Fixed
- `nornyx schema --version 0.2|1.0` crashed for pip-installed users — the JSON
  schemas weren't shipped in the wheel and were resolved relative to the package
  parent. Schemas are now bundled in the package and resolved from there (with a
  repo-root fallback for source checkouts).

## [1.1.4] - 2026-06-27

### Added
- "Use it in your repo" onboarding: README section + `docs/USE_IN_YOUR_REPO.md`
  showing `nornyx init` -> edit -> generate -> place `AGENTS.md` -> a CI /
  pre-commit **drift check** (regenerate and diff) so artifacts can't drift.

### Changed
- `nornyx examples` now nudges toward the example the quickstart leads with.

## [1.1.3] - 2026-06-27

### Fixed
- First-run for pip users: example contracts are now shipped inside the package
  and a new `nornyx examples` command copies them into `./examples/`, so the
  README/quickstart `nornyx check examples/...` works after a plain
  `pip install nornyx` (previously the examples weren't in the wheel).

## [1.1.2] - 2026-06-27

First PyPI-publishable release (no code behavior change).

### Changed
- Adoption-grade README: value prop, install, 5-minute quickstart, contract
  example, and scope/safety.
- PyPI metadata in `pyproject.toml`: description, keywords, classifiers, and
  project URLs. `twine check` passes on the wheel and sdist.

## [1.1.1] - 2026-06-27

### Added
- Consolidated example contracts into this canonical repo so it is the single
  source of truth. All examples pass `nornyx check`.

## [1.1.0] - 2026-06-27

Reconciliation release that consolidates the language into a single canonical
repo as the source of truth.

### Added
- `generation_drift` feature: a generated-artifact drift gate
  (`nornyx/generation_drift.py`), a dev check script
  (`scripts/dev/check_generated_drift.py`), committed baselines under
  `tests/fixtures/generated_drift/`, and tests in `tests/test_generator_hardening.py`.

### Changed
- Generator now writes artifacts with LF newlines (`newline="\n"`) so generated
  output is byte-identical across platforms (Windows no longer emits CRLF).
- Drift baselines regenerated with the 1.0.1 parser fix, so they encode the
  corrected `on:` harness output instead of the previous `{true: ...}` bug.

## [1.0.1] - 2026-06-27

### Fixed
- Parser: `on`/`off`/`yes`/`no` are no longer coerced to YAML 1.1 booleans, so
  harness repair steps like `- on: test_failure` keep the `on` key instead of
  becoming `{True: ...}`. Implicit bool resolution is now restricted to
  `true`/`false`. (`NornyxSafeLoader`, with regression tests.)

## [1.0.0]
- v1.0.0 GitHub source release of the generalized agentic contract language.
