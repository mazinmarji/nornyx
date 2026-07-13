## Nornyx 1.5.0

`pip install --upgrade nornyx`

### Governed package hardening

Nornyx now includes a deterministic, inert package scanner for examining
untrusted package trees without executing package payloads. Scanner output is
bound into governed-package manifests and locks so review decisions can be
traced to exact source inventory and evidence hashes.

- `nornyx package scan` inventories files, records hashes, and detects hooks,
  MCP configuration, secret-like content, endpoints, dangerous commands,
  scripts, and claim-versus-evidence mismatches.
- Scanner-derived reports and hashes are reproducible for identical input.
  Provenance timestamps remain intentionally run-specific.
- Symlinked files are skipped, directory links are not followed, and read or
  stat races become evidence errors instead of aborting the scan.
- Broad filesystem grants remain critical findings, while ordinary relative
  source references are classified without root-path false positives.
- Required evidence adapters fail closed by default unless a pack explicitly
  selects warning behavior.

### Evidence and review reports

- Normalized scanner evidence, source inventory, risk scoring, and
  claim-versus-evidence reports are available as JSON and Markdown.
- Optional report importers accept Syft-like SBOM and Gitleaks-like secret
  evidence. Nornyx parses supplied reports but does not execute external tools.
- Governed-package validation now covers observed hooks, MCP configuration,
  secret-like content, claim mismatches, required-adapter failures, and critical
  external evidence.

### Declarative governance runtime

This release also activates the local declarative profile and governance-module
contracts introduced by the governance extension:

- deterministic local profile/module discovery, monotonic composition, and
  timestamp-free profile locks;
- closed rule evaluation with fail-closed structural errors and collection
  binding semantics;
- approval normalization with intrinsic denial of AI tools and execution
  surfaces as approvers;
- exact v1-to-v0.3 projection with separate loss and provenance reports;
- packaged authoritative v1 data for all 11 built-in profiles while preserving
  starter compatibility and legacy Python API shapes.

Discovery remains offline and data-only. Profiles and modules cannot load from
the network, discover Python entry points, or execute supplied code.

### Notes

- Nornyx does not claim that scanned packages are safe. It inventories,
  risk-surfaces, evidence-binds, hash-locks, and approval-gates untrusted input.
- Existing `.nyx` contracts remain compatible. Unknown profile names continue
  with a warning; explicitly selected unknown modules fail closed.
- The Nornyx language/schema version is unchanged (still 1.0); this is a package
  release.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
