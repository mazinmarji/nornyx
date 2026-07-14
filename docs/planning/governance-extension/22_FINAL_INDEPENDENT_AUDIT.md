# 22 - Exact-Head Independent Audit Record

Status: **ready for a fresh independent read-only audit.**

The former `GO` record is superseded. It did not cover AUD-001 through AUD-022
reported against `35ee69359599af7887f6b9b58ae0a4cd06a48d25` and must not be
used as current evidence.

## Audit Identity

- Repository: `mazinmarji/nornyx`
- Pull request: `#30`
- Base: `95952226999327458c6fea81cb32d82539bcae5b`
- Failing head: `35ee69359599af7887f6b9b58ae0a4cd06a48d25`
- Remediated implementation through Stage 6:
  `6c0732c1be916a802e20bffce6eabf4bd7309703`
- Final audit target: the clean checked-out `HEAD` containing this record
- Authorization: read-only audit; no merge or release authority

## Required Evidence

The independent auditor must inspect the complete base-to-head diff and the
machine-readable `AUDIT_REMEDIATION_LEDGER.json`, reproduce all 22 original
findings, search adjacent bypass variants, inspect packaged resources, and run
or verify:

```text
python -m pytest -q
python -m ruff check .
python scripts/check-public-boundary.py --repo .
python scripts/check_compatibility_migrations.py
python -m build
python -m twine check dist/*
git diff --check 95952226999327458c6fea81cb32d82539bcae5b...HEAD
```

The audit must separately cover real Linux symlinks, the compatibility corpus,
governed examples and packages, installed-wheel resources/no-network behavior,
12 built-in profiles, 6 built-in modules, public API stability, and thread-aware
GitHub review state.

## Current Evidence Boundary

Local evidence passes the focused AUD suites, real Windows
`core.autocrlf=true` clone, exact migration verifier, Ruff, public-boundary
check, source/wheel build, and socket-denied wheel smoke. The exact Stage 7
Windows command `python -m pytest -q` passes `913 passed, 45 skipped`. The
Ubuntu/WSL outcome is recorded only after the committed candidate executes
there successfully.

No hosted Linux CI result exists for the local remediation head because it has
not been pushed. PR #30 remains draft at remote head `35ee693`; the thread-aware
GitHub query returns zero review threads. Hosted CI is therefore a pending
external release condition, not a claimed pass.

## Verdict Boundary

This in-tree record does not self-authorize a verdict. The fresh auditor's
exact-head result belongs in the task handoff. `GO` requires no unresolved
finding and green hosted CI for the exact candidate. Human merge and release
authorization remain separate in every case.
