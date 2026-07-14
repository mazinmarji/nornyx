# 06 — Composition and Precedence Semantics

Status: implemented normative composition contract.

## 1. Merge order (fixed, deterministic)

```text
L0 core defaults
L1 modules, in dependency topological order (ties: lexicographic pack id)
L2 the single profile
L3 organization policy module (optional, tier: org)
L4 project contract (.nyx)
post-composition: project exception declarations (validated records, never overrides)
```

Composition layers L0-L4 see earlier layers' output. Exception declarations
cannot alter that output. The same inputs always produce the same effective
model (no dict-ordering, environment, or timestamp dependence); this is a
tested invariant (doc 13 "deterministic merge").

## 2. Merge behavior by shape

| Shape | Behavior |
|---|---|
| Mappings (non-named) | Keys are visited lexicographically. Deep merge; later layer wins **per scalar key** only where override is permitted (§4); collisions on safety-relevant keys follow §5 |
| Lists of named/id'd items (policies, approvals, evidence requirements, rules, goals) | Merge by `name`/`id`. New id ⇒ append (stable order: layer, then id). Same id, different layer ⇒ permitted-override check (§4). Same id twice **within one layer** ⇒ fatal `DUPLICATE_ID` |
| Plain scalar lists (deny rules, required evidence names, non_goals) | **Union, never removal** (§5); first declaration fixes stable output position |
| Scalars | Later layer overrides if the key is override-permitted; otherwise fatal conflict |

Dependencies are resolved before merge by deterministic topological order with
lexicographic module-id tie breaking. Missing dependencies and cycles are
fatal. Starter fragments follow layer order, then target, then fragment id;
two fragments attempting incompatible scalar ownership are fatal. Every merged
element retains `{source_id, source_version, layer, source_tier, source_path}`
provenance. Provenance is accumulated, never overwritten.

## 3. Fatal-by-default conflict cases

Duplicate pack identity within a tier; pack dependency cycle (module→module or
profile→module chains); profile name collision within a tier; unsatisfied
`compatible_core`; declared conflicts between selected inputs; unknown rule
operator; unknown pack format version; lock mismatch; two packs defining the
same block schema fragment with different content (no silent last-wins for
schemas). "Fatal" = check/init exit non-zero with a stable code; there is no
`--force` for safety conflicts.

`requires_review_with` (existing matrix concept) composes as a **warning**
diagnostic, preserving current advisory semantics.

## 4. Override permissions

A layer element is overridable only if the defining layer marked it so:

```yaml
defaults:
  budgets:
    - name: DefaultBudget
      max_tokens: 100000
      overridable: [max_tokens]     # project may change ONLY these fields
```

Absent `overridable`, project redefinition of the same id is a fatal conflict
with a diagnostic telling the author to use a different id.
Budget conflicts specifically: numeric fields may always be **tightened**
(lower max) by later layers without permission; raising requires
`overridable`.

`overridable` is limited to direct scalar fields of entries under `defaults`.
Nested paths, wildcards, list replacement, schema fields, rule fields, denials,
evidence, and approval requirements cannot be marked overridable. Extending
this permission surface requires a new ADR.

## 5. Monotonic safety semantics

- Deny rules: union across layers. A later layer **cannot remove** an earlier
  deny. There is no `remove:` syntax at all — absence of syntax is the
  enforcement (nothing to bypass), plus the composer asserts
  `denies(effective) ⊇ denies(core ∪ modules ∪ profile)` as a final invariant
  check (defense in depth; tested adversarially).
- Required evidence: accumulate. Mandatory core evidence and module-required
  evidence cannot be dropped; contracts can add.
- Approvals: accumulate; approval gates can gain required evidence and
  approver restrictions, never lose them. Non-empty eligible-role sets
  intersect; disjoint sets or required roles excluded by another layer are
  fatal conflicts. Exact-revision requirements combine with logical OR, while
  conflicting non-empty relative expiry requirements fail closed.
  `denied_approver_types` core set
  (`ai_tool`, `execution_surface` — matching shipped governed-package
  semantics) is always present and non-removable.
- Non-goals / safety boundary: the core safety non-goals list (today's
  `PROFILE_NON_GOALS`) is injected at L0 and union-only thereafter — packs
  missing it fail pack validation (preserves
  `validate_profile_pack_catalog`'s current check, but structurally).

## 6. Governed exception declarations

```yaml
exceptions:
  schema: nornyx.governance_exceptions.v1
  source: project_contract
  entries:
    - id: EXC-2026-004
      control: project.architecture_review
      reason: Legacy module migration in flight.
      scope: [component:legacy]
      risk_tier: high
      requester: user:legacy_owner
      accountable_owner: user:risk_owner
      approving_authority: user:chief_architect
      compensating_controls: [control:quarterly_architecture_review]
      evidence: [exception_review_record]
      starts_at: "2026-07-01T00:00:00Z"
      expires_at: "2026-12-31T00:00:00Z"
      renewal_policy: manual_reapproval
      closure_evidence: []
      status: approved
```

This block is a project-owned declaration and evidence record, not an engine
relaxation mechanism. The targeted control continues to evaluate unchanged:
Nornyx never downgrades, ignores, approves, renews, or applies a failure because
an exception is present. Missing or malformed fields fail schema and structural
validation. Core namespaces, reserved governance diagnostic namespaces and
known core control/rule ids cannot be named as exceptable controls. Packs
cannot ship project exceptions.

Intervals are half-open (`starts_at <= t < expires_at`) and evaluated only
against an explicit checker time. Expired and closed records require passing
closure evidence. Active or approved records with the same control, intersecting
scope, and intersecting time fail closed. Renewal is a distinct record with a
`renews` reference, a non-overlapping interval, and new passing human-approval
evidence named by `renewal_approval_evidence`. Each proof is a single-use,
exactly typed `approval_record` with a unique artifact/hash, is absent from the
full predecessor chain, names the renewal authority as producer, and is
generated no earlier than the predecessor start and no later than renewal
activation. A normalized human approval gate must explicitly govern
`renew_exception:<new-exception-id>`, authorize the declared renewal authority,
and require exactly that evidence set; renewal is never automatic.

## 7. ADR-0022 — Composition model decision

Options considered:

| Option | Verdict |
|---|---|
| A. One profile + many modules | **Adopted** |
| B. Multiple composable profiles | Rejected for v1: today's compatibility matrix already flags most cross-domain pairs "requires_review_with"; free composition multiplies conflict surface (duplicate starters, colliding defaults) for no demonstrated user need. |
| C. Primary profile + secondary overlays | Rejected for the current program: an overlay is a module under another name; no new mechanism is justified. |

Rationale: modules already give reuse; a single profile keeps starter
generation, terminology, and identity unambiguous. The registry API keeps a
plural internal collection for uniform implementation, not as authorization
for multiple active profiles. Re-entry requires a new ADR, compatibility
proof, and human approval. Existing contracts declare exactly one
`project.profile`, so A is also the zero-migration choice.
