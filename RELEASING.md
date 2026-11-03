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
   **Actions** tab, but only after confirming that the tag gate step ("… is
   not a prerelease and is on main") passed in that run (see
   [Release provenance](#release-provenance)). Watch it with:
   ```bash
   gh run watch -R mazinmarji/nornyx
   ```

6. **Verify** from a clean environment:
   ```bash
   python -m venv /tmp/v
   /tmp/v/bin/pip install "nornyx==X.Y.Z"        # Windows: \Scripts\pip.exe
   /tmp/v/bin/nornyx check examples/governed_delivery_control_plane.nyx
   ```

## Release provenance

Publishing through Trusted Publishing is what makes an official release
*verifiable*, not merely *published*. Two properties are load-bearing in both
`release.yml` and `adapters-release.yml` and must not be silently dropped:

- the `publish` job keeps `permissions: id-token: write` and its environment
  (`pypi`, `pypi-adapters`) — PEP 740 attestation is available only to
  Trusted Publishing flows;
- the publish step declares `attestations: true` explicitly. The action ref
  tracks a moving branch, so an inherited default is not a property of the
  workflow.

`tests/test_identity_claims_boundary.py` asserts both for both workflows, so
removing either fails CI rather than quietly weakening the next release.

Both workflows also bind the release tag to the package version at the tagged
commit: `vX.Y.Z` must equal the root `pyproject.toml` version, and
`adapters-vX.Y.Z` the adapter package's. The publish job also uploads only the
sdist and wheel for that version. A mismatched tag publishes nothing
(`tests/test_release_workflow_policy.py`): the gate step records an error
annotation, the `publish` job is skipped, and the GitHub Release stays
published with nothing on PyPI.
Re-running reuses the same commit, so it cannot fix a mismatch: delete the
release and its tag, fix the version, and create the release again.

The gate also publishes nothing in two more cases, each with an error
annotation:

- **The release is marked as a prerelease.** GitHub runs the workflow for
  prereleases too, but a `vX.Y.Z` or `adapters-vX.Y.Z` upload is a final
  release on PyPI and cannot be replaced. Changing the release to a full
  release afterwards does not run the workflow again, and a re-run sees the
  same prerelease flag. Delete the GitHub Release (the tag can stay), then
  create a new release for the same tag without "Set as a pre-release".
- **`main` does not contain the tagged commit.** The gate checks out full
  history and requires the tagged commit to be an ancestor of `main` as
  fetched when the gate runs. A commit on a pull request's branch qualifies
  only once a merge commit brings it into `main`; squash and rebase merges
  create new commits, so after those it never qualifies. Delete the release
  and its tag, tag a commit on `main`, and create the release again.

These checks live in the workflow files, and GitHub runs a release with the
workflow files of the commit the tag targets. They protect only tags on
commits that include them: a tag on an older commit, or on a branch whose
workflows differ, runs that commit's own gate. Tag a commit on `main` that
includes them, and in the run confirm that the gate step ("… is not a
prerelease and is on main") ran and passed. Each PyPI trusted publisher is
registered for its environment (`pypi`, `pypi-adapters`), so a workflow that
drops the environment cannot publish; where that environment requires a
reviewer, approve the deployment only after that confirmation.

After publishing, confirm what actually reached PyPI:

```bash
curl -s https://pypi.org/pypi/nornyx/X.Y.Z/json | python -c "import json,sys; [print(f['filename'], f.get('provenance')) for f in json.load(sys.stdin)['urls']]"
```

A `provenance` URL means an attestation was published for that file; `None`
means none was. Record the actual result — releases up to and including 1.11.0
report `None`. The full consumer-side verification path, and what absence of
provenance does and does not mean, are in
[`docs/PROVENANCE_AND_RELEASE_VERIFICATION.md`](docs/PROVENANCE_AND_RELEASE_VERIFICATION.md).

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
