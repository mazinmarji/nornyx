## Nornyx 1.2.0

The first release built on community contributions — huge thanks to **@hass-nation**, who landed every feature in this version.

`pip install --upgrade nornyx`

### New
- **`nornyx --version`** — print the installed package version (#13, originally #7).
- **`nornyx workspace-check --quiet`** — print only the failing members on drift, stay silent on a clean pass. Tidier CI logs (#10).
- **A third bundled example, `release_guardrails.nyx`** — a CI/release-governance contract, shipped with the package (`nornyx examples`) and covered by the example checks (#11).

### Improved
- **Clearer missing-file error** — `nornyx check` now reports `contract file not found: <path>` instead of a generic read error (#8).
- **Docs for `nornyx complete`** — shell/editor completion is now documented in the README (#9).

### Project
- Added a CI workflow that runs the test suite on every push and pull request; the maintainer-run `nornyx-safe-dev-quality.yml` stays manual-only (#12).

### Notes
- Backward compatible — no breaking changes.
- The Nornyx **language/schema** version is unchanged (still 1.0); this is a package release only.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
