# Changelog

All notable changes to the Nornyx package are recorded here. The package
distribution version is independent of the Nornyx **language/schema** version
(still 1.0): a package patch can ship without changing the contract language.

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
