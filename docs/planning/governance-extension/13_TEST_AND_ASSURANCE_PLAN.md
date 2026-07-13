# 13 — Test and Assurance Plan

Status: implemented through Stage I. This document began as the PR-era test
plan; reports 19-20 and 22 plus the formal compatibility/security tests are the
current execution record. The final local result is 532 passed and 12
platform skips. Linux CI passes all 544 tests, including real symlink cases.

## Categories and representative cases

**Backward compatibility (golden)**
- 12 profiles: exact current-main Windows bytes plus canonical-LF hashes are
  captured. Current generation must be semantically and canonical-LF equal;
  line endings are the sole approved normalization (appendix F-01).
- `nornyx profiles` stdout identical; `init` flags identical; exit codes identical.
- Contracts without packs: checker diagnostics byte-equal on a fixture corpus.
- Full existing suite green at every stage boundary.
- Governed-package examples and established golden manifests remain pinned.

**Loader / registry (unit + fixtures)**
- Discovery precedence: explicit > project > org > builtin; resolution trace
  golden. Dynamic discovery from `.nornyx/profiles/`; explicit-path loading.
- Invalid pack schemas (one fixture per required field + unknown top-level key).
- Duplicate identity same-tier (fatal) and cross-tier (shadow + provenance).
- Reserved-namespace squat (`nornyx.builtin.*` from project tier) rejected.
- Version incompatibility (`compatible_core` unsatisfied) fail-closed.
- Dependency cycles (self, pair, 3-cycle) named in diagnostic.
- Frozen v0.3 fixture validation, valid v1 fixture validation, exact
  v1-to-v0.3 projection, separate loss report, and must-preserve failure.

**Composition (unit + property-based)**
- Deterministic merge: same inputs, permuted load order ⇒ identical effective
  model (property-based via hypothesis if the dependency is acceptable;
  otherwise permutation table tests).
- Merge-by-id, duplicate-in-layer fatal, override-permission matrix.
- Monotonicity adversarial suite: pack attempts deny removal, approval
  optionalization, `ai_tool` approver injection, evidence removal, budget
  raising without permission — each must fail with its stable code
  (`PACK_MONOTONICITY_*`). Includes the composer-invariant backstop test
  (hand-built malicious effective model rejected).
- Exceptions: valid full-field exception downgrades to warning; each missing
  field invalidates; expiry (`EXCEPTION_EXPIRED`); core-checker codes not
  exceptable; pack-supplied exceptions rejected.

**Rule evaluator**
- Every operator: positive/negative/absent-path cases.
- Unknown operator ⇒ pack load failure (never skip).
- Path grammar: `[]` traversal, depth-8 cap, rejected escapes.
- `matches_id` restricted grammar (no regex metacharacters honored).
- Severity, message, provenance in diagnostics; stable code format.

The evaluator reuses the original specification fixture ids, and every case is
executed against the current runtime.

**Security / adversarial (doc 10 mapping)**
- Path traversal fixtures (`../`, absolute, drive-relative on Windows).
- Symlink escape (skipped where symlinks unavailable — runs on Linux CI).
- YAML abuse: alias bomb, deep nesting, 10 MB file, null bytes, non-UTF8.
- Template-injection attempts in fragments (rendered literally).
- Hash mismatch, lock version substitution, stale lock, missing lock warning.
- Offline guarantee: static import audit of `nornyx/packs/` (no network
  modules), plus a socket-disabled integration run.

**Cross-platform**
- Windows path fixtures (backslashes, drive letters, reserved names).
- CRLF-input packs hash identically to LF (canonicalization test).
- Unicode pack filenames and rejection of Unicode/confusable pack ids by the
  ASCII identity grammar.

**Determinism (lesson from the scanner-branch defect: name tests honestly)**
- Double-run byte-equality for: composed model dump, rendered starter output,
  resolution trace, lock file (excluding nothing — locks contain no timestamps
  by design; if a timestamp is ever added it must be injected, not sampled).

**Specification foundation**
- Root and bundled schemas are byte-identical and meta-schema valid.
- Unknown operators, malformed paths/core ranges/compatibility, version
  mismatch, and additional properties are rejected.
- Collection semantics fixture covers existential `when`, universal `require`,
  empty/missing/null/type cases, nested lists, duplicates, and prefix binding.
- Approval normalization fixture covers ordinary, generated, governed-package,
  alias, reference, prose, boolean, duplicate, conflict, and unknown-role cases.
- Module security fixtures prove network/code/command/credential/approval-grant
  and core-weakening flags cannot be enabled.
- Tests bind the schema fixtures to the implemented loader, composer, and rule
  runtime without redefining their semantics.

**Change / architecture governance**
- Governed-package compatibility corpus.
- Change lifecycle rules; separation-of-duties structural check.
- Approval invalidation: revision mismatch fixture ⇒ `APPROVAL_STALE_FOR_REVISION`.
- Architecture evidence: pass/fail/stale-revision/missing-hash fixtures;
  malformed evidence reports (truncated JSON, wrong schema id) fail-closed.

**Documentation assurance**
- Governance CLI/API markers are tied to executable command and public-API
  tests. README and repository script commands retain their existing execution
  tests. The installed-wheel probe executes the packaged module CLI outside the
  repository.

**Distribution assurance**
- `python -m build` creates source and wheel distributions.
- `python -m twine check` validates both artifacts.
- `scripts/test_wheel_install.py` installs the wheel locally with `--no-deps`,
  isolates it from the repository, verifies packaged schemas/profiles/modules,
  imports the public API, and executes the installed CLI without network use.
