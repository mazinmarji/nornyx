# Changelog

All notable changes to the Nornyx package are recorded here. The package
distribution version is independent of the Nornyx **language/schema** version
(still 1.0): a package patch can ship without changing the contract language.

## [1.6.2] - 2026-07-17

### Added
- AN-001 adds the optional v1-only `agentic_network` profile and the bounded
  `agentic_network_governance` module. The surface is data-only and local-only:
  it validates static identities, capabilities, memberships, trust zones,
  gates, protocol contracts, revocations, evidence, and human approval without
  opening connections or executing agents, tools, commands, or frameworks.
- Proposed additive compatibility records are bound by the markers
  `migration:profiles-agentic-network-v1`,
  `migration:modules-agentic-network-governance-v1`, and
  `migration:agentic-network-starter-v1`. These records document the authorized
  remediation candidate; compatibility acceptance, merge, release, runtime,
  and autonomous approval remain outstanding.

### Fixed
- The release workflow test job now checks out full history so the AUD-022
  candidate-diff regression test can resolve the audited base commit; the
  shallow checkout in the v1.6.1 release run made
  `git diff --check <base>...HEAD` an invalid range expression. The `v1.6.1`
  GitHub release predates this fix and was never published to PyPI; PyPI
  publication first occurs at 1.6.2.

## [1.6.1] - 2026-07-16

### Fixed
- The release workflow test job now invokes `python -m pytest -q` so the
  repository-root `scripts` helper modules imported by the wheel-guard and
  compatibility tests are resolvable during release validation. The `v1.6.0`
  GitHub release predates this fix and was never published to PyPI; PyPI
  publication first occurs at 1.6.1.

## [1.6.0] - 2026-07-16

### Audit remediation
- The independent audit of candidate
  `35ee69359599af7887f6b9b58ae0a4cd06a48d25` returned `NO-GO` with
  AUD-001 through AUD-022. Earlier compatibility, security, closure, and
  release-candidate claims are superseded while remediation is in progress.
  The PR remains draft and no merge or release action is authorized.
- Stage 2 closes the implementation gaps for AUD-001, AUD-002, AUD-009,
  AUD-010, AUD-011, and AUD-018 pending final cross-platform validation:
  anchor-derived unresolved-component inspection rejects links/reparse points
  before discovery, profile/module identity is globally collision-safe, locks
  are bounded and strict, remote/device paths are rejected lexically, and the
  exact plus descendant built-in namespace is reserved.
- The same filesystem invariant now protects adjacent workspace member sync,
  governed-package lock/artifact verification, architecture reports, evidence
  artifacts, and direct parser/API paths.
- Stage 3 closes AUD-003 through AUD-007 and AUD-012 pending full integration:
  accountable authority is intrinsically human-only, authority metadata is
  never coerced, standalone approvals bind to one governed revision,
  high-risk roles are checked as a strict authorized subset, and effective
  approvals retain bounded verifiable source lineage under ADR-0032.
- Stage 4 closes AUD-008 and AUD-013 pending full integration: declared SOD
  approvers are non-empty, human, joined to the exact change, restrictive
  approval gates, and corresponding evidence, with high-risk self-approval and
  declared-independence overlap rejected. The SOD module now declares its
  shared `changes` block/schema dependency. Exception expiry, overlap, closure,
  lifecycle, core-target, and explicit renewal semantics now fail closed;
  renewal approval proof is exact-type, authority-bound, fresh before
  activation, unique across artifacts and predecessor chains, and matched
  exactly by its renewal-action gate.
- An adjacent evidence-authority bypass found during Stage 4 is also closed:
  only `pass` records whose complete dependency chains pass may satisfy module,
  approval, change, exception, closure, or renewal evidence requirements.
- Structural enum handling is fail-closed and crash-safe: mappings, arrays,
  booleans, and numbers cannot reach hash-based lifecycle, risk, architecture,
  or claimed-approval-schema comparisons.
- Stage 5 closes AUD-014 through AUD-016 pending final integration: every
  repository artifact whose raw bytes are hash-bound is protected from Git
  line-ending conversion and a real `core.autocrlf=true` clone exercises the
  affected commands and corpus; governed-package changes retain the exact
  1.5.2 accept/reject domain through a compatibility adapter; public 1.x
  constructor prefixes and v1 serializers remain unchanged and are exercised
  by a downstream installed-wheel consumer.
- The additive architecture example now attributes its decision record to the
  change author rather than its approving architect, preserving the declared
  evidence/approval separation; the compatibility corpus pins the corrected
  canonical bytes for later migration-proof validation.
- Stage 6 closes AUD-019 through AUD-022 pending full integration: every lock
  loading or validation failure on governance inspection surfaces uses exit
  code 2; five intentional output/example migrations have immutable before and
  after artifacts plus exact machine-verified diffs; the installed-wheel smoke
  denies and records socket use while installing only the local wheel; and CI
  checks whitespace across the complete candidate range from the audited base.
- Approved migration evidence is bound by the markers
  `migration:explain-declared-controls-v1`,
  `migration:explain-effective-approval-v1`,
  `migration:modules-sod-contract-v1`,
  `migration:matrix-sod-contract-v1`,
  `migration:architecture-evidence-separation-v1`, and the additive
  `migration:architecture-governance-starter-v1` record. These records reflect
  the human-requested audit remediation; they do not grant runtime authority.

### Added
- Foundational data-only governance modules for human approval, evidence
  integrity, separation of duties, and exception management, with packaged
  schemas, deterministic monotonic composition, fixed structural checks, an
  executable local-evidence example, and adversarial coverage.
