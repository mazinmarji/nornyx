"""Orchestration: build a clean environment, install the published adapter from
PyPI, and run the probe against it.

Three properties this module is responsible for, none of which the probe can
establish about itself:

* **Isolation.** The child environment must not inherit ambient pip
  configuration, alternate indexes, or repository import paths, or the run
  proves nothing about the published artifact.
* **Provenance.** Which file, from which host, of which type, with which hash.
  Version metadata alone cannot answer that.
* **Process truth.** A report is only believable if the process that produced it
  also exited consistently with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import venv

from .failures import FailureClass, PipOnlyExampleError
from .probe import RESULT_SENTINEL
from .provenance import (
    PYPI_INDEX_URL,
    ArtifactProvenance,
    parse_install_report,
    provenance_violations,
)

#: The published version this example verifies.
#:
#: Deliberately a constant rather than a read of the repository's own
#: ``adapters/nornyx-agentic-adapters/pyproject.toml``. The example's subject is
#: the artifact **on the index**, and those two values diverge for the whole
#: window between a release-preparation merge and the actual publication. Wiring
#: it to the repo version would turn every release PR into a spurious
#: ``REGISTRY_INSTALL_FAILED``. Advance this constant deliberately, after a
#: publication, as its own reviewed change.
DEFAULT_VERSION = "0.3.0"

DISTRIBUTION_NAME = "nornyx-agentic-adapters"

#: Files whose presence together identify a Nornyx checkout. Used instead of a
#: fixed number of parent directories so the example still behaves correctly
#: when its package is copied somewhere with no repository above it -- in which
#: case there is genuinely no checkout to leak from, and inventing one would
#: forbid an unrelated directory (such as the one holding the clean venv).
_CHECKOUT_MARKERS = (
    Path("adapters") / "nornyx-agentic-adapters" / "pyproject.toml",
    Path("nornyx") / "agentic" / "__init__.py",
)

#: Loose PEP 440 release shape. The example only ever names an exact released
#: version, so a range or an unpinned name is a caller error, not a package fault.
_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*((a|b|rc)[0-9]+)?(\.post[0-9]+)?$")


@dataclass(frozen=True)
class ExampleResult:
    """A completed pip-only run."""

    version: str
    audit: dict[str, object]
    install_log: str = field(repr=False, default="")

    def as_dict(self) -> dict[str, object]:
        return {"status": "pass", "version": self.version, "audit": self.audit}


def _looks_like_checkout(candidate: Path) -> bool:
    return all((candidate / marker).exists() for marker in _CHECKOUT_MARKERS)


def _ascend_to_checkout(start: Path) -> str | None:
    for candidate in (start, *start.parents):
        if _looks_like_checkout(candidate):
            return str(candidate)
    return None


def repository_roots() -> list[str]:
    """Checkout roots the probe must prove nothing resolved from.

    Detected by marker files rather than by a fixed parent depth. When the
    example package has been copied out of the repository -- the standalone,
    no-clone path -- this correctly returns nothing rather than blaming an
    arbitrary ancestor directory.
    """
    roots: set[str] = set()
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        found = _ascend_to_checkout(start)
        if found is not None:
            roots.add(found)
    return sorted(roots)


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_env() -> dict[str, str]:
    """Environment with every inheritance vector this run must not trust.

    ``PYTHONPATH`` would place a checkout on the clean interpreter's
    ``sys.path``. Every ``PIP_*`` variable is dropped rather than filtered,
    because ``PIP_INDEX_URL`` and ``PIP_EXTRA_INDEX_URL`` can silently redirect
    resolution to a mirror or a private index -- which would make the phrase
    "installed from PyPI" false while everything still appeared to work.
    ``PIP_CONFIG_FILE`` is pointed at the null device for the same reason: a
    user-level or site-level ``pip.conf`` can carry the same redirection.
    """
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PIP_")
        and name not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


@dataclass(frozen=True)
class _Completed:
    """Subprocess outcome, including the cases where it never really ran."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str | None = None


