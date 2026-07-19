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

All caller-controlled contract, pack, evidence, architecture-report, and lock
paths are screened lexically before filesystem access. URL/URI, UNC, Windows
extended/device, reparse-point, junction, live-symlink, and dangling-symlink
paths fail closed. Unresolved components are inspected from the filesystem
anchor (or current working directory for relative input); an explicit
`trust_root` can narrow containment but cannot hide a higher ancestor.

Profile locks are bounded to 512 KiB, strict UTF-8 JSON, reject duplicate keys
at every nesting level and non-finite constants, and must satisfy the packaged
lock schema before semantic duplicate/set/hash verification.

## Output and Exit Codes

Text output is YAML-shaped except for a one-line successful evidence result.
`--json` emits one JSON object. Governance resolution uses
`nornyx.governance_inspection.v1`; matrix output uses
`nornyx.governance_matrix.v1`.

| Code | Meaning |
|---|---|
| `0` | Valid or no governance selected. |
| `1` | Invalid pack, governance diagnostic, invalid evidence, or unresolved identity. |
| `2` | Contract parse failure or governance lock path, encoding, JSON, schema, set, hash, or semantic validation failure. |

Diagnostic codes retain their existing namespaces: `PACK_*`, `RULE_*`,
`GOVERNANCE_*`, `APPROVAL_*`, `EVIDENCE_*`, `SOD_*`, `EXCEPTION_*`, `CHANGE_*`,
`ARCH_*`, and `AN_*`.

The existing list, inspect, resolve, explain, and matrix commands discover the
optional `agentic_network` profile and `agentic_network_governance` module.
There is no new runtime command or public Python export. Running inspection for
that profile validates only local static declarations and never opens an A2A or
MCP connection, constructs a framework agent, or loads an endpoint, command,
credential, token, or key.

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

Composed approvals use the separately versioned
`nornyx.effective_approval.v1` envelope. The public verifier replays its
bounded retained-source composition:

```python
from nornyx.governance import (
    GovernanceRegistry,
    compose_governance,
    trusted_effective_approval,
)

registry = GovernanceRegistry.builtins()
composition = compose_governance(registry, profile_identity="architecture_governance")
for payload in composition.to_effective_dict()["approval_requirements"]:
    assert trusted_effective_approval(payload) is not None
```

`NormalizedApproval.to_verifiable_dict()` emits
`nornyx.normalized_approval.v2`; `NormalizedApproval.to_dict()` always retains
the established v1 shape. Likewise, `CompositionResult.to_dict()` remains the
v1 compatibility view and `to_effective_dict()` explicitly emits the bundled
`nornyx.effective_governance.v2` schema. Source hashes detect inconsistent
mutation but are not signatures. Missing source identities use a fallback
derived only from source shape and canonical path. Built-in effective leaves
are authenticated against packaged packs; non-built-in leaves require the
same independently established registry as a keyword argument to
`trusted_effective_approval`.

For 1.x downstream consumers, the original positional constructor fields of
`GovernanceModule`, `NormalizedApproval`, and `CompositionResult` remain the
unchanged leading fields. Additive fields are trailing defaults. The source
compatibility suite exercises both positional and keyword construction and
compares the complete v1 serialized payloads; the installed-wheel smoke runs
the same legacy consumer outside the source tree.

Installed-wheel resources and the CLI implementation are checked locally
without network access by `python scripts/test_wheel_install.py <wheel>`.
