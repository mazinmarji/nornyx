"""Install one built `nornyx-agentic-adapters` wheel into a clean venv and
smoke-test it: base import, SPI-version check, and a no-network `enforce()`
call using the installed package only (no editable install, no repository
path on `sys.path`).

Unlike the core `nornyx` package's wheel-smoke script, this does not attempt
to prove that `pip install` itself performs no network I/O (installing a
package legitimately needs the index to resolve `nornyx`) — it proves the
narrower, correctly-scoped claim this package actually makes: no network
access during *runtime* use of the installed package's public API.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv
import zipfile


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


_RUNTIME_PROBE = """
import json
import socket

def _blocked(*_a, **_k):
    raise AssertionError("network access attempted during adapter runtime operation")

socket.socket.connect = _blocked
socket.create_connection = _blocked

import nornyx_agentic_adapters as naa
from nornyx.agentic import CapabilityRequest, Decision, DecisionCode, DecisionEffect, EvaluationContext

class _Authorizer:
    def evaluate(self, request, *, context):
        return Decision(DecisionEffect.ALLOW, DecisionCode.ALLOWED, "")

class _Recorder:
    def record_decision(self, decision, *, mission_id):
        pass

naa.validate_binding(naa.SurfaceBinding("tool_invocation", "identity:agent-1", "capability:file_write"))
result = naa.enforce(
    _Authorizer(),
    CapabilityRequest(identity_ref="identity:agent-1", capability_ref="capability:file_write"),
    context=EvaluationContext(decision_at="2026-07-23T00:00:00Z", observed_subject_revision="git:0123456789abcdef0123456789abcdef01234567"),
    recorder=_Recorder(),
    mission_id="mission-1",
    action=lambda: "ok",
)
assert result == "ok"

print(json.dumps({
    "status": "pass",
    "version": naa.__version__,
    "crewai_in_sys_modules": "crewai" in __import__("sys").modules,
    "langgraph_in_sys_modules": "langgraph" in __import__("sys").modules,
}))
"""

_LANGGRAPH_PROBE = """
import nornyx_agentic_adapters.langgraph as adapter
assert adapter.METADATA.framework_version_range == "==1.2.2"
assert adapter.METADATA.nornyx_version_range == ">=1.10,<2"
assert adapter.COVERAGE_INVENTORY.wrapped()[0].surface == "sync_node_invocation"
print("LANGGRAPH_OK")
"""

# The runtime-conformance kit resolves its schema and contract fixture through
# importlib.resources. Both are package data, and package data is exactly what
# a wheel silently drops when it is not declared -- so this probe runs the kit
# from the INSTALLED distribution, in a fresh venv, from a directory that is not
# the repository, and proves the resources are really there.
_CONFORMANCE_PROBE = """
import json
import pathlib
import sys
import sysconfig

import nornyx_agentic_adapters.conformance as kit
from nornyx_agentic_adapters.conformance import (
    load_report_schema, run_conformance, serialize, validate_report,
)

# The code under test must be the installed one, not a source tree that
# happened to be importable.
purelib = pathlib.Path(sysconfig.get_paths()["purelib"]).resolve()
located = pathlib.Path(kit.__file__).resolve()
assert located.is_relative_to(purelib), (str(located), str(purelib))

schema = load_report_schema()
assert schema["$id"] == "nornyx.agentic_runtime_conformance.v1", schema.get("$id")

report = run_conformance(frameworks=["distribution", "enforcement_boundary"])
payload = report.as_dict()
diagnostics = validate_report(payload)
assert not diagnostics, diagnostics
assert payload["outcome"] == "pass", [
    c for s in payload["suites"] for c in s["cases"] if c["outcome"] == "fail"
]
assert payload["assurance_tier"] == "tier_2_cooperative"
# Observed, not declared: the guard names what it covered and reports a real
# count. A blocked attempt means the network was not reached, so the report
# deliberately carries no "network was used" flag to invert.
assert payload["safety"]["blocked_outbound_attempts"] == 0
assert payload["safety"]["blocked_process_attempts"] == 0
assert "enforcement_boundary" in payload["safety"]["guarded_suites"]
assert "network_used" not in payload["safety"]

# Determinism, from the installed distribution.
assert serialize(report) == serialize(run_conformance(
    frameworks=["distribution", "enforcement_boundary"]))

print("CONFORMANCE_OK " + json.dumps({
    "cases": sum(len(s["cases"]) for s in payload["suites"]),
    "schema": payload["schema"],
}, sort_keys=True))
"""


#: Package data the runtime-conformance kit resolves at run time. Checked
#: against the wheel's own manifest, because a missing resource otherwise
#: surfaces only when a consumer runs the kit from an installed distribution.
_REQUIRED_WHEEL_MEMBERS = (
    "nornyx_agentic_adapters/conformance/schemas/runtime_conformance_report.schema.json",
    "nornyx_agentic_adapters/conformance/fixtures/conformance_network.nyx",
)


def _assert_bundled_resources(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = [member for member in _REQUIRED_WHEEL_MEMBERS if member not in names]
    if missing:
        raise RuntimeError(
            "the wheel is missing bundled conformance resources "
            f"(declare them in [tool.setuptools.package-data]): {missing}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install and smoke-test one local nornyx-agentic-adapters wheel."
    )
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--core-wheel", type=Path)
    parser.add_argument("--with-langgraph", action="store_true")
    args = parser.parse_args(argv)
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        parser.error("wheel must identify a .whl file")
    expected_version = wheel.name.split("-")[1]

    with tempfile.TemporaryDirectory(prefix="nornyx-agentic-adapters-wheel-smoke-") as raw_tmp:
        root = Path(raw_tmp)
        venv_root = root / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_root)
        python = _venv_python(venv_root)
        if args.core_wheel is not None:
            core_wheel = args.core_wheel.resolve(strict=True)
            _run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    str(core_wheel),
                ],
                cwd=root,
            )
        else:
            _run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "nornyx>=1.10,<2",
                ],
                cwd=root,
            )
        _run(
            [str(python), "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheel)],
            cwd=root,
        )
        _assert_bundled_resources(wheel)
        probe = _run([str(python), "-c", _RUNTIME_PROBE], cwd=root)
        payload = json.loads(probe.stdout)
        if payload["version"] != expected_version:
            raise RuntimeError(f"installed wheel reports version {payload['version']!r}, expected {expected_version!r}")
        if payload["crewai_in_sys_modules"] or payload["langgraph_in_sys_modules"]:
            raise RuntimeError(f"framework leaked into sys.modules: {payload!r}")
        conformance = _run([str(python), "-c", _CONFORMANCE_PROBE], cwd=root)
        if "CONFORMANCE_OK" not in conformance.stdout:
            raise RuntimeError("the installed runtime-conformance kit did not complete")
        cli = _run(
            [
                str(python),
                "-m",
                "nornyx_agentic_adapters.conformance",
                "--suite",
                "enforcement_boundary",
                "--summary",
            ],
            cwd=root,
        )
        if "tier_2_cooperative" not in cli.stdout:
            raise RuntimeError("the installed conformance entry point did not state its tier")
        if args.with_langgraph:
            _run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "langgraph==1.2.2",
                ],
                cwd=root,
            )
            probe = _run([str(python), "-c", _LANGGRAPH_PROBE], cwd=root)
            if "LANGGRAPH_OK" not in probe.stdout:
                raise RuntimeError("installed LangGraph adapter probe did not complete")

    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
