# Governance CLI and Public API

## Boundary

The governance inspection surface is local, read-only, and data-only. It does
not fetch packs or evidence, execute tools, analyze source, write locks, grant
approval, deploy, publish, remediate, or activate connectors. Specialist tools
remain external evidence producers.

`nornyx governance analyze` does not exist. GSA found runtime analysis tooling
`not_required_after_GSA` in ADR-0031.

## Commands

| Command | Result |
|---|---|
| `nornyx modules list [--json]` | Available built-in and project-local modules, versions, dependency ids, source tiers, and hashes. |
| `nornyx modules inspect <name> [--json]` | Full validated module declaration plus resolved provenance and content hash. |
| `nornyx modules validate <path> [--json]` | Bounded validation of one explicit local module pack. Profile packs fail with `PACK_KIND_MISMATCH`. |
| `nornyx governance resolve <contract> [--as-of <time>] [--json]` | Complete effective model, provenance trace, lock state, controls, evidence, approvals, exceptions, matrix, and diagnostics. |
| `nornyx governance explain <contract> [--as-of <time>] [--json]` | Concise effective controls and requirement view. |
| `nornyx governance matrix <contract> [--as-of <time>] [--json]` | One row per contributing profile/module with dependencies, controls, evidence, approvals, provenance, and hash. |
| `nornyx evidence validate <file> [--as-of <time>] [--json]` | Schema, local artifact hash, revision, dependency, and freshness validation for one `nornyx.governance_evidence.v1` YAML/JSON set. |

Project discovery uses `.nornyx/profiles/` and `.nornyx/modules/`, then built-ins.
Governance commands verify `nornyx.profiles.lock` when present and never create
or rewrite it. `--as-of` accepts an offset timestamp and should be supplied for
reproducible freshness and expiry results; otherwise the current UTC time is
used.

## Output and Exit Codes

Text output is YAML-shaped except for a one-line successful evidence result.
`--json` emits one JSON object. Governance resolution uses
`nornyx.governance_inspection.v1`; matrix output uses
`nornyx.governance_matrix.v1`.

| Code | Meaning |
|---|---|
| `0` | Valid or no governance selected. |
| `1` | Invalid pack, governance diagnostic, invalid evidence, or unresolved identity. |
| `2` | Contract parse failure or governance lock mismatch/invalid lock. |

Diagnostic codes retain their existing namespaces: `PACK_*`, `RULE_*`,
`GOVERNANCE_*`, `APPROVAL_*`, `EVIDENCE_*`, `SOD_*`, `EXCEPTION_*`, `CHANGE_*`,
and `ARCH_*`.

## Public Python API

The names in `nornyx.governance.__all__` are the intentional public governance
surface. Callable signatures and serialized `to_dict()` shapes are stable for
the package 1.x line unless deprecated first. The new evidence entry point is:

```python
from nornyx.governance import validate_governance_evidence_file

diagnostics = validate_governance_evidence_file(
    "governance-evidence.yaml",
    allowed_root=".",
    as_of="2026-06-01T00:00:00Z",
)
```

It returns immutable `GovernanceDiagnostic` values and raises
`GovernanceError` for untrusted paths, unreadable/oversized input, or malformed
YAML. Hash binding proves the declared artifact bytes, not the truth of the
claim.

Exported dataclasses are public result/value types. Callers should consume
their documented fields or `to_dict()` output; loader, schema, structural-check,
and reporting internals outside `__all__` are private. Public behavior will not
be removed without a changelog deprecation notice lasting at least two package
minor releases and six months, whichever is longer. Security fixes may tighten
rejection of malformed or untrusted input without a deprecation period.

Installed-wheel resources and the CLI implementation are checked locally
without network access by `python scripts/test_wheel_install.py <wheel>`.
