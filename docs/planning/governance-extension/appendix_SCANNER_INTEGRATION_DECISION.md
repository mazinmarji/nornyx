# Appendix - Governed-Package Scanner Integration Decision

Status: accepted sequencing decision for PR 1. No branch merge is performed.

## Evidence inspected

The local branch `codex/governed-package-scanner-hardening` is available at
`4f0fcea`, one commit above `main` at `5fc1806`. It changes:

- `nornyx/governed_package.py` and its bundled schema;
- `nornyx/cli.py` and public governed-package docs;
- governed-package tests and examples;
- a new inert local scanner and evidence-adapter report path.

It does not change `nornyx/profiles.py`, root `profiles/*.yaml`, or the shape of
`governed_package.changes`. The profile implementation used for PR 1 golden
capture is byte-identical to main. The scanner adds evidence records, adapter
status, risk metadata, and approval-gate requirements; it does not add a shared
change schema.

## Decision

The declarative governance specification and test-foundation PR may proceed
against main because its new schema filenames do not overlap scanner files.
The scanner-hardening PR must merge before the future Change Governance
integration PR. That future PR must then re-audit the settled governed-package
schema, approval aliases, evidence records, and scanner-backed validation
before introducing a shared `nornyx.change.v1` schema.

PR 1 may describe the future shared change shape but must not add it to the
stable Nornyx schemas or delegate existing governed-package validation.

## Risk and responsibility

The principal risk is building Change Governance against pre-scanner evidence
or approval assumptions and reconciling twice. Sequencing the scanner first
removes that ambiguity. The future Change Governance PR owns reconciliation
and compatibility tests for every governed-package example. The future
Architecture Governance PR may reuse the scanner's report-import pattern only
after that pattern is merged and stable.

No scanner code, governed-package schema, or branch history is modified by PR 1.
