"""Orchestration: clean environment, install from PyPI, run the scenario.

Deliberately the same shape as `examples/pip_only_conformance`: that design is
already CI-verified on `main`, and an adoption pilot is the wrong place to
invent a second way of doing this. What differs is the payload -- this one runs
a governance A/B/C through CrewAI rather than the conformance kit.
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

from .failures import PilotError, PilotFailure

#: The published versions this pilot demonstrates.
#:
#: Constants, not reads of the repository's own metadata: the subject is what an
#: external adopter can install today. Advance them deliberately after a
#: publication, as a reviewed change.
ADAPTER_VERSION = "0.3.0"
#: The exact pin the adapter's `[crewai]` extra declares.
CREWAI_VERSION = "1.15.4"

ADAPTER_DISTRIBUTION = "nornyx-agentic-adapters"
PYPI_INDEX_URL = "https://pypi.org/simple"

#: Files whose presence together identify a Nornyx checkout. Marker-based rather
#: than a fixed parent depth so a copied package correctly reports no roots.
_CHECKOUT_MARKERS = (
    Path("adapters") / "nornyx-agentic-adapters" / "pyproject.toml",
    Path("nornyx") / "agentic" / "__init__.py",
)

_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*((a|b|rc)[0-9]+)?(\.post[0-9]+)?$")

RESULT_SENTINEL = "PILOT_RESULT"


@dataclass(frozen=True)
class PilotResult:
    adapter_version: str
    crewai_version: str
    record: dict[str, object]
    install_log: str = field(repr=False, default="")

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "pass",
            "adapter_version": self.adapter_version,
            "crewai_version": self.crewai_version,
            "record": self.record,
        }


def _looks_like_checkout(candidate: Path) -> bool:
    return all((candidate / marker).exists() for marker in _CHECKOUT_MARKERS)


def repository_roots() -> list[str]:
    roots: set[str] = set()
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        for candidate in (start, *start.parents):
            if _looks_like_checkout(candidate):
                roots.add(str(candidate))
                break
    return sorted(roots)


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _clean_env() -> dict[str, str]:
    """Drop every inheritance vector: repository paths and pip redirection."""
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("PIP_")
        and name not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"}
    }
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    # The scenario sets these too, but a child that imports crewai during pip's
    # own resolution should not phone home either.
    env["CREWAI_DISABLE_TELEMETRY"] = "true"
    env["OTEL_SDK_DISABLED"] = "true"
    env["CREWAI_TRACING_ENABLED"] = "false"
    return env


@dataclass(frozen=True)
class _Completed:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    launch_error: str | None = None


def _run(command: list[str], *, cwd: Path, timeout: int) -> _Completed:
    try:
        completed = subprocess.run(
            command, cwd=cwd, env=_clean_env(), check=False,
            text=True, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as expired:
        return _Completed(
            returncode=-1,
            stdout=expired.stdout if isinstance(expired.stdout, str) else "",
            stderr=expired.stderr if isinstance(expired.stderr, str) else "",
            timed_out=True,
        )
    except OSError as exc:
        return _Completed(returncode=-1, stdout="", stderr=str(exc), launch_error=str(exc))
    return _Completed(completed.returncode, completed.stdout, completed.stderr)


def _validate(version: str, *, label: str) -> str:
    if not isinstance(version, str) or not _VERSION_RE.match(version.strip()):
        raise PilotError(
            PilotFailure.PILOT_INPUT_INVALID,
            f"{label} must be an exact released version, got {version!r}",
        )
    return version.strip()


def parse_envelope(stdout: str) -> dict[str, object]:
    """Fallback extraction from stdout.

    The primary channel is the envelope file: CrewAI writes rich console output
    to stdout without always terminating it with a newline, so the sentinel can
    end up mid-line. This scans for the sentinel *anywhere* in a line rather
    than only at its start, for exactly that reason.
    """
    for line in stdout.splitlines():
        if RESULT_SENTINEL in line:
            payload = line.split(RESULT_SENTINEL, 1)[1].strip()
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise PilotError(
                    PilotFailure.SCENARIO_EXECUTION_FAILED,
                    f"the scenario emitted an unparsable envelope: {exc}",
                    evidence={"payload": payload[:2000]},
                ) from exc
            if not isinstance(parsed, dict):
                raise PilotError(
                    PilotFailure.SCENARIO_EXECUTION_FAILED,
                    "the scenario envelope was not a JSON object",
                )
            return parsed
    raise PilotError(
        PilotFailure.SCENARIO_EXECUTION_FAILED,
        (
            "the scenario produced no result envelope. It always emits one, so "
            "this means it died before reporting."
        ),
        evidence={"stdout": stdout[-4000:]},
    )


def _read_envelope(
    path: Path, *, stdout: str, stderr: str, returncode: int
) -> dict[str, object]:
    """Prefer the envelope file; fall back to stdout only if it is absent."""
    if path.is_file():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PilotError(
                PilotFailure.SCENARIO_EXECUTION_FAILED,
                f"the scenario wrote an unreadable envelope: {exc}",
                evidence={"returncode": returncode, "stderr": stderr[-4000:]},
            ) from exc
        if isinstance(parsed, dict):
            return parsed
        raise PilotError(
            PilotFailure.SCENARIO_EXECUTION_FAILED,
            "the scenario envelope was not a JSON object",
            evidence={"returncode": returncode},
        )
    try:
        return parse_envelope(stdout)
    except PilotError as failure:
        failure.evidence.setdefault("returncode", returncode)
        failure.evidence.setdefault("stderr", stderr[-4000:])
        raise


def check_process_consistency(envelope: dict[str, object], *, returncode: int) -> None:
    """The report and the exit status must agree, or neither is evidence."""
    status = envelope.get("status")
    if status == "pass" and returncode != 0:
        raise PilotError(
            PilotFailure.SCENARIO_EXECUTION_FAILED,
            f"the scenario reported success but exited {returncode}",
            evidence={"returncode": returncode},
        )
    if status == "fail" and returncode == 0:
        raise PilotError(
            PilotFailure.SCENARIO_EXECUTION_FAILED,
            "the scenario reported a failure but exited 0",
            evidence={"returncode": returncode},
        )
    if status not in {"pass", "fail"}:
        raise PilotError(
            PilotFailure.SCENARIO_EXECUTION_FAILED,
            f"the scenario reported an unknown status {status!r}",
        )


def raise_for_envelope(envelope: dict[str, object]) -> dict[str, object]:
    if envelope.get("status") == "pass":
        record = envelope.get("record")
        if not isinstance(record, dict):
            raise PilotError(
                PilotFailure.SCENARIO_EXECUTION_FAILED,
                "the scenario reported success without an adoption record",
            )
        return record

    raw = str(envelope.get("failure_class") or "")
    try:
        failure_class = PilotFailure(raw)
    except ValueError:
        raise PilotError(
            PilotFailure.SCENARIO_EXECUTION_FAILED,
            f"the scenario reported an unknown failure class {raw!r}",
            evidence={"envelope": envelope},
        ) from None
    evidence = envelope.get("evidence")
    raise PilotError(
        failure_class,
        str(envelope.get("detail") or "the scenario reported a failure"),
        evidence=evidence if isinstance(evidence, dict) else {"evidence": evidence},
    )


def _create_environment(venv_root: Path) -> Path:
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_root)
    except Exception as exc:  # noqa: BLE001
        raise PilotError(
            PilotFailure.PILOT_INPUT_INVALID,
            (
                f"could not create a clean virtual environment: {exc!r}. This is "
                "local and says nothing about the published packages."
            ),
        ) from exc
    python = _venv_python(venv_root)
    if not python.exists():
        raise PilotError(
            PilotFailure.PILOT_INPUT_INVALID,
            f"the created environment has no interpreter at {python}",
        )
    return python


def _install(python: Path, *, root: Path, adapter_version: str, timeout: int) -> str:
    requirement = f"{ADAPTER_DISTRIBUTION}[crewai]=={adapter_version}"
    result = _run(
        [
            str(python), "-m", "pip", "install", "--no-input",
            # Resolution is still bound to PyPI explicitly, and the adapter must
            # still arrive as a wheel. What is deliberately *not* used here is
            # `--no-cache-dir`: the CrewAI extra pulls a several-hundred-megabyte
            # dependency tree, and forcing a cold re-download of all of it on
            # every run buys no extra assurance while making the pilot slow and
            # flaky on ordinary connections. Byte-level provenance of the
            # published artifact is `examples/pip_only_conformance`'s control;
            # this pilot's subject is the governance behaviour.
            "--index-url", PYPI_INDEX_URL,
            "--only-binary", ADAPTER_DISTRIBUTION,
            # A large tree over a slow link needs more patience than pip's
            # defaults; a timeout here would otherwise surface as an install
            # failure attributed to the distribution.
            "--retries", "5",
            "--timeout", "60",
            requirement,
        ],
        cwd=root,
        timeout=timeout,
    )
    if result.timed_out:
        raise PilotError(
            PilotFailure.REGISTRY_INSTALL_FAILED,
            f"installing {requirement} timed out after {timeout}s",
            evidence={"timeout_seconds": timeout},
        )
    if result.launch_error is not None:
        raise PilotError(
            PilotFailure.REGISTRY_INSTALL_FAILED,
            f"pip could not be launched: {result.launch_error}",
        )
    if result.returncode != 0:
        raise PilotError(
            PilotFailure.REGISTRY_INSTALL_FAILED,
            f"pip could not install {requirement} from the index",
            evidence={
                "returncode": result.returncode,
                "stderr": result.stderr[-4000:],
            },
        )
    return result.stdout


def run_pilot(
    *,
    adapter_version: str = ADAPTER_VERSION,
    crewai_version: str = CREWAI_VERSION,
    timeout: int = 1800,
) -> PilotResult:
    """Install the published adapter with its CrewAI extra and run the A/B/C."""
    adapter = _validate(adapter_version, label="adapter version")
    framework = _validate(crewai_version, label="crewai version")
    if timeout <= 0:
        raise PilotError(
            PilotFailure.PILOT_INPUT_INVALID, "timeout must be a positive number of seconds"
        )

    forbidden = repository_roots()
    scenario_source = Path(__file__).resolve().parent / "scenario.py"

    with tempfile.TemporaryDirectory(prefix="nornyx-adoption-pilot-") as raw_tmp:
        root = Path(raw_tmp).resolve()
        python = _create_environment(root / "venv")
        install_log = _install(python, root=root, adapter_version=adapter, timeout=timeout)

        shutil.copyfile(scenario_source, root / "scenario.py")
        envelope_path = root / "envelope.json"
        command = [
            str(python), "scenario.py",
            "--expect-adapter", adapter,
            "--expect-crewai", framework,
            "--envelope", str(envelope_path),
        ]
        for entry in forbidden:
            command += ["--forbidden-root", entry]

        scenario = _run(command, cwd=root, timeout=timeout)
        if scenario.timed_out:
            raise PilotError(
                PilotFailure.SCENARIO_EXECUTION_FAILED,
                f"the scenario timed out after {timeout}s",
                evidence={"stderr": scenario.stderr[-2000:]},
            )
        if scenario.launch_error is not None:
            raise PilotError(
                PilotFailure.SCENARIO_EXECUTION_FAILED,
                f"the scenario could not be launched: {scenario.launch_error}",
            )

        envelope = _read_envelope(
            envelope_path, stdout=scenario.stdout, stderr=scenario.stderr,
            returncode=scenario.returncode,
        )

        check_process_consistency(envelope, returncode=scenario.returncode)
        record = raise_for_envelope(envelope)
        record["index_url"] = PYPI_INDEX_URL

    return PilotResult(
        adapter_version=adapter,
        crewai_version=framework,
        record=record,
        install_log=install_log[-2000:],
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="external_adoption_pilot",
        description=(
            "Install the published nornyx-agentic-adapters with its CrewAI extra "
            "and demonstrate governed vs ungoverned behavior on one action."
        ),
    )
    parser.add_argument("--adapter-version", default=ADAPTER_VERSION)
    parser.add_argument("--crewai-version", default=CREWAI_VERSION)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None, help="write the record to a file")
    args = parser.parse_args(argv)

    try:
        result = run_pilot(
            adapter_version=args.adapter_version,
            crewai_version=args.crewai_version,
            timeout=args.timeout,
        )
    except PilotError as failure:
        payload = {"status": "fail", **failure.as_dict()}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"FAIL  {failure.failure_class.value}", file=sys.stderr)
            print(f"      {failure.detail}", file=sys.stderr)
            attribution = (
                "the published distributions"
                if failure.attributable_to_distribution
                else "this pilot's invocation or local environment"
            )
            print(f"      attributed to: {attribution}", file=sys.stderr)
            print(f"      next step:     {failure.remedy}", file=sys.stderr)
        if args.out:
            args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    if args.out:
        args.out.write_text(
            json.dumps(result.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        return 0

    record = result.record
    delta = record.get("governance_delta", {})
    print(f"PASS  nornyx-agentic-adapters {result.adapter_version} + crewai {result.crewai_version}")
    print(f"      installed at   {record.get('environment', {}).get('site_packages')}")
    print(f"      contract       {record.get('governance_contract', {}).get('origin')}")
    print("")
    print("      variant                 executions  decisions  evidence")
    for variant in record.get("variants", []):
        print(
            f"      {variant['id']:<22}  {variant['executions']:>10}  "
            f"{variant['authorizations']:>9}  {len(variant['decision_events']):>8}"
        )
    print("")
    print(f"      ungoverned action reachable        : {delta.get('action_reachable_ungoverned')}")
    print(f"      permitted when authorized          : {delta.get('action_permitted_when_authorized')}")
    print(f"      prevented when unauthorized        : {delta.get('action_prevented_when_unauthorized')}")
    print(f"      evidence absent without governance : {delta.get('evidence_absent_ungoverned')}")
    print(f"      evidence present with governance   : {delta.get('evidence_present_when_governed')}")
    return 0
