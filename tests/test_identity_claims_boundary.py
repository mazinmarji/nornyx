"""ADR-0045: the project must obey the claim boundaries it publishes.

A project that overclaims its own identity cannot credibly describe anyone
else's. These tests hold Nornyx to the vocabulary in
``docs/NYX_FORMAT_AND_CONFORMANCE.md`` and the provenance boundaries in
``docs/PROVENANCE_AND_RELEASE_VERIFICATION.md``, and guard the two behavioural
properties those documents assert about the implementation.

**Scope.** Two different breadths, deliberately:

* The registered-trademark symbol is checked across *every tracked Markdown
  file*. No registration exists, so the symbol is wrong anywhere, and the
  check is unambiguous enough to run repository-wide.
* The narrower unsupported-claim checks run against a named list of
  ``PRIMARY_CLAIM_SURFACES`` only. They are phrase-based, and historical
  planning records and the edition-pinned textbook legitimately discuss
  things the current-voice documents may not assert. This is a selected
  surface, not the whole repository, and nothing here should be read as
  governing all Nornyx documentation.

They are deliberately about *claims*, not about governed content. Existing
suites already pin canonicalization and generated-artifact digests; nothing
here duplicates that coverage.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from nornyx.agentic_artifacts import contract_digest
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]

TRADEMARKS = ROOT / "TRADEMARKS.md"
FORMAT_DOC = ROOT / "docs" / "NYX_FORMAT_AND_CONFORMANCE.md"
PROVENANCE_DOC = ROOT / "docs" / "PROVENANCE_AND_RELEASE_VERIFICATION.md"
ADR = ROOT / "docs" / "decisions" / "ADR-0045-project-identity-conformance-and-provenance.md"

#: The *selected* primary claim surfaces: where the project speaks about itself
#: in its own current voice. This is not every document in the repository.
#: Historical planning records and the edition-pinned textbook are excluded --
#: they are preserved evidence, not current claims, and they may legitimately
#: discuss wording the current-voice documents must not assert.
PRIMARY_CLAIM_SURFACES = (
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "RELEASING.md",
    ROOT / "SECURITY.md",
    ROOT / "LICENSE",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "00_EXECUTIVE_OVERVIEW.md",
    ROOT / "docs" / "48_NORNYX_POSITIONING.md",
    TRADEMARKS,
    FORMAT_DOC,
    PROVENANCE_DOC,
    ADR,
)

#: The identity policy documents are permitted to *name* a prohibited claim in
#: order to rule it out. Everywhere else, naming it is asserting it.
POLICY_DOCS = frozenset({TRADEMARKS, FORMAT_DOC, PROVENANCE_DOC, ADR})


def _tracked_markdown() -> list[Path]:
    """Every Markdown file git tracks, for the repository-wide symbol check."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=ROOT, capture_output=True, check=True, text=True,
    ).stdout
    return [ROOT / name for name in out.split("\0") if name]

#: Affirmative claims the project has not established and must not imply.
#: Registration, certification, and endorsement are the three that would each
#: require an authority that does not exist.
PROHIBITED_CLAIMS = (
    "registered trademark",
    "certified by nornyx",
    "nornyx-certified",
    "nornyx certified",
    "officially endorsed by nornyx",
    "conformance certificate",
)


