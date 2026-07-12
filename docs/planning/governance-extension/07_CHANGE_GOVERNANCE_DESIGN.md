# 07 — Change Governance Design

## ADR-0021 — Where does `Change` live?

| Option | Assessment |
|---|---|
| New core concept | Rejected. Requires language-schema rev (0.1/0.2/1.0 all frozen), forces every contract to acknowledge changes, and repository evidence shows change semantics living happily inside a profile (`governed_package.changes`) today. Fails the "universal enough" bar because many governed projects (docs sites, eval-only projects) never model discrete changes. |
| Extension block only | Rejected as primary: loses reuse across profiles; each profile would redefine change fields. |
| Governed-package-only concept | Rejected: architecture governance (doc 08) and release control need the same shape; duplicating guarantees the "two incompatible change definitions" failure the brief forbids. |
| **Reusable `change_control` module** | **Adopted.** Declarative block schema + rules; profiles opt in; governed packages reconcile to it. |

## 1. Shared change schema (`nornyx.change.v1`, defined by the module)

Required fields kept to the **existing governed-package minimum** so every
shipped contract remains valid:

```yaml
changes:
  - id: change-example-001            # required
    type: documentation               # required
    expected_artifacts: [artifact-x]  # optional (governed-package field, kept)
    # --- optional v1 extension fields (all additive) ---
    purpose: ...
    status: draft | proposed | approved | in_progress | completed | rolled_back | closed
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
    required_evals: [...]
    required_evidence: [...]
    approver_roles: [...]
    separation_of_duties: {author_role: engineer, approver_role: reviewer, disjoint: true}
    revision_binding: {vcs: git, revision: <sha>}
    approval_invalidated_on: [revision_change, scope_change]
    exceptions: [EXC-...]
    closure_evidence: [...]
```

## 2. Module rules (all expressible in the doc 05 rule language)

- `CHG-001` (error): `changes[].id` exists and unique — unique-ness via
  `min_count`/registry check is a composer-level structural check, not a rule
  (relational; stays in engine code, documented).
- `CHG-010` (error): when `risk_tier in [high, critical]` require
  `approver_roles` non-empty and `required_evidence` non-empty.
- `CHG-011` (error): when `impacts.architecture equals major` require
  `required_evidence contains architecture_decision_record` (shared with doc 08).
- `CHG-020` (error): when `reversibility equals irreversible` require
  `rollback_required exists` and `approver_roles references_role` a
  human-accountable role.
- `CHG-030` (error): when `revision_binding exists` require
  `approval_invalidated_on contains revision_change`.
- `CHG-040` (warning): `status equals completed` requires `closure_evidence`.
- Separation of duties enforced by the `separation_of_duties` module
  (author≠approver disjointness is relational → engine-assisted structural
  check with a stable code, declared by the module manifest).

Approval invalidation semantics: Nornyx is static — it cannot watch commits.
The check is evidential: if `revision_binding.revision` differs from the
revision recorded in the approval evidence artifact, `CHG-030`'s companion
structural check flags `APPROVAL_STALE_FOR_REVISION`. Enforcement-in-time
belongs to CI, which reruns `nornyx check`.

## 3. Reconciliation with `governed_package.changes`

Facts (main): governed packages validate changes minimally (list of dicts;
ids referenced by tasks). The scanner branch adds no change fields.

Approach — **one schema, two required-field tiers**:
1. `change_control` owns `nornyx.change.v1` (above). The governed-package
   profile declares `requires_modules: [.., change_control]` after migration
   (PR 5) and states its tier: only `id`/`type` required, all else optional.
2. `governed_package.py` validation delegates change-shape checks to the shared
   schema; its package-specific rules (task→change references,
   expected_artifacts→artifact ids) remain in the profile.
3. No existing `.nyx` file changes meaning: additive optional fields only.
4. Compatibility test: every `examples/governed_package/*.nyx` validates
   unchanged, and the golden manifests are byte-identical.

Rejected alternatives: (a) renaming `expected_artifacts` → `affected_assets`
(breaks shipped contracts; they mean different things — outputs vs touched
assets — keep both); (b) making governed-package changes a *sub*type with its
own schema id (two ids for one concept = the forbidden fork).

## 4. Migration approach

PR 5 (doc 12): module pack + schema + rules + tests; governed-package profile
gains the module dependency behind a compatibility check; docs updated. No
deprecations needed — strictly additive.
