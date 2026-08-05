"""Orchestration: build a clean environment, install the published adapter from
the index, and run the probe against it.

Nothing here touches the repository except to locate the probe source and to
compute the repository roots the probe must prove it did *not* import from.
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


def repository_roots() -> list[str]:
    """Roots the probe must prove nothing resolved from.

    ``parents[2]`` is the repository root: this file sits at
    ``<repo>/examples/pip_only_conformance/runner.py``. The current working
    directory is included as well, because a consumer may run the example from
    a checkout that is not this one.
    """
    roots = {str(Path(__file__).resolve().parents[2]), str(Path.cwd().resolve())}
    return sorted(roots)


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_env() -> dict[str, str]:
    """Environment with repository leakage vectors removed.

    ``PYTHONPATH`` is the obvious one: it would place a checkout on the clean
    interpreter's ``sys.path`` and silently invalidate the entire run.
    ``PYTHONHOME`` and ``PYTHONSTARTUP`` are removed for the same reason.
    """
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(name, None)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=_clean_env(),
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
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
        venv_root = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
        python = _venv_python(venv_root)

        requirement = f"{DISTRIBUTION_NAME}=={resolved_version}"
        install = _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--no-input",
                requirement,
            ],
            cwd=root,
            timeout=timeout,
        )
        if install.returncode != 0:
            raise PipOnlyExampleError(
                FailureClass.REGISTRY_INSTALL_FAILED,
                f"pip could not install {requirement} from the index",
                evidence={
                    "returncode": install.returncode,
                    "stderr": install.stderr[-4000:],
                    "stdout": install.stdout[-2000:],
                },
            )

        shutil.copyfile(probe_source, root / "probe.py")
        command = [
            str(python),
            "probe.py",
            "--expect-version",
            resolved_version,
        ]
        for entry in forbidden:
            command += ["--forbidden-root", entry]

        probe = _run(command, cwd=root, timeout=timeout)
        envelope = parse_envelope(probe.stdout)
        audit = raise_for_envelope(envelope)

    return ExampleResult(
        version=resolved_version,
        audit=audit,
        install_log=install.stdout[-2000:],
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
                else "this example's invocation"
            )
            print(f"      attributed to: {attribution}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    audit = result.audit
    distribution = audit.get("distribution", {})
    conformance = audit.get("conformance", {})
    model_calls = audit.get("model_calls", {})
    print(f"PASS  {DISTRIBUTION_NAME} {distribution.get('version')} from the index")
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
