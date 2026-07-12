# Appendix — CLI and Developer Experience Specification

Covers brief §11. Preserves all current commands; additions are namespaced
under the existing `profiles` noun (mirroring how `package` grew subcommands).

## Commands

| Command | Behavior | Exit codes |
|---|---|---|
| `nornyx profiles` | Unchanged: 11 names, one per line (compat alias for `list`) | 0 |
| `nornyx profiles list [--json]` | Names + version + status + source tier | 0 |
| `nornyx profiles inspect <name> [--json]` | Full validated v1 profile, provenance, hash, module deps | 0; 1 unknown name (`PACK_NOT_FOUND`) |
| `nornyx profiles validate <path> [--json]` | Schema + structural + rule-language validation of one pack file | 0 valid; 1 invalid (diagnostics listed) |
| `nornyx profiles resolve <name> [--lock] [--json]` | Full resolution: precedence trace, dependency order, hashes; `--lock` writes `nornyx.profiles.lock` | 0; 1 resolution failure; 2 lock mismatch |
| `nornyx profiles compatibility <p> [<p>...]` | Composed compatibility verdict (conflicts fatal-listed, review-with warned) | 0 compatible; 1 conflicts |
| `nornyx init --profile <name>` | Unchanged | unchanged |
| `nornyx init --profile-path <file>` | New: scaffold from explicit pack (validate first, fail-closed) | 0; 1 invalid pack |
| `nornyx governance analyze <contract>` | Deferred to PR 7 decision gate; not committed here | — |

## Conventions (matching existing CLI style)

- Human output: terse lines, paths printed after a one-line status (existing
  `cmd_init` pattern). JSON output: `--json` flag, one object, `status` field —
  matching `cmd_package_*` conventions.
- Errors: JSON error objects `{level, code, message}` to stdout with exit 1,
  exactly like `cmd_init`/`cmd_package_generate` today (consistency beats
  stderr purity here; revisit repo-wide, not piecemeal).
- Stable diagnostic codes: `PACK_*` (load/registry), `RULE_*` (evaluator),
  `EXC_*` (exceptions), `LOCK_*`. Codes documented in one generated reference
  page; adding/renaming a code is CHANGELOG-worthy.
- Offline: every command works with no network; there is nothing to disable.
- Provenance display: `inspect`/`resolve` always print source tier, path, hash —
  trust is visible by default, not opt-in.
- Windows: all path handling through `pathlib`; output paths printed with
  `as_posix()` for machine-read fields and native for human lines (current
  mixed behavior in `cli.py` should be normalized to this rule — small,
  documented UX fix).
- No new top-level nouns beyond `profiles` (and possibly `governance` at PR 7);
  reject flag proliferation — anything needing >2 new flags goes back to design.
