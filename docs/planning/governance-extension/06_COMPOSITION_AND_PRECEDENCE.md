# 06 — Composition and Precedence Semantics

Status: implemented normative composition contract.

## 1. Merge order (fixed, deterministic)

```text
L0 core defaults
L1 modules, in dependency topological order (ties: lexicographic pack id)
L2 the single profile
L3 organization policy module (optional, tier: org)
L4 project contract (.nyx)
L5 explicit project exceptions (contract `exceptions:` block)
```

Later layers see earlier layers' output. The same inputs always produce the
same effective model (no dict-ordering, environment, or timestamp dependence);
this is a tested invariant (doc 13 "deterministic merge").

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
with a diagnostic telling the author to use a different id or an exception.
Budget conflicts specifically: numeric fields may always be **tightened**
(lower max) by later layers without permission; raising requires
`overridable` or an exception.

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

## 6. Governed exceptions (the only relaxation path)

```yaml
exceptions:
  - id: EXC-2026-004
    target: org.acme.arch_governance/ARCH-001   # exactly one rule/control id
    accountable_owner: legacy_platform_owner
    approving_authority: chief_architect        # role that must appear in approvals
    reason: Legacy module migration in flight.
    scope: ["src/legacy/**"]
    compensating_controls: [quarterly_architecture_review]
    starts_at: "2026-07-01T00:00:00Z"
    expires: "2026-12-31"
    closure_evidence: [legacy_migration_closeout]
```

Semantics: the targeted rule still evaluates; on failure within scope the
diagnostic downgrades to `warning` with the exception attached (visible, never
silent). Missing any field ⇒ exception invalid ⇒ rule stays `error`. Expired ⇒
ignored with its own `EXCEPTION_EXPIRED` error. Exceptions cannot target core
checker rules (checker codes are outside the exceptable namespace) and cannot
target deny-list membership. Packs cannot ship exceptions; only L4 contracts
declare them, and `exception_management` module rules can require approval
evidence for each exception.

`starts_at` and `expires` are evaluated against an explicit checker time input;
tests inject it. The evaluator does not sample wall-clock time inside rule
evaluation. Closure evidence is mandatory when an exception is expired or
closed. Invalid, overlapping, or ambiguous exception scope fails closed.

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