def _run(command: list[str], *, cwd: Path, timeout: int) -> _Completed:
    """Run a subprocess, converting every non-completion into data.

    A ``TimeoutExpired`` or an ``OSError`` from the launch itself must not
    escape as a raw exception: the caller's contract is that every failure
    arrives as one of the seven classes.
    """
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=_clean_env(),
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as expired:
        return _Completed(
            returncode=-1,
            stdout=(expired.stdout or "") if isinstance(expired.stdout, str) else "",
            stderr=(expired.stderr or "") if isinstance(expired.stderr, str) else "",
            timed_out=True,
        )
    except OSError as exc:
        return _Completed(returncode=-1, stdout="", stderr=str(exc), launch_error=str(exc))
    return _Completed(
        returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
    )


def _validate_version(version: str) -> str:
    if not isinstance(version, str) or not version.strip():
        raise PipOnlyExampleError(
            FailureClass.EXAMPLE_INPUT_INVALID, "a version must be supplied"
        )
    candidate = version.strip()
    if not _VERSION_RE.match(candidate):
        raise PipOnlyExampleError(
            FailureClass.EXAMPLE_INPUT_INVALID,
            (
                f"{candidate!r} is not an exact release version. This example pins "
                "one published version on purpose; a range would make the result "
                "ambiguous about which artifact was verified."
            ),
        )
    return candidate


def parse_envelope(stdout: str) -> dict[str, object]:
    """Extract the probe's single JSON envelope from its stdout."""
    for line in stdout.splitlines():
        if line.startswith(RESULT_SENTINEL):
            payload = line[len(RESULT_SENTINEL) :].strip()
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise PipOnlyExampleError(
                    FailureClass.CONFORMANCE_EXECUTION_FAILED,
                    f"the probe emitted an unparsable envelope: {exc}",
                    evidence={"payload": payload},
                ) from exc
            if not isinstance(parsed, dict):
                raise PipOnlyExampleError(
                    FailureClass.CONFORMANCE_EXECUTION_FAILED,
                    "the probe envelope was not a JSON object",
                    evidence={"payload": payload},
                )
            return parsed
    raise PipOnlyExampleError(
        FailureClass.CONFORMANCE_EXECUTION_FAILED,
        (
            "the probe produced no result envelope. It is written to always emit "
            "one, so this means it died before reporting."
        ),
        evidence={"stdout": stdout[-4000:]},
    )


def check_process_consistency(envelope: dict[str, object], *, returncode: int) -> None:
    """Bind the report to the exit status of the process that produced it.

    An envelope is a claim; the exit code is the operating system's account of
    the same run. When they disagree, neither can be trusted, and accepting the
    envelope alone would let a probe that crashed after printing ``pass`` be
    read as a passing run.
    """
    status = envelope.get("status")
    if status == "pass" and returncode != 0:
        raise PipOnlyExampleError(
            FailureClass.CONFORMANCE_EXECUTION_FAILED,
            (
                f"the probe reported success but exited {returncode}; the report "
                "and the process disagree, so neither is evidence"
            ),
            evidence={"returncode": returncode, "envelope": envelope},
        )
    if status == "fail" and returncode == 0:
        raise PipOnlyExampleError(
            FailureClass.CONFORMANCE_EXECUTION_FAILED,
            (
                "the probe reported a failure but exited 0; a failing run that "
                "exits successfully would pass any exit-code-based gate"
            ),
            evidence={"returncode": returncode, "envelope": envelope},
        )
    if status not in {"pass", "fail"}:
        raise PipOnlyExampleError(
            FailureClass.CONFORMANCE_EXECUTION_FAILED,
            f"the probe reported an unknown status {status!r}",
            evidence={"returncode": returncode, "envelope": envelope},
        )


def raise_for_envelope(envelope: dict[str, object]) -> dict[str, object]:
    """Turn a failing envelope into the classified error it describes."""
    if envelope.get("status") == "pass":
        audit = envelope.get("audit")
        if not isinstance(audit, dict):
            raise PipOnlyExampleError(
                FailureClass.CONFORMANCE_EXECUTION_FAILED,
                "the probe reported success without an audit record",
            )
        return audit

    raw_class = str(envelope.get("failure_class") or "")
    try:
        failure_class = FailureClass(raw_class)
    except ValueError:
        raise PipOnlyExampleError(
            FailureClass.CONFORMANCE_EXECUTION_FAILED,
            f"the probe reported an unknown failure class {raw_class!r}",
            evidence={"envelope": envelope},
        ) from None
    evidence = envelope.get("evidence")
    raise PipOnlyExampleError(
        failure_class,
        str(envelope.get("detail") or "the probe reported a failure"),
        evidence=evidence if isinstance(evidence, dict) else {"evidence": evidence},
    )


