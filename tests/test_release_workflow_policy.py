"""Release-workflow eligibility policy (F-3, F-4).

These tests execute the ACTUAL bash logic embedded in the release workflows
(extracted from the YAML, not reimplemented in Python), substituting only the
``${{ github.event.release.tag_name }}`` expression the way GitHub's template
engine would before the shell ever runs it. This proves the real gate
behavior rather than a Python model of it that could silently drift from the
YAML. Static checks separately prove `workflow_dispatch` cannot reach either
publish job, since that gate is a job-level `if:` expression with no shell
script to execute.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CORE_RELEASE_YML = ROOT / ".github" / "workflows" / "release.yml"
ADAPTERS_RELEASE_YML = ROOT / ".github" / "workflows" / "adapters-release.yml"


def _bash_executable() -> str:
    """Resolve a real POSIX bash, not a launcher stub.

    On some Windows setups, a bare ``"bash"`` combined with an explicit
    ``cwd=`` resolves to the WSL launcher stub (``System32\\bash.exe``)
    instead of Git-Bash, which does not inherit the parent's environment the
    way MSYS bash does. GitHub Actions runners (``ubuntu-latest``) have no
    such ambiguity; this only matters for running this test locally on
    Windows, so prefer a known Git-Bash path when present.
    """
    for candidate in (
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    assert found, "no bash executable found"
    return found


_BASH = _bash_executable()


def _load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _step_script(workflow: dict[str, Any], job_name: str, step_id: str) -> str:
    for step in workflow["jobs"][job_name]["steps"]:
        if step.get("id") == step_id:
            return step["run"]
    raise AssertionError(f"step id={step_id!r} not found in job {job_name!r}")


def _eligible_for_tag(script: str, tag_name: str, *, cwd: Path) -> str:
    """Run the exact extracted shell step, substituting the tag-name template
    expression, and return the ``eligible`` value it wrote to $GITHUB_OUTPUT."""
    substituted = script.replace("${{ github.event.release.tag_name }}", tag_name)
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "github_output.txt"
        output_path.write_text("", encoding="utf-8")
        env = dict(os.environ)
        env["GITHUB_OUTPUT"] = str(output_path)

        result = subprocess.run(
            [_BASH, "-c", substituted],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"eligibility script failed (exit {result.returncode}): "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        output = output_path.read_text(encoding="utf-8")
    match = re.search(r"^eligible=(true|false)$", output, re.MULTILINE)
    assert match, f"eligibility script wrote no eligible= line: {output!r}"
    return match.group(1)


def _core_eligible(tag_name: str) -> bool:
    workflow = _load(CORE_RELEASE_YML)
    script = _step_script(workflow, "check-core-tag", "check")
    return _eligible_for_tag(script, tag_name, cwd=ROOT) == "true"


def _adapter_eligible(tag_name: str) -> bool:
    workflow = _load(ADAPTERS_RELEASE_YML)
    script = _step_script(workflow, "check-adapter-tag", "check")
    return _eligible_for_tag(script, tag_name, cwd=ROOT) == "true"


def test_core_vXYZ_tag_is_core_eligible_and_adapter_ineligible() -> None:
    assert _core_eligible("v1.8.1") is True
    assert _adapter_eligible("v1.8.1") is False


def test_matching_adapters_tag_is_adapter_eligible_and_core_ineligible() -> None:
    # Uses the real current package version (0.1.0) from the checked-out
    # pyproject.toml, not a hardcoded assumption.
    pkg_version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "adapters" / "nornyx-agentic-adapters" / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)
    assert _adapter_eligible(f"adapters-v{pkg_version}") is True
    assert _core_eligible(f"adapters-v{pkg_version}") is False


def test_adapters_tag_version_mismatch_is_rejected() -> None:
    # The package currently declares 0.1.0; a tag naming a different version
    # must fail closed rather than publish a mismatched release.
    pkg_version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "adapters" / "nornyx-agentic-adapters" / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)
    assert pkg_version == "0.1.0", "test assumption drifted from the actual package version"
    assert _adapter_eligible("adapters-v0.1.1") is False


def test_unrelated_release_tag_is_rejected_by_both_gates() -> None:
    for tag in ("nightly", "release-2026", "vNext", "adapters-latest"):
        assert _core_eligible(tag) is False, tag
        assert _adapter_eligible(tag) is False, tag


def test_prerelease_suffixed_core_tag_is_rejected() -> None:
    """The core gate requires an exact vX.Y.Z match, not a prefix match."""
    assert _core_eligible("v1.8.0-rc1") is False


@pytest.mark.parametrize(
    "workflow_path,job_name",
    [(CORE_RELEASE_YML, "publish"), (ADAPTERS_RELEASE_YML, "publish")],
)
def test_workflow_dispatch_cannot_bypass_the_publish_gate(workflow_path: Path, job_name: str) -> None:
    """Static proof: `workflow_dispatch` carries no release tag_name at all, and
    the publish job's own `if:` requires `github.event_name == 'release'`, so
    a manual dispatch can never satisfy it regardless of any other input."""
    workflow = _load(workflow_path)
    condition = workflow["jobs"][job_name]["if"]
    assert "github.event_name == 'release'" in condition, condition


def test_core_publish_requires_the_tag_eligibility_output() -> None:
    workflow = _load(CORE_RELEASE_YML)
    condition = workflow["jobs"]["publish"]["if"]
    assert "needs.check-core-tag.outputs.eligible == 'true'" in condition


def test_adapter_publish_requires_the_tag_version_binding_output() -> None:
    workflow = _load(ADAPTERS_RELEASE_YML)
    condition = workflow["jobs"]["publish"]["if"]
    assert "needs.check-adapter-tag.outputs.eligible == 'true'" in condition


def test_adapter_release_workflow_never_writes_tags() -> None:
    """The workflow must not create, move, or repair tags."""
    text = ADAPTERS_RELEASE_YML.read_text(encoding="utf-8")
    assert "git tag" not in text
    assert "git push" not in text
    assert "contents: write" not in text


def test_core_release_workflow_never_writes_tags() -> None:
    text = CORE_RELEASE_YML.read_text(encoding="utf-8")
    assert "git tag" not in text
    assert "git push" not in text
    assert "contents: write" not in text
