# 11 - Migration and Compatibility

Status: implemented compatibility contract.

## 1. Current authority

The 12 authoritative v1 profile packs live under `nornyx/profiles_data/` and
ship in the wheel. Runtime profile inspection, starter generation, governance
resolution, and legacy projection all read that packaged source. The former
repo-root `profiles/*.yaml` mirrors were removed, so there is no writable
second source of profile truth.

`nornyx/profiles.py` remains the public compatibility facade. It delegates to
the authoritative packs while preserving the established constants, starter
APIs, projection APIs, and validation entry points.

## 2. Starter compatibility

The exact starter baseline, newline evidence, compatibility classes,
deterministic tests, and intentional-change procedure are normative in
`appendix_STARTER_COMPATIBILITY.md`.

The 11 profiles present before this program retain their approved semantics.
The additive `architecture_governance` profile has its own reviewed golden.
Golden mismatches fail tests and are never accepted automatically. Any
intentional migration requires a recorded reason, updated golden hashes, and
human review.

## 3. Public compatibility guarantees

- `nornyx profiles` preserves the 11 established names and adds
  `architecture_governance` without renaming an existing profile.
- `nornyx init --profile <name>` preserves flags, output-path behavior, and
  approved starter content.
- Existing `.nyx` contracts preserve parser/checker meaning.
- `PROFILE_NAMES` remains the additive 12-profile catalog.
- `BASE_PROFILE_NAMES` and `DOMAIN_PROFILE_NAMES` preserve their documented
  legacy categories and order.
- `profile_document()` and `write_profile()` preserve their signatures.
- `profile_pack()`, `profile_pack_catalog()`,
  `profile_compatibility_matrix()`, `validate_profile_pack_catalog()`,
  `validate_profile_conformance()`, and `profile_conformance_report()` preserve
  their documented legacy return shapes.

The public API compatibility floor and deprecation policy are documented in
`docs/GOVERNANCE_CLI_AND_API.md`. No active governance API deprecation is part
of this program.

## 4. v1 and v0.3 separation

The v0.3 schema remains frozen. The v1 schema supersedes it without changing
historical meaning. The exact v1-to-v0.3 projection is specified in
`appendix_LEGACY_PROJECTION.md` and implemented by the compatibility facade.

Legacy projection returns only the schema-valid v0.3 object. Source v1
identity and omitted-field diagnostics remain in the separate projection
report; no marker is inserted into the strict v0.3 object. Projection fails
closed when required legacy semantics would be lost. V1-native APIs and CLI
inspection expose the complete authoritative object.

## 5. Mirror decision

Repo-root profile mirrors are `superseded` and removed. Users can inspect
authoritative objects through the CLI/API instead of maintaining exported
copies as runtime sources. Reversal requires an identified consumer, a new
ADR, and dual-source drift controls.

## 6. Import and deprecation boundary

No v0.3 authoring/import shim is required by the current program. A later shim
would be a `future_proposal_outside_current_program` and would require explicit
provenance, compatibility tests, and human approval. Historical v0.3
validation and exact projection remain supported.

## 7. Packaging and assurance

Authoritative profile/module packs and all governance schemas are included in
sdist and wheel package data. The wheel smoke test installs the built artifact
in isolation, enumerates all 12 profiles and six modules, validates governance
evidence, and confirms that no network access is used. Compatibility corpus
tests cover established starters, legacy projections, example contracts, and
approved intentional migrations.