def _create_environment(venv_root: Path) -> Path:
    """Build the clean venv. A failure here is local, never the package's fault."""
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
    except Exception as exc:  # noqa: BLE001 - re-raised as a classified failure
        raise PipOnlyExampleError(
            FailureClass.EXAMPLE_INPUT_INVALID,
            (
                f"could not create a clean virtual environment: {exc!r}. This is a "
                "local environment problem and says nothing about the published "
                "distribution."
            ),
            evidence={"venv_root": str(venv_root)},
        ) from exc
    python = _venv_python(venv_root)
    if not python.exists():
        raise PipOnlyExampleError(
            FailureClass.EXAMPLE_INPUT_INVALID,
            f"the created virtual environment has no interpreter at {python}",
        )
    return python


def _install_from_pypi(
    python: Path, *, root: Path, version: str, timeout: int
) -> tuple[ArtifactProvenance, str]:
    """Install the exact published version, bound to PyPI, as a wheel."""
    requirement = f"{DISTRIBUTION_NAME}=={version}"
    report_path = root / "install-report.json"
    result = _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-input",
            # Bind resolution to PyPI explicitly. Combined with the PIP_* scrub
            # and the null config file, "from PyPI" becomes a checked fact.
            "--index-url",
            PYPI_INDEX_URL,
            # The subject is the *published wheel*. Allowing an sdist would let
            # a local build stand in for the artifact consumers receive.
            "--only-binary",
            DISTRIBUTION_NAME,
            "--report",
            str(report_path),
            requirement,
        ],
        cwd=root,
        timeout=timeout,
    )
    if result.timed_out:
        raise PipOnlyExampleError(
            FailureClass.REGISTRY_INSTALL_FAILED,
            f"installing {requirement} timed out after {timeout}s",
            evidence={"timeout_seconds": timeout, "stderr": result.stderr[-2000:]},
        )
    if result.launch_error is not None:
        raise PipOnlyExampleError(
            FailureClass.REGISTRY_INSTALL_FAILED,
            f"pip could not be launched: {result.launch_error}",
            evidence={"launch_error": result.launch_error},
        )
    if result.returncode != 0:
        raise PipOnlyExampleError(
            FailureClass.REGISTRY_INSTALL_FAILED,
            f"pip could not install {requirement} from the index",
            evidence={
                "returncode": result.returncode,
                "stderr": result.stderr[-4000:],
                "stdout": result.stdout[-2000:],
            },
        )

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipOnlyExampleError(
            FailureClass.REGISTRY_INSTALL_FAILED,
            (
                f"pip produced no readable installation report ({exc!r}), so the "
                "artifact's origin cannot be established"
            ),
        ) from exc

    provenance = parse_install_report(report, distribution=DISTRIBUTION_NAME)
    problems = provenance_violations(
        provenance, expected_version=version, distribution=DISTRIBUTION_NAME
    )
    if problems:
        raise PipOnlyExampleError(
            FailureClass.REGISTRY_INSTALL_FAILED,
            "; ".join(problems),
            evidence={
                "provenance": provenance.as_dict() if provenance else None,
                "index_url": PYPI_INDEX_URL,
            },
        )
    assert provenance is not None  # provenance_violations covers None
    return provenance, result.stdout


