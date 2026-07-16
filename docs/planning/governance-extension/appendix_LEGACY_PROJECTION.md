# Appendix - v1 to Legacy v0.3 Projection (F-04)

Status: implemented normative compatibility contract. The production facade
uses this exact projection and keeps loss diagnostics out of the strict v0.3
object.

## Version separation

`nornyx.profile_pack.v0_3` and `nornyx.profile_pack.v1` are different formats.
The historical `domain_profile_pack.schema.json` remains frozen with
`version: v0.3`, `core_surface: v0.2`, `status: optional_profile`, and
`additionalProperties: false`. A complete v1 pack does not and must not claim
to validate against it.

The v1 schema uses `schema: nornyx.profile_pack.v1`, SemVer pack versions,
explicit core ranges, structured rules, starter fragments, provenance, and
integrity metadata. These meanings are never added to the v0.3 schema.

## Projection boundary

```text
authoritative nornyx.profile_pack.v1
  -> explicit, deterministic projection
  -> exact nornyx.profile_pack.v0_3 legacy view
  + separate projection report
```

The legacy view contains only the 13 fields accepted by the frozen schema:

```text
name version core_surface status purpose domain required_blocks
recommended_blocks graph_node_kinds validation_rules conformance
non_goals core_concepts
```

`version`, `core_surface`, and `status` are literal legacy constants because
they describe the projected view, not the source pack. Source identity is never
inserted into that object: an extra `projected_from` field would violate the
strict legacy schema.

Source identity, source version, omitted fields, and loss diagnostics live in a
separate `nornyx.profile_pack_projection_report.v1` sidecar. The
`profile_pack_projection_report(name)` API exposes it. The existing
`profile_pack(name)` API continues returning the exact v0.3-shaped dictionary
for one deprecation cycle; a new v1-native API returns the authoritative pack.

## Deterministic field mapping

| v0.3 field | v1 source |
|---|---|
| `name` | `name` |
| `version` | literal `v0.3` |
| `core_surface` | literal `v0.2` |
| `status` | literal `optional_profile` |
| `purpose`, `domain` | same-named fields |
| `required_blocks`, `recommended_blocks` | same-named fields |
| `graph_node_kinds` | `graph.node_kinds` |
| `validation_rules` | `compatibility.legacy_v0_3.validation_rules` prose |
| `conformance` | `compatibility.legacy_v0_3.conformance` |
| `non_goals` | `non_goals` |
| `core_concepts` | `compatibility.legacy_v0_3.core_concepts` |

Structured v1 rules are never converted to prose and never presented as
legacy enforcement. The compatibility declaration must list every omitted v1
field. Typical omissions include modules, defaults, evidence, approvals,
evaluations, starter fragments, structured rules, compatibility/conflicts,
provenance, and integrity.

## Failure and diagnostics

Projection fails when:

- the source is not a valid `nornyx.profile_pack.v1` profile;
- legacy projection is absent, disabled, or not `exact_v0_3_view`;
- a required legacy field cannot be produced;
- a field listed in `must_preserve` is also listed as omitted;
- projection output fails the frozen v0.3 schema;
- the source version or core range is invalid.

Loss that is explicitly declared and not in `must_preserve` produces
`PROFILE_PROJECTION_LOSS_REPORTED` in the sidecar. A must-preserve conflict
fails with `PROFILE_PROJECTION_REQUIRED_FIELD_OMITTED`. There is no silent
best-effort projection.

## Deprecation strategy

The legacy API remains stable while built-ins migrate. Documentation directs
new authors to v1. The projection report makes loss visible. Removal of direct
v0.3 authoring support requires a later release decision and migration notice;
the frozen schema remains available for historical validation.

## F-04 closure

Resolution: implemented. Fixtures prove a valid v0.3 pack, a valid v1 pack,
an exact schema-valid projection, and a projection that must fail because
unsupported semantics were marked must-preserve.
