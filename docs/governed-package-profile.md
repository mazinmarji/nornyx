# Governed Package Profile

## Purpose

The governed package profile lets Nornyx declare, validate, generate, lock, and
export governed package contracts.

## What a governed package is

A governed package is an inert declarative contract bundle for controlled work.
It describes mission scope, tasks, change boundaries, evidence requirements,
approval gates, artifacts, safety restrictions, installation policy, locks, and
provenance.

## What Nornyx does

- Defines the governed package contract.
- Validates the contract and generated metadata.
- Generates inert artifacts.
- Hash-locks generated outputs.
- Exports portable metadata.

## What Nornyx does not do

- Does not execute packages.
- Does not install packages.
- Does not approve work.
- Does not deploy.
- Does not store secrets.
- Does not operate runtime systems.

## Core concepts

- `mission`: the objective and scope of the governed package.
- `task`: a bounded work item inside the package.
- `change`: the proposed or expected modification or output controlled by the package.
- `evidence_pack`: a declared collection of evidence artifacts required to validate the package.
- `evidence_requirement`: a required proof item, such as a diff, report, or review record.
- `approval_gate`: a declared decision point with required evidence and eligible approver roles.
- `risk_tier`: a declared risk classification such as `low`, `medium`, `high`, or `critical`.
- `agent_assignment`: a responsible actor or role assignment for human, service, or assisted work.
- `execution_surface`: a tool, CLI, service, worker, editor, CI runner, or environment that may produce evidence or artifacts.
- `artifact`: a file, report, patch, manifest, binary, generated output, or evidence object.
- `installation_policy`: a declaration that generated packages are not installed or executable by default.
- `safety_boundary`: declarative restrictions for secrets, production data, execution, writes, deployment, and approval.
- `package_lock`: a hash-lock file proving generated artifact integrity and provenance.
- `provenance`: source identity, generator version, timestamps, content hashes, and profile version.

Execution surfaces are tools, not accountable approvers.

## Safety model

Generated governed packages are inert by default. The required installation policy is:

```yaml
installed: false
executable_by_default: false
requires_explicit_install: true
```

The required safety boundary is:

```yaml
secrets_allowed: false
production_data_allowed: false
autonomous_execution_allowed: false
external_writes_allowed: false
deployment_allowed: false
approval_required: true
```

Unsafe flags fail validation. Installation or execution is a downstream
responsibility and outside the Nornyx runtime.

## Operating modes

| Mode | Input | Output | Mutates source? | Executable? | Purpose |
| --- | --- | --- | --- | --- | --- |
| Generate | `.nyx` contract | inert package artifacts | no | no | contract-first package creation |
| Register existing | existing folder or manifest | lock and registration report | no | no | adopt existing artifacts safely |
| Radar | repo or folder | candidate report or suggested contract | no by default | no | discover governable units |

### Generate mode

Generate mode is contract-first. A `.nyx` governed package contract generates an
inert package directory containing manifests, markdown contracts, provenance, and
a package lock.

### Register existing mode

Register existing mode is artifact-first. Existing files are described,
validated, hash-locked, and made governable without becoming executable.
When the registered source directory is still available, validation re-checks
registered artifact hashes; if that source directory has been moved or deleted,
the portable generated package metadata is still validated but source drift
cannot be re-checked.

### Radar mode

Radar mode is discovery-first. A repository or folder is scanned and Nornyx
proposes candidate governed package contracts and missing controls. Radar output
is advisory only. It does not approve, install, execute, deploy, infer secret
values, upload data, or call external systems. Secret-like material is flagged
without copying values into output.

All three modes create contracts, reports, manifests, locks, and suggestions.
They do not execute, install, approve, deploy, or operate packages.

## Example

```yaml
nornyx: "0.1"
project:
  name: ExampleGovernedPackage

governed_package:
  profile: governed_package
  schema_version: "1.0"
  package_id: gp-example-001
  name: Example governed package
  risk_tier: low
  mission:
    id: mission-example-001
    objective: "Deliver a small controlled documentation update."
  tasks:
    - id: task-example-001
      title: "Prepare documentation change"
      assigned_to: doc_writer
      required_evidence: [doc_diff]
  changes:
    - id: change-example-001
      type: documentation
      expected_artifacts: [artifact-doc-diff]
  evidence:
    requirements:
      - id: doc_diff
        type: diff
        required: true
      - id: review_record
        type: review
        required: true
  approval_gates:
    - id: gate-review
      required_evidence: [doc_diff, review_record]
      eligible_approver_roles: [reviewer]
      denied_approver_types: [execution_surface, ai_tool]
  agent_assignments:
    - id: doc_writer
      role: author
      accountable_actor_type: human_or_service
  execution_surfaces:
    - id: editor-local
      type: editor
      can_approve: false
      produces_evidence: [doc_diff]
  artifacts:
    - id: artifact-doc-diff
      path: artifacts/doc.diff
      type: diff
  installation_policy:
    installed: false
    executable_by_default: false
    requires_explicit_install: true
  safety_boundary:
    secrets_allowed: false
    production_data_allowed: false
    autonomous_execution_allowed: false
    external_writes_allowed: false
    deployment_allowed: false
    approval_required: true
  provenance:
    source_contract: examples/governed_package/basic.nyx
    source_sha256: pending-generation
    generator_version: "1.3.0"
    profile_version: "1.0"
```

## Generated artifacts

- `package_manifest.json`: full governed package manifest.
- `package_lock.json`: source hash, generator metadata, artifact hashes, and manifest hash.
- `AGENTS.md`: responsible role assignments, without approval authority for tools.
- `evidence_contract.md`: declared evidence requirements.
- `approval_contract.md`: approval gates and approver restrictions.
- `safety_boundary.md`: inert installation policy and safety flags.
- `provenance.json`: source contract identity, generator version, timestamps, and hashes.

Register existing mode also writes `registration_report.json`. Radar mode writes
`radar_report.json` and can optionally write a suggested `.nyx` contract.

## Validation rules

Validation fails when:

- Required governed package fields are missing.
- An approval gate has no required evidence.
- Approval gates reference unknown evidence.
- An execution surface or AI tool is listed as an approver.
- An execution surface declares `can_approve: true`.
- `installation_policy.installed` is true.
- `installation_policy.executable_by_default` is true.
- `installation_policy.requires_explicit_install` is false.
- Any safety flag allows secrets, production data, autonomous execution, external writes, or deployment.
- Approval is not required.
- Artifacts are missing `id`, `path`, or `type`.
- Existing registered artifacts are missing `sha256`.
- Provenance is missing source hash, generator version, or profile version.
- Package lock hashes do not match generated artifacts.

## CLI usage

Generate an inert governed package:

```bash
nornyx package generate examples/governed_package/basic.nyx --out dist/governed-package
```

Validate a contract:

```bash
nornyx package validate examples/governed_package/basic.nyx
```

Validate a generated manifest or directory:

```bash
nornyx package validate dist/governed-package/package_manifest.json
nornyx package validate dist/governed-package
```

Register an existing artifact directory:

```bash
nornyx package register ./some-existing-artifacts --contract examples/governed_package/register_existing.nyx --out dist/registered-package
```

Run radar discovery:

```bash
nornyx package radar ./example-repo --out dist/radar_report.json
nornyx package radar ./example-repo --suggest-contract --out dist/radar_suggested.nyx
```
