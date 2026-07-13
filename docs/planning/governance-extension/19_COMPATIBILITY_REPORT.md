# 19 - Backward Compatibility Report

Status: implemented compatibility release gate.

## Baseline and Policy

The formal corpus is
`tests/fixtures/governance_compatibility/manifest.json`, anchored to Nornyx
1.5.2 and baseline main commit
`95952226999327458c6fea81cb32d82539bcae5b`. It distinguishes:

- `byte_identical`;
- `canonical_lf_identical`;
- `semantically_equivalent`;
- `intentional_migration_requiring_approval`.

Tests fail on unrecorded additions, removals, byte changes, canonical JSON
changes, exit-code changes, or missing migration approval metadata. A failed
golden is not regenerated automatically.

## Corpus Coverage

| Required surface | Classification | Executable evidence | Result |
|---|---|---|---|
| All profile starters | Byte/canonical-LF hashes from the established starter manifest | `test_current_main_starter_goldens_are_complete_hashed_and_deterministic` plus corpus delegation test | 11 established starters unchanged; architecture starter additive |
| Existing governed-package examples | `canonical_lf_identical` | complete enumerated canonical-LF path/hash set in compatibility manifest | pinned across Git text checkout modes |
| Existing top-level `.nyx` examples | `canonical_lf_identical` | complete enumerated canonical-LF path/hash set in compatibility manifest | pinned across Git text checkout modes |
| Legacy profile API output | `semantically_equivalent` | catalog/API tests plus pinned `ai_coding` v0.3 projection and loss report | pinned |
| CLI stdout and exit codes | `semantically_equivalent` canonical JSON | six success/error cases with repository-root normalization | pinned |
| Generated artifacts and manifests | `canonical_lf_identical` | both committed generated-drift baselines | pinned across Git text checkout modes |
| Governance locks | `canonical_lf_identical` | canonical minimal-profile lock hash and existing permutation tests | pinned |
| Governed-package locks/manifests | `semantically_equivalent` plus deterministic scanner anchors | governed-package generation, tamper, and byte-determinism tests | retained |
| Projection reports | `semantically_equivalent` | normative projection cases and pinned report hash | pinned |

## Approved Migration Record

The program changed no established starter golden. It added one new
`architecture_governance` starter, for which no old hash existed. The corpus
records its new byte hash, additive classification, exact reason, approval
context, and changelog location. The eleven 1.5.2 profile starters retain their
existing hashes and semantics.

The PR #30 blocking review required `exact_revision_required` and
`expires_after` to appear in normalized effective approval reporting. The
`governance_explain` canonical hash therefore changes from
`651fd74c369080e28b6599e8ad608a6a59d40170d1c63c3d6507eeb56ac7afb8` to
`dcc04caa5f693831db56d3c1fb341622e2be508279415eea9109fe18ff7d6de3`.
The corpus records the exact additive paths, unchanged exit code, reason,
review approval, and changelog location. No field was removed.

Governance modules, schemas, commands, examples, and advisory GSA matrices are
additive. Existing free-form `project.profile` values retain warning-and-pass
behavior; explicit module selection remains fail closed. Existing profile
projection and lock formats are unchanged.

## Residual Compatibility Risk

Security corrections may reject malformed or untrusted inputs previously
accepted accidentally; this is an intentional tightening, not supported input
breakage. CLI reports contain current validation time unless `--as-of` is
provided. Absolute repository paths are normalized only for corpus comparison,
not in real CLI output.

The compatibility corpus is a release gate. Any future changed golden requires
old hash, new hash, exact diff, reason, classification, approval, and changelog
entry before the test can be updated.

Wheel packaging is checked separately by `scripts/test_wheel_install.py`. The
probe installs one local wheel with `--no-deps` into a temporary environment,
runs outside the repository with isolated Python path handling, and verifies
all packaged profiles, modules, governance schemas, the public evidence API,
and the installed CLI without network access.

## Final Execution Evidence

At audited commit `16f8eb350e61966d37000f34b8ebdd720aa741af`, the
Windows suite passes 522 tests with 10 platform symlink skips. Linux CI run
`29260631031` passes all 532 tests. A fresh 1.5.2 source distribution and wheel
pass Twine, and the isolated wheel probe reports 12 profiles, 6 modules, no
network use, and status pass.
