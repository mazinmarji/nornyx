# 13 — Test and Assurance Plan

## Categories and representative cases

**Backward compatibility (golden)**
- 11 profiles: exact current-main Windows bytes plus canonical-LF hashes are
  captured. Current generation must be semantically and canonical-LF equal;
  line endings are the sole approved normalization (appendix F-01).
- `nornyx profiles` stdout identical; `init` flags identical; exit codes identical.
- Contracts without packs: checker diagnostics byte-equal on a fixture corpus.
- Full existing suite (currently ~330 tests) green at every PR boundary.
- Governed-package examples and golden manifests unchanged through PR 5.

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

PR 1 covers these as schema and specification fixtures only. Evaluator outcome
tests begin when the evaluator exists; they must reuse the PR 1 semantic-case
ids rather than silently redefining them.

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
- Unicode pack filenames and unicode ids.

**Determinism (lesson from the scanner-branch defect: name tests honestly)**
- Double-run byte-equality for: composed model dump, future rendered starter output,
  resolution trace, lock file (excluding nothing — locks contain no timestamps
  by design; if a timestamp is ever added it must be injected, not sampled).

**PR 1 specification foundation**
- Root and bundled draft schemas are byte-identical and meta-schema valid.
- Unknown operators, malformed paths/core ranges/compatibility, version
  mismatch, and additional properties are rejected.
- Collection semantics fixture covers existential `when`, universal `require`,
  empty/missing/null/type cases, nested lists, duplicates, and prefix binding.
- Approval normalization fixture covers ordinary, generated, governed-package,
  alias, reference, prose, boolean, duplicate, conflict, and unknown-role cases.
- Module security fixtures prove network/code/command/credential/approval-grant
  and core-weakening flags cannot be enabled.
- Tests assert no loader/composer package exists and do not claim current
  runtime behavior for planned rules.

**Change / architecture governance (PR 5–6)**
- Governed-package compatibility corpus.
- Change lifecycle rules; separation-of-duties structural check.
- Approval invalidation: revision mismatch fixture ⇒ `APPROVAL_STALE_FOR_REVISION`.
- Architecture evidence: pass/fail/stale-revision/missing-hash fixtures;
  malformed evidence reports (truncated JSON, wrong schema id) fail-closed.

**Documentation assurance**
- Doc examples executed: every fenced `nornyx ...` command in the new docs runs
  in CI against fixtures (guards against the doc-drift problem found in audit
  doc 01 §1.6).
