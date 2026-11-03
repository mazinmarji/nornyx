"""Release-workflow eligibility policy (F-3, F-4).

These tests execute the ACTUAL bash logic embedded in the release workflows
(extracted from the YAML, not reimplemented in Python), passing the release
tag through the ``TAG_NAME`` environment variable exactly as each step's
``env:`` does. The tag never reaches the script as text, so a tag name cannot
inject shell code. The release's prerelease flag arrives the same way, in
``PRERELEASE``, and each script runs in a throwaway git repository whose
detached HEAD is the tagged commit and whose ``refs/remotes/origin/main`` is
placed per test, built the way the gate job's full-history checkout is,
with decoy refs spelled like main.
This proves the real gate behavior rather than a Python
model of it that could silently drift from the YAML. Static checks
separately prove `workflow_dispatch` cannot reach either publish job, since
that gate is a job-level `if:` expression with no shell script to execute.
"""

from __future__ import annotations

import functools
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


ADAPTER_PYPROJECT = Path("adapters") / "nornyx-agentic-adapters" / "pyproject.toml"

# Where the tagged commit sits relative to `main` in the fixture origin.
ON_MAIN_TIP = "main-tip"
ON_MAIN_BEHIND_TIP = "main-behind-tip"
OFF_MAIN = "off-main"
NO_MAIN_REF = "no-main-ref"

# Refs a careless gate could mistake for main: tags and branches spelled like
# it. Every fixture origin has them, all pointing at the tagged commit.
DECOY_TAGS = ("main", "origin/main", "refs/remotes/origin/main")
DECOY_BRANCHES = ("origin/main", "remotes/origin/main")

# What actions/checkout@v4 fetches with `fetch-depth: 0`, as the release
# workflow's own test job logs it, before checking out the release tag.
CHECKOUT_REFSPECS = ("+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*")

_FIXTURE_ROOT: Path | None = None


@pytest.fixture(scope="module", autouse=True)
def _gate_fixture_root(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """pytest owns the fixture directory and its cleanup, including git's
    read-only object files."""
    global _FIXTURE_ROOT
    _FIXTURE_ROOT = tmp_path_factory.mktemp("release-gate")
    (_FIXTURE_ROOT / "empty.gitconfig").write_text("", encoding="utf-8")
    _fixture_repo.cache_clear()
    yield
    _fixture_repo.cache_clear()


def _git_env() -> dict[str, str]:
    """The caller's environment without its git settings: no GIT_* variables
    (a GIT_DIR would redirect every command) and no system or global config
    (hooks, signing, default branch, line endings)."""
    assert _FIXTURE_ROOT is not None
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = str(_FIXTURE_ROOT / "empty.gitconfig")
    return env


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=release-gate-test", "-c", "user.email=gate@example.invalid", *args],
        cwd=repo, env=_git_env(), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@functools.lru_cache(maxsize=None)
def _fixture_repo(placement: str) -> Path:
    """The gate job's checkout, built the way actions/checkout builds it: an
    origin repository holding `main`, the tagged commit (on `main`, or on an
    unmerged `feature` branch), both release tags and the decoy refs; then a
    fresh repository that fetches every branch and tag from it and checks out
    the release tag, leaving a detached HEAD at the tagged commit and no local
    branches. The gate scripts only read the checkout, so one per placement
    is shared; each build starts in a new directory."""
    assert _FIXTURE_ROOT is not None
    work = Path(tempfile.mkdtemp(prefix=f"{placement}-", dir=_FIXTURE_ROOT))
    src, checkout = work / "src", work / "checkout"
    (src / ADAPTER_PYPROJECT.parent).mkdir(parents=True)
    shutil.copyfile(ROOT / "pyproject.toml", src / "pyproject.toml")
    shutil.copyfile(ROOT / ADAPTER_PYPROJECT, src / ADAPTER_PYPROJECT)
    _git(src, "init", "-q", "-b", "main")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "base")
    if placement in (ON_MAIN_TIP, ON_MAIN_BEHIND_TIP):
        tagged = _git(src, "rev-parse", "HEAD")
        if placement == ON_MAIN_BEHIND_TIP:
            _git(src, "commit", "-q", "--allow-empty", "-m", "later on main")
    elif placement in (OFF_MAIN, NO_MAIN_REF):
        # main and the tagged commit share a parent, but main does not
        # contain the tagged commit: a tag on an unmerged branch.
        _git(src, "checkout", "-q", "-b", "feature")
        _git(src, "commit", "-q", "--allow-empty", "-m", "unmerged branch commit")
        tagged = _git(src, "rev-parse", "HEAD")
        _git(src, "checkout", "-q", "main")
        _git(src, "commit", "-q", "--allow-empty", "-m", "main moves on")
        if placement == NO_MAIN_REF:
            _git(src, "checkout", "-q", "feature")
            _git(src, "branch", "-q", "-D", "main")
    else:
        raise AssertionError(placement)
    release_tag = f"v{_core_package_version()}"
    for tag in (release_tag, f"adapters-v{_adapter_package_version()}", *DECOY_TAGS):
        _git(src, "tag", tag, tagged)
    for branch in DECOY_BRANCHES:
        _git(src, "branch", branch, tagged)
    _git(work, "clone", "-q", "--bare", "src", "origin.git")

    checkout.mkdir()
    _git(checkout, "init", "-q")
    _git(checkout, "remote", "add", "origin", (work / "origin.git").as_posix())
    _git(checkout, "fetch", "-q", "--prune", "--no-recurse-submodules", "origin", *CHECKOUT_REFSPECS)
    _git(checkout, "checkout", "-q", "--force", f"refs/tags/{release_tag}")
    assert _git(checkout, "rev-parse", "HEAD") == tagged
    assert _git(checkout, "for-each-ref", "refs/heads") == ""
    return checkout


