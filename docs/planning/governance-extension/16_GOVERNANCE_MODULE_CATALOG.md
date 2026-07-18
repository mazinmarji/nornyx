# 16 - Governance Module Catalog

Status: implemented catalog; the historical governance program closed with six
modules and ADR-0033 independently authorizes one bounded additive module.

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
| `separation_of_duties` | `human_approval` | `separation_of_duties`, `changes` | `separation_of_duties.v1` | Join assignments to changes and gates; enforce high/critical author separation and producer separation when evidence independence is required, plus declared release/exception separation |
| `exception_management` | `separation_of_duties` | `exceptions` | `exception_management.v1` | Keep exceptions project-owned, human-authorized, evidenced, compensated, expiring, and unable to weaken core safety |
| `change_control` | `exception_management` | `changes` | `change_control.v1` | Enforce evidenced lifecycle transitions, risk gates, revision and scope binding, human approval, rollback readiness, architecture evidence, and explicit closure |
| `architecture_conformance` | `change_control` | `architecture`, `architecture_evidence` | `architecture_conformance.v1` | Validate declared architecture, references and dependency directions, and revision-bound local evidence from external specialist tools |
| `agentic_network_governance` | `human_approval` | `agentic_network`, `agent_identities`, `capabilities` | `agentic_network_foundation.v1` | Validate a static agentic-network contract, bounded authorization, revocation, sensitive sharing, evidence, and human authority without operating a network |

Selecting `architecture_conformance` resolves all six modules in the order
shown. Executable contracts are `examples/governance_foundations.nyx` and
`examples/architecture_governance.nyx`.

ADR-0031 freezes this catalog at six modules for the current program. GSA found
no reusable seventh module: supply-chain controls retain their scanner and
external-evidence owner, release control is superseded by existing tooling,
and data protection, common lifecycle, and incident response are not required
after GSA. Their documented re-entry conditions require new evidence and human
review; none is merely deferred inside this roadmap.

ADR-0033 is a later, proposed domain decision based on a concrete
two-layer profile/module contract and executable fixtures. It raises the
installed catalog to seven modules without changing any of the six historical
modules or existing profile mappings. Its direct dependency is only
`human_approval`; evidence integrity is resolved transitively.

## Evidence Semantics

`nornyx.governance_evidence.v1` records producer identity, artifact location,
SHA-256 content binding, subject revision, tool/version, generation and expiry
times, status, and dependencies. Validation reads only declared local files
under the trusted document root and rejects symlinks, traversal, missing files,
hash substitution, revision mismatch, stale/future evidence, duplicate IDs,
dependency errors, and approval or exception references to absent records.

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
non-human-authority denial, no-external-tool-execution controls, reserved
governance diagnostic namespaces, or selected built-in control/rule ids.
Nornyx validates declarations only; it never approves, renews, applies, or
executes an exception or compensating control. Active intervals use half-open
bounds and cannot overlap for the same control and intersecting scope. Expired
and closed records require passing closure evidence. Renewal is a separate,
non-overlapping record that references its predecessor and single-use,
exactly typed human approval proof with a unique artifact/hash, no predecessor
reuse, and a generation time between the predecessor start and renewal
activation. The corresponding human approval gate must explicitly name the
`renew_exception:<id>` action, authorize the renewal authority, and require
exactly the declared proof set.

## Architecture Evidence Boundary

Architecture analysis remains external. CI adapters may create the bounded
`nornyx.architecture_report.v1` envelope; Nornyx parses, validates, hashes, and
revision-binds it as `nornyx.architecture_evidence.v1`. Nornyx never invokes a
tool or infers architecture from source. ADR-0030 rejects Architecture Radar
for the current program.
