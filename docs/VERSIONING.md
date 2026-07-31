# Nornyx Versioning

Nornyx carries several **independent** version axes. The most important rule:

> The **package (distribution) version** is independent of the **language/schema version**.
> A package release can ship without changing the contract language, and vice versa.

This separation is deliberate. It lets Nornyx fix bugs, add commands, or repackage without forcing
every existing `.nyx` contract to migrate, and it lets the language evolve on its own cadence.

## Version axes

| Axis | Current | Bumped when… | Source of truth |
| --- | --- | --- | --- |
| **Package (distribution)** | `1.10.0` | any release of the Python package (SemVer: minor for backward-compatible features, patch for fixes) | `pyproject.toml` `version`, `nornyx/__init__.py` `__version__`, `manifest.json` `version` — **all three must match** |
| **Agentic integration SPI** | `1.2` | the supported in-process `nornyx.agentic` integration contract changes; additive capabilities advance the minor and breaking changes advance the major | `nornyx.agentic.SPI_VERSION` |
| **Language / schema** | `1.0` | the `.nyx` contract language or its schema targets change in a way authors must know about | `manifest.json` `language_version`, `nornyx.cli schema --version` |
| **`agentic_network_governance` module** | `0.2.0` | the composed agentic-network governance module changes its catalog surface (bound by a `migration:` marker) | `nornyx/profiles_data/module_agentic_network_governance.yaml` `version` |
| **Agentic schema targets** | `v1` | a new major schema id is minted (breaking) | `$id` tokens: `agentic_network_v1`, `agentic_capabilities_v1`, `agentic_network_lock_v1`, `agentic_runtime_events_v1` |
| **Network lock format** | `1.0` | the lock byte format changes | `LOCK_FORMAT_VERSION`, `LOCK_SCHEMA_ID` (`nornyx/agentic_artifacts.py`) |
| **Generation format** | `1.0` | the generated-artifact layout changes | `GENERATION_FORMAT_VERSION` (`nornyx/agentic_artifacts.py`) |
| **Runtime-events schema** | `1.1` | the emitted/validated evidence event schema changes | `RUNTIME_EVENTS_SCHEMA_VERSION`, `RUNTIME_EVENTS_SCHEMA_ID` (`nornyx/agentic_artifacts.py`) |

## Rules

1. **An active package-version synchronization touches exactly seven equality-enforced
   locations**:
   - `pyproject.toml` — `project.version`
   - `nornyx/__init__.py` — `__version__`
   - `manifest.json` — top-level `version`
   - `docs/VERSIONING.md` — the active package-version declaration
   - `README.md` — the active `nornyx@vX.Y.Z` source-install pin
   - `tests/fixtures/governance_compatibility/manifest.json` —
     `baseline.package_version`
   - `tests/fixtures/governance_extension/starter_golden/manifest.json` — top-level
     `nornyx_version`

   These locations are enforced collectively by multiple test modules:
   `tests/test_documentation_consistency.py` covers the first five;
   `tests/test_governance_compatibility_corpus.py` covers the compatibility fixture;
   `tests/test_governance_extension_spec.py` covers the starter-golden fixture; and
   `tests/test_manifest_metadata.py` provides additional package/manifest redundancy.
   The release flow in [`../RELEASING.md`](../RELEASING.md) lists all seven.
   `CHANGELOG.md` is updated for every release, but it is not one of these seven
   equality-enforced fields; historical changelog versions are retained. Nested
   per-profile fixture versions are historical generation metadata. Historical and
   evidence-bound versions must not be bulk-rewritten.
2. **Semantic Versioning for the package.** Backward-compatible functionality (new commands,
   schemas, artifact formats that do not break existing contracts) is a **minor** bump; bug fixes
   are a **patch**. AN-002…AN-006 were additive, so the next release after 1.6.2 is **1.7.0**
   (a minor bump, not a patch).
3. **Language/schema version changes are separate** and are announced in `CHANGELOG.md` and the
   schema docs, not implied by a package bump.
4. **Schema `$id` tokens are permanent.** A breaking change to a schema mints a new `_v2` id; it
   never rewrites `_v1` in place. Locks and evidence bind to exact ids.
5. **Runtime-events minor versions are selected by the lock.** Runtime-events
   1.1 remains under the permanent v1 schema id because its exact 1.0 branch is
   retained. New locks default to 1.1; verification reconstructs supported
   historical 1.0 locks and artifact hashes using their declared version.
6. **Implementation and release version changes are separate review units.**
   Additive work is recorded under `CHANGELOG.md`'s Unreleased section without
   partially changing the seven synchronized package-version locations. The
   release PR that cuts the distribution advances all seven together. The
   additive SPI 1.2 construction-state capability therefore leaves the working
   package version at 1.10.0; the recommended later release is Nornyx 1.11.0.
   Tagging and publication remain separate authorized actions.

## Supported Python

The package advertises `requires-python = ">=3.10"` and is tested on **3.10, 3.11, 3.12, 3.13**.
The Linux test job runs the full matrix; the expensive quality, native-framework, and Windows jobs
run on a pinned subset to control cost (see `.github/workflows/ci.yml`).
