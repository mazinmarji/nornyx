# 08 — Architecture Governance Design

## Positioning

An **implemented optional profile** (`architecture_governance`) composed from
`change_control`, `architecture_conformance`, `evidence_integrity`,
`exception_management`, `human_approval`. Nornyx declares which architecture
checks are required, what evidence they must produce, binds evidence to exact
revisions, validates presence/integrity/freshness, applies gates — and does
**not** parse source code, infer architecture, detect duplicate code, or
replace ArchUnit / import-linter / dependency-cruiser / Semgrep / CodeQL /
SonarQube / compiler checks.

## Governed Vocabulary

The `architecture_conformance` module contributes the reviewed
`nornyx.architecture.v1` schema. It covers descriptions, viewpoints, systems,
components, modules, layers, bounded contexts, interfaces, dependency
directions, trust/data/deployment boundaries, canonical components, decisions,
ADR artifacts, principles, constraints, required checks, and references to the
single governed-exception model.

```yaml
architecture:
  schema: nornyx.architecture.v1
  subject_revision: git:<exact-revision>
  descriptions: [{id, title, viewpoints: [...], artifact: docs/arch/overview.md}]
  systems: [...]
  components: [{id, name, layer, bounded_context, canonical: true}]
  layers: [{id, name, may_depend_on: [layer-ids]}]
  bounded_contexts: [...]
  interfaces: [{id, provider, consumers: [...], contract_artifact: ...}]
  boundaries:
    trust: [{id, description, crossing_requires: [...]}]
    data: [...]
    deployment: [...]
  decisions: [{id: ADR-0007, status, artifact: docs/ADRs/0007-*.md, supersedes: []}]
  principles: [...]
  constraints: [{id, statement, verified_by: check-id | human_review}]
  required_checks:
  - id: dependency-boundaries
    tool: import-linter                # declared, not executed by Nornyx
    evidence_schema: nornyx.architecture_evidence.v1
    frequency: per_change
```

`impact classification` lives on changes (`impacts.architecture`, doc 07) —
one model, no duplicate.

## Normalized Architecture Evidence

`nornyx.architecture_evidence.v1` uses the brief's shape plus explicit expiry:

```json
{
  "schema": "nornyx.architecture_evidence.v1",
  "check_id": "dependency-boundaries",
  "tool": "import-linter",
  "tool_version": "2.0",
  "status": "pass",
  "subject_revision": "<commit-sha>",
  "generated_at": "<iso8601>",
  "expires_at": "<iso8601>",
  "violations": [],
  "artifact": "reports/import-linter.json",
  "artifact_sha256": "<hash>"
}
```

The public `import_architecture_evidence` API reads only the versioned
`nornyx.architecture_report.v1` neutral envelope under an explicit local root.
It rejects traversal, symlinks, malformed JSON, duplicate keys, oversized or
deep payloads, schema errors, and inconsistent pass status before hashing the
exact report bytes. ADR-0030 records why raw vendor formats and tool execution
are outside this program.

## Rules And Fixed Checks

- `ARCH-001` (error): change with `impacts.architecture equals major` requires
  `evidence contains architecture_decision_record` + `approvals
  references_role architect` (the brief's example, verbatim expressible).
- `ARCH-010` (error): declared required checks require normalized evidence.
  The fixed `architecture_conformance.v1` check performs the relational match
  and verifies tool, schema, pass status, subject revision, freshness, local
  artifact, and SHA-256 content binding.
- `ARCH-020` (error): `constraints[].verified_by exists`.
- Entity references, duplicate IDs, layer direction, constraint verifiers,
  architecture exceptions, and one-evidence-record-per-check are fixed
  structural checks with stable diagnostics.
- Exceptions: standard governed-exception mechanics (owner = `authority`,
  compensating controls, expiry) via `exception_management`; architecture
  drift = generated-artifact drift (existing `nornyx drift`) + declared-vs-
  evidence mismatches surfaced by ARCH-010/ARCH_EVIDENCE_STALE_REVISION.

## Architecture Radar

Status: `rejected_with_ADR` for the current program. ADR-0030 requires a new,
separately approved program and a representative evidence corpus before this
candidate can re-enter. No radar command, source parser, repository heuristic,
or inferred architecture exists in Nornyx.

## Packaged Surface

- module: `nornyx/profiles_data/module_architecture_conformance.yaml`;
- profile: `nornyx/profiles_data/architecture_governance.yaml`;
- declaration/evidence/report schemas: root and bundled exact copies;
- executable contract: `examples/architecture_governance.nyx`;
- assurance: `tests/test_architecture_governance.py`.

The profile is appended to the built-in profile catalog but is not inserted
into the legacy `DOMAIN_PROFILE_NAMES` projection API because its contributed
blocks have no truthful v0.3 representation.
