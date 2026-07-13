## Nornyx 1.5.1

`pip install --upgrade nornyx`

Nornyx 1.5.1 is a focused governance hardening hotfix for three findings
identified after the 1.5.0 release.

### Raw-path symlink enforcement

`nornyx profiles validate` and `nornyx init --profile-path` now preserve the
unresolved components of explicit user paths when invoking the local pack
loader. Symlinked pack files and symlinked parent directories are rejected
instead of being accepted after eager path resolution.

### Fail-closed approval revalidation

Malformed retained approval source data that raises a governance schema error
during canonical re-normalization now produces `RULE_REFERENCE_TYPE_ERROR`.
It no longer escapes rule evaluation as an unhandled exception from
`nornyx check`.

Coverage includes invalid retained raw data, invalid timing, malformed revision
bindings, and inconsistent source shapes.

### Starter scope correction

The six affected built-in profile starters no longer reference deleted root
`profiles/*.yaml` mirrors. All 11 built-in packs are regression-checked for
stale profile scope entries, and the six changed starter goldens are recorded
as an explicitly approved intentional migration.

The Nornyx language/schema version remains 1.0. This patch changes package
behavior and generated starter content only.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
