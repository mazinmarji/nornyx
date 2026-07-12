# 11 - Migration and Compatibility

## 1. Current authority and future target

Today, `nornyx/profiles.py` is authoritative for profile names, starter
generation, six v0.3 domain dictionaries, stability, and compatibility.
`profiles/*.yaml` is not loaded and is not packaged. Tests treat Python as the
source and the six domain YAML files as mirrors. The five base YAML files are
descriptive metadata with a different shape.

Future migration may make packaged v1 profile files authoritative, but that is
PR 2 or later. PR 1 adds no loader, no `packs_data`, and no migration of built-in
content.

## 2. Starter compatibility

The exact current-main starter baseline, newline evidence, three compatibility
classes, deterministic tests, and intentional-change procedure are normative
in `appendix_STARTER_COMPATIBILITY.md`.

All 11 current profiles are frozen semantically. The demonstrated Windows/
POSIX text translation is the only allowed normalization. A future renderer
must either reproduce the canonical baseline exactly or obtain approval for an
intentional migration. Golden mismatches are investigated, never auto-updated.

## 3. Public compatibility guarantees

- `nornyx profiles` keeps the same 11 names, order, stdout, and exit code.
- `nornyx init --profile <name>` keeps names, flags, output-path behavior, and
  baseline content subject only to the recorded line-ending normalization.
- Existing `.nyx` contracts keep current parser/checker meaning.
- `PROFILE_NAMES`, `BASE_PROFILE_NAMES`, and `DOMAIN_PROFILE_NAMES` remain
  importable with the same values and order.
- `profile_document()` and `write_profile()` keep signatures.
- `profile_pack()`, `profile_pack_catalog()`,
  `profile_compatibility_matrix()`, `validate_profile_pack_catalog()`,
  `validate_profile_conformance()`, and `profile_conformance_report()` keep
  signatures and legacy return shapes for at least one deprecation cycle.

## 4. v1 and v0.3 are separate

The v0.3 schema is frozen. The v1 schema supersedes it without modifying old
meaning. The exact v1-to-v0.3 projection is specified in
`appendix_LEGACY_PROJECTION.md`.

The existing `profile_pack()` compatibility API will return only the exact
schema-valid v0.3 view. Source v1 identity and omitted-field diagnostics are
available through a separate projection-report API; no marker is inserted into
the strict v0.3 object. Projection fails when required semantics would be lost.

New v1-native APIs and CLI inspection will expose the authoritative v1 object.
They are not implemented in PR 1.

## 5. Mirror decision

When built-ins migrate, repo-root `profiles/*.yaml` mirrors will be removed,
not regenerated. A user who needs an export will use a future explicit inspect
or export command. This prevents recreating the dual-source drift that the
framework is intended to eliminate. Reversal requires an identified consumer
and a new decision.

## 6. Deprecation sequence

1. Loader release: constants and legacy functions remain stable; v1-native
   inspection is added.
2. Following release: v0.3 authoring/import is documented as deprecated while
   historical validation and exact projection remain.
3. Later release, with human approval: consider removing direct access to the
   mutable `DOMAIN_PROFILE_PACKS` constant. Function APIs remain.

No deprecation warning or API behavior change is introduced by PR 1.

## 7. Packaging

The four PR 1 draft schemas are synchronized into `nornyx/schemas/` and are
included by the existing `schemas/*.json` package-data glob. Profile YAML files
remain outside the wheel until a future loader PR deliberately adds packaged
data and corresponding compatibility tests.
