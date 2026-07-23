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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install and smoke-test one local nornyx-agentic-adapters wheel."
    )
    parser.add_argument("wheel", type=Path)
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
        _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "nornyx>=1.8,<2"], cwd=root)
        _run(
            [str(python), "-m", "pip", "install", "--no-deps", "--disable-pip-version-check", str(wheel)],
            cwd=root,
        )
        probe = _run([str(python), "-c", _RUNTIME_PROBE], cwd=root)
        payload = json.loads(probe.stdout)
        if payload["version"] != expected_version:
            raise RuntimeError(f"installed wheel reports version {payload['version']!r}, expected {expected_version!r}")
        if payload["crewai_in_sys_modules"] or payload["langgraph_in_sys_modules"]:
            raise RuntimeError(f"framework leaked into sys.modules: {payload!r}")

    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