def run_example(
    *,
    version: str = DEFAULT_VERSION,
    timeout: int = 900,
    extra_forbidden_roots: list[str] | None = None,
) -> ExampleResult:
    """Install the published adapter into a clean environment and verify it.

    Raises :class:`PipOnlyExampleError` with the classified reason on failure.
    """
    resolved_version = _validate_version(version)
    if timeout <= 0:
        raise PipOnlyExampleError(
            FailureClass.EXAMPLE_INPUT_INVALID, "timeout must be a positive number of seconds"
        )

    forbidden = list(repository_roots()) + list(extra_forbidden_roots or [])
    probe_source = Path(__file__).resolve().parent / "probe.py"

    # The temporary directory is the probe's working directory, so `sys.path[0]`
    # is a directory that contains nothing but the probe itself. Placed under the
    # system temp root, never inside the repository.
    with tempfile.TemporaryDirectory(prefix="nornyx-pip-only-") as raw_tmp:
        root = Path(raw_tmp).resolve()
        python = _create_environment(root / "venv")
        provenance, install_log = _install_from_pypi(
            python, root=root, version=resolved_version, timeout=timeout
        )

        shutil.copyfile(probe_source, root / "probe.py")
        command = [str(python), "probe.py", "--expect-version", resolved_version]
        for entry in forbidden:
            command += ["--forbidden-root", entry]

        probe = _run(command, cwd=root, timeout=timeout)
        if probe.timed_out:
            raise PipOnlyExampleError(
                FailureClass.CONFORMANCE_EXECUTION_FAILED,
                f"the probe timed out after {timeout}s",
                evidence={"timeout_seconds": timeout, "stderr": probe.stderr[-2000:]},
            )
        if probe.launch_error is not None:
            raise PipOnlyExampleError(
                FailureClass.CONFORMANCE_EXECUTION_FAILED,
                f"the probe could not be launched: {probe.launch_error}",
                evidence={"launch_error": probe.launch_error},
            )

        try:
            envelope = parse_envelope(probe.stdout)
        except PipOnlyExampleError as failure:
            # A missing envelope is the one case where the process account is
            # all the evidence there is, so it has to carry it.
            failure.evidence.setdefault("returncode", probe.returncode)
            failure.evidence.setdefault("stderr", probe.stderr[-4000:])
            raise

        check_process_consistency(envelope, returncode=probe.returncode)
        audit = raise_for_envelope(envelope)
        audit["provenance"] = provenance.as_dict()
        audit["index_url"] = PYPI_INDEX_URL

    return ExampleResult(
        version=resolved_version, audit=audit, install_log=install_log[-2000:]
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="pip_only_conformance",
        description=(
            "Install a published nornyx-agentic-adapters from PyPI into a clean "
            "environment and verify its bundled conformance resources."
        ),
    )
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the full audit record as JSON instead of a summary",
    )
    args = parser.parse_args(argv)

    try:
        result = run_example(version=args.version, timeout=args.timeout)
    except PipOnlyExampleError as failure:
        payload = failure.as_dict()
        if args.json:
            print(json.dumps({"status": "fail", **payload}, indent=2, sort_keys=True))
        else:
            print(f"FAIL  {failure.failure_class.value}", file=sys.stderr)
            print(f"      {failure.detail}", file=sys.stderr)
            attribution = (
                "the published distribution"
                if failure.attributable_to_distribution
                else "this example's invocation or local environment"
            )
            print(f"      attributed to: {attribution}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    audit = result.audit
    distribution = audit.get("distribution", {})
    provenance = audit.get("provenance", {})
    conformance = audit.get("conformance", {})
    model_calls = audit.get("model_calls", {})
    print(f"PASS  {DISTRIBUTION_NAME} {distribution.get('version')} from PyPI")
    print(f"      artifact       {provenance.get('filename')} ({provenance.get('artifact_type')})")
    print(f"      served by      {provenance.get('host')}")
    print(f"      sha256         {provenance.get('sha256')}")
    print(f"      installed at   {audit.get('environment', {}).get('site_packages')}")
    for label, origin in sorted(audit.get("resource_origins", {}).items()):
        print(f"      {label:<16} {origin}")
    print(
        f"      conformance    {conformance.get('outcome')} "
        f"({conformance.get('cases')} cases, tier {conformance.get('assurance_tier')})"
    )
    for field_name in ("external_model_service_called", "scripted_in_process_model_called"):
        entry = model_calls.get(field_name, {})
        print(f"      {field_name} = {entry.get('value')} [{entry.get('kind')}]")
    return 0
