## Nornyx 1.4.0

`pip install --upgrade nornyx`

### New: Governed Package Profile

Nornyx now includes a standalone governed package profile for declarative,
validation-first package contracts. It can define controlled work, evidence
requirements, approval gates, risk tier, artifacts, safety boundaries,
installation policy, provenance, and package locks.

The profile is inert by design. Nornyx creates contracts, manifests, reports,
locks, and suggestions. It does not execute, install, approve, deploy, store
secrets, or operate runtime systems.

### Package operating modes

- `nornyx package generate`: generate an inert governed package directory from a
  `.nyx` contract.
- `nornyx package register`: describe and hash-lock an existing artifact
  directory without making it executable.
- `nornyx package radar`: scan a folder and propose candidate governed package
  contracts and missing controls. Radar output is advisory only.

### Safety and integrity

- Generated packages are not installed and are not executable by default.
- Execution surfaces are treated as tools, never accountable approvers.
- Unsafe installation and safety flags fail validation.
- Package locks verify generated artifacts.
- Registered artifact hashes are re-checked when the registered source directory
  is available.
- Radar flags secret-like material by path and does not copy secret-like values
  into reports.

### Public boundary hardening

This release adds public-boundary policy documentation and a local scan helper
for keeping public repository content product-neutral. Tests use neutral
synthetic markers only; downstream-specific deny lists belong outside the public
repository.

### Notes

- Backward compatible for existing `.nyx` contracts and CLI commands.
- The Nornyx language/schema version is unchanged (still 1.0); this is a package
  release.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