- Shared declarative change governance with evidenced lifecycle transitions,
  risk-proportionate human approval, revision and scope binding, rollback and
  closure checks, and one additive schema reused by governed packages.
- Optional architecture governance profile and conformance module with bounded
  declarations, revision-bound external evidence, a safe neutral-report
  importer, deterministic starter, and fixed reference/direction checks.
- Bounded module block-schema bindings. Packs may select only reviewed schemas
  bundled with Nornyx; inline schemas, remote references, custom validators,
  dynamic code, and unknown structural checks fail closed.
- Governance Surface Analysis dogfood, one validated advisory completeness
  matrix for each profile, and a compatibility-preserving profile/module
  mapping. GSA remains documentation, not a runtime schema or command.
- Read-only `modules list/inspect/validate`, `governance
  resolve/explain/matrix`, and `evidence validate` commands with text/JSON
  output, stable exit semantics, lock status, provenance, controls,
  requirements, exception status, and bounded local evidence verification.
- Public `validate_governance_evidence_file` API and an explicit governance API
  stability/deprecation policy.
- A formal compatibility corpus covering starters, examples, legacy API
  projections, CLI output/exit codes, generated artifacts, locks, manifests,
  and approved migrations, plus adversarial assurance for every new governance
  trust boundary.

### Changed
- Project contract checking now rejects every unresolved symlink component
  before reading the contract or discovering project governance packs.
- Approval composition intersects non-empty eligible human-role sets and fails
  on disjoint or required-role conflicts instead of broadening authority.
- Explicit normalized-v2 and effective-approval output retains
  `exact_revision_required` and relative `expires_after` independently from
  concrete revision bindings and absolute expiry timestamps; base-compatible
  `to_dict()` serializers remain v1.
- Approval normalization rejects non-string or empty accountable authority
  instead of coercing it into an apparent human identity.
- Approval authority now explicitly denies autonomous agents, models,
  connectors, and generated output in addition to AI tools and execution
  surfaces. Claimed normalized approvals are still fully re-derived from their
  retained source before use.
- Selected modules now enforce their required blocks, block schemas, evidence
  contracts, and fixed relational checks. Legacy profile-only requirements
  remain compatibility-preserving unless a module is explicitly selected.
- Governed-package changes retain the exact 1.x input domain through a frozen
  compatibility adapter and matching package schemas. The strict shared
  `nornyx.change.v1` identity and lifecycle rules apply only to an explicitly
  selected top-level `change_control` block; legacy nested extension metadata
  is not reinterpreted as governance authority.
- Architecture analysis remains external: Nornyx imports only a versioned
  local data envelope and never executes tools or infers repository structure.
  Architecture Radar is rejected for the current program by ADR-0030.
- Specialist candidate placement is closed by ADR-0031: supply-chain controls
  remain governed-package/external-evidence integrations, release control is
  superseded by existing release tooling and shared modules, and data
  protection, common lifecycle, and incident response are not required after
  GSA. The module catalog is frozen at six for this program.
- Local evidence-file loading now reuses the pack loader's unresolved-component
  symlink inspection, containment, resource limits, and safe YAML parser with
  evidence-specific fail-closed diagnostics.
- Project-local `.nornyx` discovery now preserves the unresolved project trust
  root and rejects symlinked ancestor components before enumerating profile or
  module packs.
- Governance block-schema validation now detects nested local-reference cycles
  and dangling local references, not only direct `$defs` aliases.
- Raw approval role lookup now fails closed on normalization/schema errors;
  non-string or empty authority values cannot normalize as roles, evidence, or
  governed actions, required roles must always be eligible, and offset
  timestamp formats are checked explicitly.
- Architecture report import now inspects unresolved path components from an
  independent trust root and rejects symlinked ancestors before reading.
- Approval and exception evidence names now resolve against actual governance
  evidence records; closed exceptions require available closure evidence.
- Explicit non-human actor identities such as `tool:*`, `agent:*`, `model:*`,
  `connector:*`, and `system:*` are denied approval, separation-of-duties, and
  exception authority in addition to the existing category denials.

## [1.5.2] - 2026-07-13

### Fixed
- Explicit profile paths now use a trust root independent of the pack's
  immediate parent. Every unresolved component between that root and the pack
  is inspected before path resolution, including components followed by `..`,
  so symlinked higher ancestors are rejected by both `profiles validate` and
  `init --profile-path`.

## [1.5.1] - 2026-07-13

### Fixed
- Explicit profile paths passed to `profiles validate` and
  `init --profile-path` retain unresolved path components so symlinked files
  and directories are rejected by the governance pack loader.
- Pre-normalized approval revalidation catches governance schema errors and
  fails closed with `RULE_REFERENCE_TYPE_ERROR` instead of aborting
  `nornyx check`.
- Generated starters no longer include scope entries for the deleted root
  `profiles/*.yaml` mirrors. The six affected starter goldens were refreshed
  as an explicitly approved intentional migration.

## [1.5.0] - 2026-07-13

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
  the same ancestor element. Pre-normalized approval payloads are re-validated
  end to end before their roles are read: the payload must satisfy the
  normalized-approval schema, carry no error diagnostics, expose roles only
  under a `complete` resolution, and exactly match the canonical payload
  regenerated from its retained raw source. Structural, semantic, diagnostic,
  and provenance fields are therefore re-derived rather than believed. Any
  failure makes `references_role` fail closed.
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
