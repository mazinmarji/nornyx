"""Release-workflow eligibility policy (F-3, F-4).

These tests execute the ACTUAL bash logic embedded in the release workflows
(extracted from the YAML, not reimplemented in Python), passing the release
tag through the ``TAG_NAME`` environment variable exactly as each step's
``env:`` does. The tag never reaches the script as text, so a tag name cannot
inject shell code. This proves the real gate behavior rather than a Python
model of it that could silently drift from the YAML. Static checks
separately prove `workflow_dispatch` cannot reach either publish job, since
that gate is a job-level `if:` expression with no shell script to execute.
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
    """Run the exact extracted shell step with the tag in ``TAG_NAME`` and
    return the single ``eligible`` value it wrote to $GITHUB_OUTPUT."""
    assert "${{" not in script, "the tag must reach the script as data (env), not as text"
    substituted = script
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "github_output.txt"
        output_path.write_text("", encoding="utf-8")
        env = dict(os.environ)
        if os.name == "nt":
            bash_bin = str(Path(_BASH).resolve().parent)
            env["PATH"] = bash_bin + os.pathsep + env.get("PATH", "")
        env["GITHUB_OUTPUT"] = str(output_path)
        env["TAG_NAME"] = tag_name

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
    # GitHub keeps the last value of a repeated output key, so a second
    # eligible= line could override the first: require exactly one.
    matches = re.findall(r"^eligible=(true|false)$", output, re.MULTILINE)
    assert len(matches) == 1, f"expected exactly one eligible= line: {output!r}"
    return matches[0]


def _core_eligible(tag_name: str) -> bool:
    workflow = _load(CORE_RELEASE_YML)
    script = _step_script(workflow, "check-core-tag", "check")
    return _eligible_for_tag(script, tag_name, cwd=ROOT) == "true"


def _adapter_eligible(tag_name: str) -> bool:
    workflow = _load(ADAPTERS_RELEASE_YML)
    script = _step_script(workflow, "check-adapter-tag", "check")
    return _eligible_for_tag(script, tag_name, cwd=ROOT) == "true"


def _core_package_version() -> str:
    return re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)


def test_core_vXYZ_tag_is_core_eligible_and_adapter_ineligible() -> None:
    # Uses the real current package version from the checked-out
    # pyproject.toml: the gate binds the tag to it.
    tag = f"v{_core_package_version()}"
    assert _core_eligible(tag) is True
    assert _adapter_eligible(tag) is False


def test_core_tag_version_mismatch_is_rejected() -> None:
    # A well-formed vX.Y.Z tag naming any other version must fail closed
    # rather than publish whatever version the tagged commit declares.
    major, minor, patch = (int(part) for part in _core_package_version().split("."))
    for version in (
        f"{major}.{minor}.{patch + 1}",
        f"{major}.{minor + 1}.0",
        f"{major + 1}.0.0",
        "1.8.1",
    ):
        assert _core_eligible(f"v{version}") is False, version


def _checkouts(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout@")]


@pytest.mark.parametrize(
    "workflow_path,gate_job",
    [(CORE_RELEASE_YML, "check-core-tag"), (ADAPTERS_RELEASE_YML, "check-adapter-tag")],
)
def test_gate_test_and_publish_all_check_out_the_release_commit(
    workflow_path: Path, gate_job: str
) -> None:
    """The binding compares against pyproject.toml, so the gate job must check
    out the commit the release tag targets before the check runs, and the test
    and publish jobs must use that same commit: no job may override `ref`, so
    all three resolve to the release event's own commit."""
    jobs = _load(workflow_path)["jobs"]
    steps = jobs[gate_job]["steps"]
    check_index = next(i for i, step in enumerate(steps) if step.get("id") == "check")
    assert any(
        str(step.get("uses", "")).startswith("actions/checkout@")
        for step in steps[:check_index]
    )
    for job_name in ("test", gate_job, "publish"):
        checkouts = _checkouts(jobs[job_name])
        assert len(checkouts) == 1, job_name
        assert "ref" not in (checkouts[0].get("with") or {}), job_name


@pytest.mark.parametrize(
    "tag",
    [
        'v9.9.9";echo${IFS}eligible=true>>$GITHUB_OUTPUT;exit${IFS}0;"',
        "v9.9.9$(echo${IFS}eligible=true>>$GITHUB_OUTPUT)",
        'adapters-v9.9.9";echo${IFS}eligible=true>>$GITHUB_OUTPUT;exit${IFS}0;"',
    ],
)
def test_tag_name_is_data_not_shell(tag: str) -> None:
    """Git permits `"`, `$`, `(`, `;` and `>` in tag names; the gates must
    treat the tag as data, never as script text."""
    assert _core_eligible(tag) is False
    assert _adapter_eligible(tag) is False


