"""Provenance of the artifact pip actually installed.

Version metadata proves what a distribution *calls itself*. It does not prove
where the file came from, whether it was a wheel or an sdist built on the spot,
or which bytes were consumed. Those are separate claims and this module makes
them separately.

The evidence is pip's own installation report (``pip install --report``), which
records, per resolved requirement, the URL it downloaded and the hash of the
archive. Parsing that is what turns "a package named X version Y is importable"
into "this exact wheel, from this host, with this SHA-256".
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

#: Hosts that count as "from PyPI". The index is ``pypi.org``; the files it
#: serves live on ``files.pythonhosted.org``, so a wheel legitimately downloaded
#: from PyPI reports the latter.
PYPI_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org"})

#: Canonical index this example binds resolution to.
PYPI_INDEX_URL = "https://pypi.org/simple"


def canonical_name(name: str) -> str:
    """PEP 503 normalized project name, so `_`/`-`/`.` spellings compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class ArtifactProvenance:
    """Where one installed artifact came from, and what it was."""

    name: str
    version: str
    url: str
    host: str
    filename: str
    artifact_type: str
    sha256: str | None

    @property
    def is_wheel(self) -> bool:
        return self.artifact_type == "wheel"

    @property
    def from_pypi(self) -> bool:
        return self.host in PYPI_HOSTS

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "url": self.url,
            "host": self.host,
            "filename": self.filename,
            "artifact_type": self.artifact_type,
            "sha256": self.sha256,
            "from_pypi": self.from_pypi,
            "is_wheel": self.is_wheel,
        }


def _artifact_type(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".whl"):
        return "wheel"
    if lowered.endswith((".tar.gz", ".zip", ".tar.bz2")):
        return "sdist"
    return "unknown"


def _extract_sha256(download_info: dict) -> str | None:
    archive = download_info.get("archive_info")
    if not isinstance(archive, dict):
        return None
    hashes = archive.get("hashes")
    if isinstance(hashes, dict) and isinstance(hashes.get("sha256"), str):
        return hashes["sha256"]
    # pip's older single-hash spelling, retained so an older pip still yields
    # provenance rather than silently reporting none.
    legacy = archive.get("hash")
    if isinstance(legacy, str) and legacy.startswith("sha256="):
        return legacy.split("=", 1)[1]
    return None


def parse_install_report(report: dict, *, distribution: str) -> ArtifactProvenance | None:
    """Pull one distribution's provenance out of a ``pip install --report`` payload.

    Returns ``None`` when the report contains no entry for the distribution,
    which the caller treats as a provenance failure rather than as success.
    """
    if not isinstance(report, dict):
        return None
    entries = report.get("install")
    if not isinstance(entries, list):
        return None

    wanted = canonical_name(distribution)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        if canonical_name(str(metadata.get("name", ""))) != wanted:
            continue

        download_info = entry.get("download_info")
        download_info = download_info if isinstance(download_info, dict) else {}
        url = str(download_info.get("url", ""))
        filename = urlsplit(url).path.rsplit("/", 1)[-1]
        return ArtifactProvenance(
            name=str(metadata.get("name", distribution)),
            version=str(metadata.get("version", "")),
            url=url,
            host=(urlsplit(url).hostname or ""),
            filename=filename,
            artifact_type=_artifact_type(filename),
            sha256=_extract_sha256(download_info),
        )
    return None


def provenance_violations(
    provenance: ArtifactProvenance | None,
    *,
    expected_version: str,
    distribution: str,
) -> list[str]:
    """Reasons this artifact fails to be 'the published wheel from PyPI'."""
    if provenance is None:
        return [
            f"pip's installation report contains no entry for {distribution}; "
            "the artifact's origin cannot be established"
        ]

    problems: list[str] = []
    if not provenance.url:
        problems.append("the installation report recorded no download URL")
    if not provenance.from_pypi:
        problems.append(
            f"artifact was served by {provenance.host or '<unknown host>'!s}, "
            f"which is not PyPI ({', '.join(sorted(PYPI_HOSTS))})"
        )
    if not provenance.is_wheel:
        problems.append(
            f"artifact {provenance.filename or '<unnamed>'} is a "
            f"{provenance.artifact_type}, not a wheel; an sdist would have been "
            "built locally rather than consumed as published"
        )
    if provenance.version != expected_version:
        problems.append(
            f"installation report names version {provenance.version!r}, "
            f"expected {expected_version!r}"
        )
    if not provenance.sha256:
        problems.append("the installation report carried no SHA-256 for the artifact")
    return problems
