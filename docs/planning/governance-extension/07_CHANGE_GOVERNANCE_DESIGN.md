# 07 — Change Governance Design

Status: implemented by the `change_control` governance module and reconciled
governed-package projection.

## ADR-0021 — Where does `Change` live?

| Option | Assessment |
|---|---|
| New core concept | Rejected. Requires language-schema rev (0.1/0.2/1.0 all frozen), forces every contract to acknowledge changes, and repository evidence shows change semantics living happily inside a profile (`governed_package.changes`) today. Fails the "universal enough" bar because many governed projects (docs sites, eval-only projects) never model discrete changes. |
| Extension block only | Rejected as primary: loses reuse across profiles; each profile would redefine change fields. |
| Governed-package-only concept | Rejected: architecture governance (doc 08) and release control need the same shape; duplicating guarantees the "two incompatible change definitions" failure the brief forbids. |
| **Reusable `change_control` module** | **Adopted.** Declarative block schema + rules; profiles opt in; governed packages reconcile to it. |

## 1. Shared change schema (`nornyx.change.v1`, defined by the module)

The generalized, module-selected model requires `id` and `type` and uses
bounded governance identities. It is intentionally stricter than the frozen
nested governed-package 1.x projection described in section 3:

```yaml
changes:
  - id: change-example-001            # required
    type: documentation               # required
    expected_artifacts: [artifact-x]  # optional (governed-package field, kept)
    # --- optional v1 extension fields (all additive) ---
    purpose: ...
    status: draft | proposed | approved | in_progress | completed | rolled_back | closed
    transition: {from: draft, to: proposed, evidence: [change-record]}
    scope: ["src/pkg/**"]
    excluded_scope: ["src/pkg/legacy/**"]
    affected_assets: [...]
    affected_systems: [...]
    risk_tier: low | medium | high | critical
    blast_radius: component | service | system | organization
    reversibility: reversible | partially_reversible | irreversible
    rollback_required: true
    impacts: {security: none|minor|major, architecture: ..., data: ..., dependency: ...}
    required_controls: [...]
    required_evaluations: [...]
    required_evidence: [...]
    approver_roles: [...]
    separation_of_duties: {author_role: engineer, approver_role: reviewer, disjoint: true}
    revision_binding: {kind: git, revision: <sha>, exact: true, scope_hash: sha256:...}
    approval_invalidated_on: [revision_change, scope_change]
    exceptions: [EXC-...]
    closure_evidence: [...]
```

## 2. Module Rules And Fixed Checks

- `CHANGE_DUPLICATE_ID` (error): change IDs are unique. This relational
  invariant is enforced by the declared, fixed `change_control.v1` structural
  check.
- `CHG-010` (error): when `risk_tier in [high, critical]` require
  `approver_roles` non-empty and `required_evidence` non-empty.
- `CHG-011` (error): when `impacts.architecture equals major` require
  `required_evidence contains architecture_decision_record` (shared with doc 08).
- `CHG-020` (error): when `reversibility equals irreversible` require
  `rollback_required` and a rollback plan artifact. The structural check also
  requires an explicit irreversible authority among the human approver roles.
- `CHG-030` (error): when `revision_binding exists` require both revision and
  scope invalidation conditions.
- `CHG-040` (error): `status equals closed` requires `closure_evidence`.
- Separation of duties enforced by the `separation_of_duties` module
  (author≠approver disjointness is relational → engine-assisted structural
  check with a stable code, declared by the module manifest).

Approval invalidation semantics: Nornyx is static — it cannot watch commits.
The fixed check compares the change's revision and deterministic included and
excluded scope hash with a matching normalized human approval declaration. A
revision or scope mismatch produces `APPROVAL_STALE_FOR_REVISION` or
`APPROVAL_STALE_FOR_SCOPE`. Enforcement-in-time belongs to CI, which reruns
`nornyx check`.

## 3. Reconciliation with `governed_package.changes`

Governed packages retain the exact 1.x compatibility projection: `id` and
`type` must be JSON strings across the full string domain,
`expected_artifacts` remains an optional array of unrestricted JSON strings,
and additional properties remain permitted. `nornyx/governed_package.py` and
both governed-package schema copies implement that frozen boundary.

`change_control` separately owns the strict top-level `nornyx.change.v1`
schema. A project opts into those semantics by selecting the module and
declaring the module-governed top-level `changes` block. Fields placed only in
the nested legacy package projection are package metadata and do not acquire
generalized change authority.

This compatibility adapter is not a second generalized change model: it is a
frozen input projection at the governed-package boundary. Mutation-based
base-vs-head tests compare its accept/reject domain with the 1.5.2 schema,
while generalized-change tests independently prove the strict schema remains
fail-closed.

Rejected alternatives: (a) renaming `expected_artifacts` → `affected_assets`
(breaks shipped contracts; they mean different things — outputs vs touched
assets — keep both); (b) silently applying the strict generalized identity
domain to nested package data (breaks the 1.x contract); (c) treating an
arbitrary legacy extension property as an opt-in (additional properties were
already valid and cannot safely be reinterpreted).

## 4. Migration approach

Implemented in Stage C: module pack, shared schema, fixed checks, rules,
governed-package compatibility adapter, executable example, and adversarial
tests. No governed-package deprecation is needed because its accepted 1.x
domain is preserved rather than migrated.