ARTIFACT_CHECK_STEP = "Verify the built distributions carry the release tag's version"


def _publish_artifact_check(workflow_path: Path) -> dict[str, Any]:
    """The publish job verifies what it built before the upload step."""
    steps = _load(workflow_path)["jobs"]["publish"]["steps"]
    checks = [i for i, s in enumerate(steps) if s.get("name") == ARTIFACT_CHECK_STEP]
    upload = [
        i for i, s in enumerate(steps)
        if str(s.get("uses", "")).startswith("pypa/gh-action-pypi-publish")
    ]
    assert len(checks) == 1 and len(upload) == 1
    assert checks[0] < upload[0]
    step = steps[checks[0]]
    # Nothing may skip the check, swallow its failure, or change its shell.
    assert not (set(step) & {"if", "continue-on-error", "shell"}), step
    return step


def _artifact_check_passes(step: dict[str, Any], tag: str, files: list[str]) -> bool:
    assert "${{" not in step["run"], "the tag must reach the script as data (env)"
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "dist").mkdir()
        for name in files:
            (Path(tmp) / "dist" / name).write_text("", encoding="utf-8")
        env = dict(os.environ)
        if os.name == "nt":
            env["PATH"] = str(Path(_BASH).resolve().parent) + os.pathsep + env.get("PATH", "")
        env["TAG_NAME"] = tag
        # GitHub runs `run:` steps with `bash -e`, so the first failing
        # `test` ends the step.
        result = subprocess.run(
            [_BASH, "-e", "-c", step["run"]], cwd=tmp, env=env, capture_output=True, text=True
        )
    return result.returncode == 0


def test_core_publish_uploads_only_the_tagged_version() -> None:
    step = _publish_artifact_check(CORE_RELEASE_YML)
    built = ["nornyx-1.12.0.tar.gz", "nornyx-1.12.0-py3-none-any.whl"]
    assert _artifact_check_passes(step, "v1.12.0", built) is True
    assert _artifact_check_passes(step, "v1.12.1", built) is False
    assert _artifact_check_passes(step, "v1.12.0", built[:1]) is False
    assert _artifact_check_passes(step, "v1.12.0", [*built, "nornyx-1.11.0.tar.gz"]) is False


def test_adapter_publish_uploads_only_the_tagged_version() -> None:
    step = _publish_artifact_check(ADAPTERS_RELEASE_YML)
    built = ["nornyx_agentic_adapters-0.3.1.tar.gz", "nornyx_agentic_adapters-0.3.1-py3-none-any.whl"]
    assert _artifact_check_passes(step, "adapters-v0.3.1", built) is True
    assert _artifact_check_passes(step, "adapters-v0.3.2", built) is False
    assert _artifact_check_passes(step, "adapters-v0.3.1", built[1:]) is False


def test_core_release_test_job_installs_what_the_suite_needs() -> None:
    """The publish job needs the test job, and the suite builds the textbook:
    it needs the dev extra (mistune) and the Graphviz `dot` binary, as ci.yml
    installs them. A bare `pip install .` fails the job and blocks publish."""
    workflow = _load(CORE_RELEASE_YML)
    assert "test" in workflow["jobs"]["publish"]["needs"]
    # Only unconditional steps, and only command lines, not comments.
    commands = [
        line.strip()
        for step in workflow["jobs"]["test"]["steps"]
        if "if" not in step
        for line in step.get("run", "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert any(re.search(r'pip install (-e )?"\.\[dev\]"', c) for c in commands), commands
    assert any("apt-get install -y graphviz" in c for c in commands), commands


def test_matching_adapters_tag_is_adapter_eligible_and_core_ineligible() -> None:
    # Uses the real current package version (0.3.1) from the checked-out
    # pyproject.toml, not a hardcoded assumption.
    pkg_version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "adapters" / "nornyx-agentic-adapters" / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)
    assert _adapter_eligible(f"adapters-v{pkg_version}") is True
    assert _core_eligible(f"adapters-v{pkg_version}") is False


def test_adapters_tag_version_mismatch_is_rejected() -> None:
    # The package currently declares 0.3.1; a tag naming a different version
    # must fail closed rather than publish a mismatched release.
    pkg_version = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "adapters" / "nornyx-agentic-adapters" / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)
    assert pkg_version == "0.3.1", "test assumption drifted from the actual package version"
    assert _adapter_eligible("adapters-v0.3.2") is False


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
