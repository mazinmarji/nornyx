# 08 — Architecture Governance Design

## Positioning

An **optional profile** (`architecture_governance`) composed from
`change_control`, `architecture_conformance` (new module), `evidence_integrity`,
`exception_management`, `human_approval`. Nornyx declares which architecture
checks are required, what evidence they must produce, binds evidence to exact
revisions, validates presence/integrity/freshness, applies gates — and does
**not** parse source code, infer architecture, detect duplicate code, or
replace ArchUnit / import-linter / dependency-cruiser / Semgrep / CodeQL /
SonarQube / compiler checks.

## Governed vocabulary (blocks contributed by the profile)

```yaml
architecture:
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

## Normalized architecture evidence (`nornyx.architecture_evidence.v1`)

Exactly the brief's shape, plus freshness:

```json
{
  "schema": "nornyx.architecture_evidence.v1",
  "check_id": "dependency-boundaries",
  "tool": "import-linter",
  "tool_version": "2.0",
  "status": "pass",
  "subject_revision": "<commit-sha>",
  "generated_at": "<iso8601>",
  "violations": [],
  "artifact": "reports/import-linter.json",
  "artifact_sha256": "<hash>"
}
```

New JSON schema file; the evidence-import pattern follows the scanner branch's
adapter design (parse a report file; never execute the tool) — after that
branch merges, architecture evidence importers register alongside
syft/gitleaks parsers.

## Profile rules (samples, all in the doc 05 rule language)

- `ARCH-001` (error): change with `impacts.architecture equals major` requires
  `evidence contains architecture_decision_record` + `approvals
  references_role architect` (the brief's example, verbatim expressible).
- `ARCH-010` (error): every `required_checks[].id` must have a matching
  evidence record with `status equals pass` — presence is a rule; matching
  `subject_revision` to the change's `revision_binding.revision` is a
  structural check (`ARCH_EVIDENCE_STALE_REVISION`) since it's relational.
- `ARCH-020` (error): `constraints[].verified_by exists`.
- `ARCH-030` (warning): components not marked `canonical` referenced by >N
  consumers — **dropped from v1**: needs counting over references; revisit
  only if the rule language ever grows `min_count` over joins (scope guard).
- Exceptions: standard governed-exception mechanics (owner = `authority`,
  compensating controls, expiry) via `exception_management`; architecture
  drift = generated-artifact drift (existing `nornyx drift`) + declared-vs-
  evidence mismatches surfaced by ARCH-010/ARCH_EVIDENCE_STALE_REVISION.

## Architecture Radar

Advisory discovery ("these dirs look like undeclared components") mirrors
`package radar`'s proposal-only pattern. **Not MVP** — it needs heuristics over
repo layout, which flirts with the source-analysis non-goal. Deferred; listed
as a rejected-for-now alternative worth revisiting in doc 14.
