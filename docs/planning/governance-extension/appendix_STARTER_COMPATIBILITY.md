# Appendix - Starter Compatibility Baselines (F-01)

Status: normative PR 1 specification and captured test foundation.

## Authoritative baseline

All 11 names exposed by `nornyx profiles` and accepted by `nornyx init` are
captured under `tests/fixtures/governance_extension/starter_golden/` using:

```text
source ref: main
source commit: 5fc1806fedb46e221eaa48a5129174e9a1a9d6f4
Nornyx package version: 1.4.0
project name: GovernanceGolden
command: python -m nornyx.cli init --profile <name> --name GovernanceGolden --out <fixture>
```

The manifest records the command, exact SHA-256, canonical-LF SHA-256, source
commit, package version, and compatibility class for every profile. The
captured implementation was verified identical between `main` and the current
scanner-hardening branch before capture.

## Compatibility classes

- `byte_identical`: every output byte must match. This is the default for any
  new baseline unless repository evidence requires normalization.
- `semantic_equivalence_allowed`: only the normalization explicitly recorded
  in the baseline manifest is permitted. Parsed values, mapping order, list
  order, scalar spelling, and content remain frozen.
- `intentional_migration_requires_approval`: an identified output migration is
  blocked until a human approves the reason and reviewed replacement hashes.

Current-main `write_profile()` uses platform text translation. The same
starter is CRLF on Windows and LF on POSIX. This is repository evidence that
cross-platform byte identity is not currently achievable without changing
starter generation, which PR 1 must not do. All existing profiles therefore
use `semantic_equivalence_allowed` with exactly one permitted normalization:
`CRLF_to_LF_only`. The exact Windows current-main bytes are preserved as the
goldens; canonical-LF hashes make the cross-platform expectation explicit.

## Change approval procedure

1. Run the golden tests and investigate the first mismatch. Do not regenerate.
2. Classify the cause as a defect, a line-ending-only difference, or an
   intentional migration.
3. For an intentional migration, document affected profiles, before/after
   hashes, semantic differences, compatibility impact, rollback, and approval
   authority in the PR and CHANGELOG.
4. Obtain explicit human approval for the migration.
5. Run `scripts/capture_profile_starter_baselines.py --approve-update
   --approval-reason "<reviewed reason>"` in the approved change only.
6. Review fixture diffs; never accept a bulk golden update without explaining
   every changed profile.

The capture script refuses content mismatches by default and refuses to capture
from an implementation that differs from the recorded source commit.

## F-01 closure

Resolution: closed for PR 1. Exact current-main output and canonical hashes now
exist for every public profile, deterministic double-run tests cover every
profile, and the only semantic-equivalence allowance is the demonstrated
platform newline translation. Future generator refactoring remains blocked on
these baselines and the approval procedure above.
