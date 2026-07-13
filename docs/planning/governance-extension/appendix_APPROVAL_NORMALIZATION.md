# Appendix - Normalized Approval Model (F-03)

Status: implemented normative internal contract. Runtime normalization,
schema validation, retained-source revalidation, and fail-closed role lookup
enforce this representation.

## Normalized representation

The legacy `nornyx.normalized_approval.v1` compatibility view and the
trust-boundary `nornyx.normalized_approval.v2` representation share these
semantic fields. V2 additionally retains a deterministic path-derived source
fallback and source-consistency binding:

```text
id
required_roles
eligible_roles
denied_actor_types
denied_execution_surfaces
required_evidence
actions_requiring_approval
timing
accountable_authority
revision_binding (exact)
exact_revision_required
invalidation_conditions
expires_after
expires_at
resolution
normalization_diagnostics
source {shape, path, raw, role_field, fallback_id, binding} (v2)
```

The complete raw source value and source path are retained. This is essential
for legacy prose and boolean requirement fields whose meaning cannot safely be
invented. Normalization makes fields comparable; it does not manufacture an
approver or grant authority.

When raw source has no intrinsic identity, v1 keeps the caller-supplied
fallback for public compatibility, but verifiable v2 derives one as
`approval:` plus the first 24 hexadecimal characters of SHA-256 over canonical
JSON containing only `shape` and `path`. Neither the claimed normalized ID nor
an in-band caller fallback participates in verification.

## Repository-grounded mappings

| Current shape | Deterministic mapping |
|---|---|
| Ordinary `approvals[].name` | `id`; the name is a gate identity, not an eligible role |
| Ordinary/generated `approvals[].required_for` | `actions_requiring_approval` |
| Governed-package `approval_gates[].id` | `id` |
| `required_evidence` | `required_evidence` |
| `eligible_approver_roles` | `eligible_roles` |
| Legacy governed aliases `approver_roles`, `approvers`, `eligible_approvers` | union into `eligible_roles` in field-table order, then first-seen order |
| `denied_approver_types: [ai_tool]` | `denied_actor_types` |
| `denied_approver_types: [execution_surface]` | `denied_execution_surfaces` |
| `contracts[].approval` | `reference_only`; resolves to the named ordinary gate later |
| `goals[].approval` prose | `legacy_text_preserved`; raw text retained, no role inferred |
| `approval_required` / `requires_approval` booleans | `requirement_only`; raw boolean and path retained, no authority inferred |

Structured fields map directly: `required_roles`,
`accountable_authority`, exact `revision_binding`, the independent
`exact_revision_required` requirement, `invalidation_conditions`, relative
`expires_after`, and absolute `expires_at`. Relative and absolute expiry are
never collapsed into one field. Ordinary contract schemas allow
open named mappings, so unknown non-role fields remain in `source.raw`. Unknown
role-bearing fields are errors until added to this table by an ADR.

## Conflict behavior

- Duplicate roles/evidence/actions are de-duplicated in first-seen order and
  produce an informational diagnostic.
- Role, denial, evidence, and action values must be non-empty strings;
  malformed values are omitted and make normalization invalid.
- `accountable_authority` must be a canonical non-empty source string. It is
  never stringified from another YAML type and explicit non-human identities
  are intrinsically invalid.
- `exact_revision_required` must be boolean and `expires_after` must be a
  non-empty duration string when present.
- Every required role must appear in the eligible-role set; required roles
  with an empty eligible-role set are invalid.
- Governed-package gates missing all known eligible-role fields are errors.
- Non-human categories and explicit identities such as `ai_tool`,
  `execution_surface`, `tool:*`, `agent:*`, `model:*`, `connector:*`, and
  `system:*` can never be eligible approvers. If an actor category is both
  eligible and denied, normalization is invalid.
- Governed-package gates with no roles, evidence, or actions are invalid.
- Missing eligible roles in ordinary or legacy reference shapes with no
  required-role claim remain an explicit unresolved fact; no default human
  role is invented.
- Contradictions fail normalization. The loader and evaluator do not compose
  or authorize an invalid normalized approval.
- Across composition layers, non-empty eligible-role sets intersect. A
  disjoint intersection or a required role excluded by another layer is a
  fatal monotonicity conflict; authority sets are never unioned.
- Effective composition uses `nornyx.effective_approval.v1`, retains bounded
  flattened source approvals and pack provenance, and is independently
  replayed by `trusted_effective_approval` as specified by ADR-0032. Built-in
  lineage is resolved from packaged resources; other tiers require an explicit
  authoritative registry. Effective reporting artifacts are not document
  approval declarations.

`references_role` operates only on normalized `required_roles` and
`eligible_roles`. Approval names, action names, prose, and accountable
authority are not silently treated as eligible roles.

## Fixture coverage

The approval fixture covers ordinary approvals, generated starters, the
current governed-package gate, all four role-field spellings accepted by
`APPROVER_FIELDS`, contract references, goal prose, boolean requirements,
duplicates, empty gates, unknown role fields, and eligible/denied conflicts.
Every normalized record validates against the packaged internal schema and keeps
the original source value byte-for-value after YAML parsing.

## F-03 closure

Resolution: implemented. Role lookup is no longer an unspecified operator
shortcut; every supported repository shape has a deterministic, loss-aware
map, and claimed canonical data is re-derived from retained source before use.