def _rel(path: Path) -> str:
    """Repo-relative id, so ``README.md`` and ``docs/README.md`` stay distinct."""
    return path.relative_to(ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(path: Path) -> str:
    """Whitespace-collapsed, case-folded text.

    These documents are hard-wrapped prose, so a phrase routinely straddles a
    line break. Matching the raw text would make a harmless reflow fail CI,
    and a test that fails on reformatting is a test that gets deleted.
    """
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8")).casefold()


def test_no_registered_trademark_symbol_in_any_tracked_markdown() -> None:
    """Repository-wide, not just the selected surfaces.

    No registration exists, so the symbol would be a misrepresentation in
    several jurisdictions wherever it appeared. TRADEMARKS.md says so in words
    and must therefore also avoid the character itself.
    """
    offenders = [
        _rel(path)
        for path in _tracked_markdown()
        if "®" in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert not offenders, (
        f"{len(offenders)} tracked Markdown file(s) use the registered-trademark "
        f"symbol, but TRADEMARKS.md records that no registration is claimed: "
        f"{offenders[:10]}"
    )


@pytest.mark.parametrize(
    "path", [p for p in PRIMARY_CLAIM_SURFACES if p not in POLICY_DOCS], ids=_rel
)
def test_no_unsupported_identity_claims_outside_the_policy_docs(path: Path) -> None:
    text = _flat(path)
    for phrase in PROHIBITED_CLAIMS:
        assert phrase not in text, (
            f"{_rel(path)} asserts {phrase!r}, which no Nornyx authority "
            "currently supports (ADR-0045)"
        )


def test_trademark_policy_is_marked_as_requiring_counsel_review() -> None:
    # Without this marker the document could drift into being treated as an
    # enforcement instrument it is not.
    text = _flat(TRADEMARKS)
    assert "counsel review" in text
    assert "not a legal instrument" in text
    assert "no trademark registration is claimed" in text


def test_trademark_policy_preserves_the_mit_grant() -> None:
    text = _flat(TRADEMARKS)
    assert "mit licensed" in text
    # Forking must be stated as permitted, not merely left unmentioned.
    assert "forking is a legitimate use" in text


def test_every_conformance_claim_class_is_fully_specified() -> None:
    """A claim term with no stated verification or non-meaning is branding."""
    text = _read(FORMAT_DOC)
    flat = _flat(FORMAT_DOC)
    for claim in (
        "Nornyx-compatible",
        "Nornyx-conformant",
        "Nornyx implementation",
        "Official Nornyx release",
    ):
        assert f"### `{claim}`" in text, f"claim class {claim!r} is not defined"

    for section in ("**requirement.**", "**who may assert.**", "**verification.**", "**does not mean.**"):
        # One occurrence per claim class, so a new class cannot be added
        # without also stating its boundaries.
        assert flat.count(section) >= 4, (
            f"{section!r} appears {flat.count(section)} times; every claim "
            "class must state it"
        )


def test_the_two_version_axes_are_not_conflated() -> None:
    """A conformance claim naming the wrong version axis is unfalsifiable.

    The in-document ``nornyx:`` marker is ``"0.1"``/``"0.2"``; the
    language/schema version is ``1.0`` and lives in ``manifest.json``. The
    v1.0 schema accepts only the 0.1 and 0.2 markers, so a document cannot
    declare its own language/schema version. Verified against the packaged
    schema below rather than asserted from prose alone.
    """
    schema = json.loads(
        (ROOT / "nornyx" / "schemas" / "nornyx_v1_0.schema.json").read_text(encoding="utf-8")
    )
    accepted = {
        branch["const"]
        for branch in schema["properties"]["nornyx"]["oneOf"]
        if isinstance(branch.get("const"), str)
    }
    assert accepted == {"0.1", "0.2"}, (
        f"the v1.0 schema accepts markers {sorted(accepted)}; the format "
        "document's version-axis table must be updated to match"
    )
    assert "1.0" not in accepted, "a document must not be able to declare language/schema 1.0"

    flat = _flat(FORMAT_DOC)
    assert "a contract does not declare its language/schema version" in flat
    assert "in-document version marker" in flat
    # The claim vocabulary must name the target, not the marker.
    assert "the claimant names the target; the document does not" in flat


def test_verification_is_scoped_to_nornyx_operated_services_not_offline() -> None:
    """'Offline' would be false: the procedure reads PyPI and GitHub.

    The property the design actually holds is the absence of any
    *Nornyx-operated* dependency, which is the one worth claiming.
    """
    for doc in (FORMAT_DOC, PROVENANCE_DOC):
        flat = _flat(doc)
        assert "nornyx-operated" in flat, f"{_rel(doc)} must name the actual property"
    prov = _flat(PROVENANCE_DOC)
    assert "must never require a nornyx-operated service" in prov
    assert "package index or forge" in prov, (
        "the document must acknowledge that obtaining an artifact and its "
        "attestation reaches a network service"
    )


def test_no_certification_authority_is_claimed_to_exist() -> None:
    lowered = _flat(FORMAT_DOC)
    assert "operates **no certification authority**" in lowered
    assert "issues no certification" in lowered


def test_provenance_and_conformance_are_documented_as_independent() -> None:
    lowered = _flat(PROVENANCE_DOC)
    assert "official provenance is never a substitute for conformance testing" in lowered
    assert "conformance never implies nornyx endorsement" in lowered


def test_provenance_absence_is_distinguished_from_provenance_failure() -> None:
    lowered = _flat(PROVENANCE_DOC)
    for state in ("**verified**", "**absent**", "**failed**"):
        assert state in lowered, f"provenance result state {state} is undocumented"
    # The distinction is the whole point: absence must not read as invalidity.
    assert "stripping provenance is permitted" in lowered


def test_provenance_doc_does_not_overclaim_published_attestations() -> None:
    """Guards against optimistic drift.

    Verified against the PyPI JSON API on 2026-09-01: both files of
    ``nornyx==1.11.0`` report ``provenance: null``. If a future release does
    publish attestations, this statement should be updated with evidence — not
    quietly deleted.
    """
    lowered = _flat(PROVENANCE_DOC)
    assert "currently carry no pep 740 attestation" in lowered
    assert "no claim is made here about artifacts already published" in lowered


def test_release_workflow_declares_attestations_explicitly() -> None:
    workflow = yaml.safe_load(_read(ROOT / ".github" / "workflows" / "release.yml"))
    steps = workflow["jobs"]["publish"]["steps"]
    publish = [s for s in steps if str(s.get("uses", "")).startswith("pypa/gh-action-pypi-publish")]
    assert len(publish) == 1, "expected exactly one PyPI publish step"
    assert publish[0].get("with", {}).get("attestations") is True, (
        "the publish step must declare attestations explicitly; the action ref "
        "tracks a moving branch, so an inherited default is not a property of "
        "this workflow (ADR-0045)"
    )


def test_release_workflow_still_uses_trusted_publishing() -> None:
    workflow = yaml.safe_load(_read(ROOT / ".github" / "workflows" / "release.yml"))
    publish = workflow["jobs"]["publish"]
    # PEP 740 attestation is only available to Trusted Publishing flows, so the
    # OIDC permission is part of the provenance claim, not incidental.
    assert publish["permissions"]["id-token"] == "write"
    assert publish["environment"] == "pypi"


@pytest.mark.parametrize(
    "schema_name",
    ["nornyx_v0_1.schema.json", "nornyx_v0_2.schema.json", "nornyx_v1_0.schema.json"],
)
def test_contract_language_carries_no_identity_metadata(schema_name: str) -> None:
    """ADR-0045 decision 2: identity metadata must not enter the language.

    ``contract_digest()`` canonicalizes the whole parsed document, so a
    branding block would move the governed digest of every contract that
    adopted it. Adding one is a breaking change, and this test forces that
    conversation rather than letting it land as metadata.
    """
    schema = json.loads((ROOT / "nornyx" / "schemas" / schema_name).read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False, (
        "a closed top level is what keeps identity metadata out by default"
    )
    forbidden = {"identity", "provenance", "trademark", "branding", "official", "vendor", "signature"}
    present = forbidden & set(schema.get("properties", {}))
    assert not present, (
        f"{schema_name} declares identity-shaped top-level blocks {sorted(present)}; "
        "identity metadata belongs in detached provenance, not the contract language"
    )


def test_contract_identity_does_not_depend_on_the_file_extension(tmp_path: Path) -> None:
    """The format doc promises the parser does not gate on ``.nyx``.

    Nornyx claims canonical *semantics*, not ownership of an extension. If the
    parser ever started rejecting other names, that promise would silently
    become false.
    """
    source = ROOT / "examples" / "governed_delivery_control_plane.nyx"
    baseline = contract_digest(load_nyx(source))
    raw = source.read_bytes()

    for name in ("renamed.abc", "renamed.txt", "renamed"):
        target = tmp_path / name
        target.write_bytes(raw)
        assert contract_digest(load_nyx(target)) == baseline, (
            f"renaming the contract to {name!r} changed its governed identity"
        )


def test_identity_documents_are_registered_in_the_documentation_map() -> None:
    index = _read(ROOT / "docs" / "README.md")
    for link in (
        "NYX_FORMAT_AND_CONFORMANCE.md",
        "PROVENANCE_AND_RELEASE_VERIFICATION.md",
        "../TRADEMARKS.md",
    ):
        assert link in index, f"{link} is not reachable from the documentation map"


def test_readme_separates_licence_from_project_identity() -> None:
    readme = _read(ROOT / "README.md")
    assert "TRADEMARKS.md" in readme, "the README must link the identity policy"
    assert "NYX_FORMAT_AND_CONFORMANCE.md" in readme
    assert "PROVENANCE_AND_RELEASE_VERIFICATION.md" in readme
