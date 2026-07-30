# Releasing Nornyx

Nornyx publishes to [PyPI](https://pypi.org/project/nornyx/) via **GitHub Actions
Trusted Publishing** (OIDC) — there is no API token anywhere. Publishing a GitHub
Release builds the package from the tagged source and pushes it to PyPI
automatically (see [`.github/workflows/release.yml`](.github/workflows/release.yml)).

## Cut a release

1. **Bump the version** in seven equality-enforced locations (keep them in sync — see
   [`docs/VERSIONING.md`](docs/VERSIONING.md)). They are enforced collectively:
   `tests/test_documentation_consistency.py` covers the first five locations,
   `tests/test_governance_compatibility_corpus.py` covers the compatibility fixture,
   `tests/test_governance_extension_spec.py` covers the starter-golden fixture, and
   `tests/test_manifest_metadata.py` provides additional package/manifest redundancy:
   - `pyproject.toml` → `project.version = "X.Y.Z"`
   - `nornyx/__init__.py` → `__version__ = "X.Y.Z"`
   - `manifest.json` → top-level `"version": "X.Y.Z"`
   - `docs/VERSIONING.md` → the active package-version declaration
   - `README.md` → the active `nornyx@vX.Y.Z` source-install pin
   - `tests/fixtures/governance_compatibility/manifest.json` →
     `baseline.package_version = "X.Y.Z"`
   - `tests/fixtures/governance_extension/starter_golden/manifest.json` → top-level
     `nornyx_version = "X.Y.Z"`

2. **Add a `CHANGELOG.md` entry** under a new `## [X.Y.Z] - YYYY-MM-DD` heading.
   The changelog is updated for every release, but it is not one of the seven
   equality-enforced fields; retain historical changelog versions. Nested per-profile
   fixture versions are historical generation metadata. Historical and evidence-bound
   versions must not be bulk-rewritten.

3. **Sanity-check locally** (optional but cheap):
   ```bash
   python -m pytest -q
   python -m build && python -m twine check dist/* && rm -rf dist build *.egg-info
   ```

4. **Commit, tag, and create the GitHub Release** — the release is what triggers
   publishing:
   ```bash
   git commit -am "Release X.Y.Z: <summary>"
   git tag -a vX.Y.Z -m "vX.Y.Z: <summary>"
   git push origin main --tags
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "<notes>"
   ```

5. The **release** workflow runs: it tests, builds, and publishes to PyPI. If the
   `pypi` GitHub Environment has a required reviewer, approve the run in the repo's
   **Actions** tab. Watch it with:
   ```bash
   gh run watch -R mazinmarji/nornyx
   ```

6. **Verify** from a clean environment:
   ```bash
   python -m venv /tmp/v
   /tmp/v/bin/pip install "nornyx==X.Y.Z"        # Windows: \Scripts\pip.exe
   /tmp/v/bin/nornyx check examples/governed_delivery_control_plane.nyx
   ```

## Rules that bite

- **A version is immutable on PyPI.** You can never re-upload `X.Y.Z`, even after
  deleting it. If a published build is wrong, bump to the next patch and release
  again — do not try to overwrite.
- **Let CI build the artifact.** Don't `twine upload` by hand; the trusted-publish
  workflow is the source of truth and guarantees the artifact matches the tag.
- The **package version is independent of the language/schema version** (still
  1.0). A package patch can ship without changing the contract language.

## One-time setup (already done — for reference)

Trusted publishing is configured. If it ever needs to be re-established:

- **PyPI** → *Account → Publishing* → add a trusted publisher:
  project `nornyx`, owner `mazinmarji`, repo `nornyx`, workflow `release.yml`,
  environment `pypi`.
- **GitHub** → *Settings → Environments* → `pypi`, optionally with a required
  reviewer so every publish needs a human approval (matches Nornyx's own
  "human approval before release" posture).
