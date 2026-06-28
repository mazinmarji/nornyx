# Changelog

All notable changes to the Nornyx package are recorded here. The package
distribution version is independent of the Nornyx **language/schema** version
(still 1.0): a package patch can ship without changing the contract language.

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
