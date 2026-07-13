# 16 - Governance Module Catalog

## Contract

Built-in modules are authoritative YAML resources in `nornyx/profiles_data/`
and are listed in `catalog.json`. They are data-only, local-only, versioned,
integrity-locked, dependency-ordered, and composed monotonically. A module may
select only reviewed block schemas and fixed structural checks bundled with
Nornyx. It cannot ship code, an inline schema, an expression evaluator, a
network source, a custom validator, or approval authority.

## Implemented Modules

| Module | Dependencies | Blocks | Fixed checks | Purpose |
|---|---|---|---|---|
| `evidence_integrity` | none | `governance_evidence` | `evidence_integrity.v1` | Verify local artifact hashes, revision binding, freshness, dependencies, and mandatory evidence |
| `human_approval` | `evidence_integrity` | `approvals`, `governance_evidence` | `human_approval.v1` | Require accountable human roles, explicit non-human denials, exact revision binding, evidence, invalidation, and expiry |
| `separation_of_duties` | `human_approval` | `separation_of_duties` | `separation_of_duties.v1` | Enforce author/approver, producer/approver, release, and exception role disjointness |
| `exception_management` | `separation_of_duties` | `exceptions` | `exception_management.v1` | Keep exceptions project-owned, human-authorized, evidenced, compensated, expiring, and unable to weaken core safety |
| `change_control` | `exception_management` | `changes` | `change_control.v1` | Enforce evidenced lifecycle transitions, risk gates, revision and scope binding, human approval, rollback readiness, architecture evidence, and explicit closure |
| `architecture_conformance` | `change_control` | `architecture`, `architecture_evidence` | `architecture_conformance.v1` | Validate declared architecture, references and dependency directions, and revision-bound local evidence from external specialist tools |

Selecting `architecture_conformance` resolves all six modules in the order
shown. Executable contracts are `examples/governance_foundations.nyx` and
`examples/architecture_governance.nyx`.

## Evidence Semantics

`nornyx.governance_evidence.v1` records producer identity, artifact location,
SHA-256 content binding, subject revision, tool/version, generation and expiry
times, status, and dependencies. Validation reads only declared local files
under the trusted document root and rejects symlinks, traversal, missing files,
hash substitution, revision mismatch, stale/future evidence, duplicate IDs,
and dependency errors.

A valid hash proves that reviewed bytes match the declaration. It does not
prove the evidence claim is correct, complete, unbiased, or produced by the
claimed tool. Human review and specialist systems retain that responsibility.

## Approval Semantics

The module reuses `normalize_approval`; there is no second approval model.
Claims already marked as normalized are schema-checked and fully re-derived
from retained `source.raw` before they can confer role references. High-impact
approval declarations require a human authority, prerequisite evidence, exact
revision binding, invalidation conditions, and expiry. AI tools, execution
surfaces, autonomous agents, models, connectors, and generated output are
denied authority.

## Exception Boundary

Exceptions cannot target the stable core safety namespace, pack integrity,
data-only loading, no-executable-code, no-network, no-auto-approval,
non-human-authority denial, or no-external-tool-execution controls. Nornyx
validates declarations only; it never approves, renews, applies, or executes an
exception or compensating control.

## Architecture Evidence Boundary

Architecture analysis remains external. CI adapters may create the bounded
`nornyx.architecture_report.v1` envelope; Nornyx parses, validates, hashes, and
revision-binds it as `nornyx.architecture_evidence.v1`. Nornyx never invokes a
tool or infers architecture from source. ADR-0030 rejects Architecture Radar
for the current program.