def _eligible_for_tag(
    script: str, tag_name: str, *, prerelease: str | None, placement: str
) -> str:
    """Run the exact extracted shell step, as GitHub does (`bash -e`), in a
    fixture checkout, with the tag in ``TAG_NAME`` and the release's
    prerelease flag in ``PRERELEASE`` (``None`` leaves it unset), and return
    the single ``eligible`` value it wrote to $GITHUB_OUTPUT."""
    assert "${{" not in script, "the tag must reach the script as data (env), not as text"
    repo = _fixture_repo(placement)
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "github_output.txt"
        output_path.write_text("", encoding="utf-8")
        env = _git_env()
        if os.name == "nt":
            bash_bin = str(Path(_BASH).resolve().parent)
            env["PATH"] = bash_bin + os.pathsep + env.get("PATH", "")
        env["GITHUB_OUTPUT"] = str(output_path)
        env["TAG_NAME"] = tag_name
        env.pop("PRERELEASE", None)
        if prerelease is not None:
            env["PRERELEASE"] = prerelease

        result = subprocess.run(
            [_BASH, "-e", "-c", script],
            cwd=repo,
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


def _core_eligible(
    tag_name: str, *, prerelease: str | None = "false", placement: str = ON_MAIN_TIP
) -> bool:
    workflow = _load(CORE_RELEASE_YML)
    script = _step_script(workflow, "check-core-tag", "check")
    return _eligible_for_tag(script, tag_name, prerelease=prerelease, placement=placement) == "true"


def _adapter_eligible(
    tag_name: str, *, prerelease: str | None = "false", placement: str = ON_MAIN_TIP
) -> bool:
    workflow = _load(ADAPTERS_RELEASE_YML)
    script = _step_script(workflow, "check-adapter-tag", "check")
    return _eligible_for_tag(script, tag_name, prerelease=prerelease, placement=placement) == "true"


def _core_package_version() -> str:
    return re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    ).group(1)


def _adapter_package_version() -> str:
    return re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        (ROOT / ADAPTER_PYPROJECT).read_text(encoding="utf-8"),
    ).group(1)


def _matching_tags() -> list[tuple[Any, str]]:
    """Each gate with a tag that otherwise passes it: right shape, right version."""
    return [
        (_core_eligible, f"v{_core_package_version()}"),
        (_adapter_eligible, f"adapters-v{_adapter_package_version()}"),
    ]


@pytest.mark.parametrize("prerelease", ["true", "", None, "False", "0"])
def test_only_a_release_explicitly_not_marked_prerelease_publishes(prerelease: str | None) -> None:
    """GitHub fires `release: published` for prereleases too, and PyPI cannot
    replace a version once uploaded: a prerelease tagged vX.Y.Z (or
    adapters-vX.Y.Z) would otherwise publish a final release. The gate
    accepts only the exact value `false` and fails closed on anything else,
    including a missing value."""
    # The positive case, prerelease=false, is test_a_tag_on_main_is_eligible.
    for gate, tag in _matching_tags():
        assert gate(tag, prerelease=prerelease) is False, (tag, prerelease)


@pytest.mark.parametrize("placement", [ON_MAIN_TIP, ON_MAIN_BEHIND_TIP])
def test_a_tag_on_main_is_eligible(placement: str) -> None:
    """A tag on main's tip, or on an earlier main commit, passes."""
    for gate, tag in _matching_tags():
        assert gate(tag, placement=placement) is True, (tag, placement)


@pytest.mark.parametrize("placement", [OFF_MAIN, NO_MAIN_REF])
def test_a_tag_not_on_main_publishes_nothing(placement: str) -> None:
    """The version binding alone would publish a correctly versioned commit
    from an unmerged branch. The tagged commit must be contained in main,
    resolved by its full ref name: the decoy tags and branches spelled like
    main all point at the tagged commit, and with no main at all the gate
    fails closed."""
    for gate, tag in _matching_tags():
        assert gate(tag, placement=placement) is False, (tag, placement)


@pytest.mark.parametrize(
    "workflow_path,gate_job",
    [(CORE_RELEASE_YML, "check-core-tag"), (ADAPTERS_RELEASE_YML, "check-adapter-tag")],
)
def test_gate_reads_main_and_the_prerelease_flag_from_the_release(
    workflow_path: Path, gate_job: str
) -> None:
    """The ancestry check needs main's history in the gate checkout
    (`fetch-depth: 0` fetches every branch to refs/remotes/origin/*), still
    without persisted credentials; the prerelease flag reaches the script as
    data from the release event itself."""
    job = _load(workflow_path)["jobs"][gate_job]
    (checkout,) = _checkouts(job)
    assert checkout["with"]["fetch-depth"] == 0
    assert checkout["with"]["persist-credentials"] is False
    check = next(step for step in job["steps"] if step.get("id") == "check")
    assert check["env"]["PRERELEASE"] == "${{ github.event.release.prerelease }}"
    assert check["env"]["TAG_NAME"] == "${{ github.event.release.tag_name }}"
    assert not (set(check) & {"if", "continue-on-error", "shell"}), check


@pytest.mark.parametrize("workflow_path", [CORE_RELEASE_YML, ADAPTERS_RELEASE_YML])
def test_release_workflows_run_only_on_published_releases_and_dispatch(workflow_path: Path) -> None:
    """The gates are reviewed against the `published` payload; another release
    activity (`created`, `edited`, `released`) would reach them with a
    different one. PyYAML reads the bare `on` key as the boolean True."""
    assert _load(workflow_path)[True] == {"release": {"types": ["published"]}, "workflow_dispatch": None}


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
