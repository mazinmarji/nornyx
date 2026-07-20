"""Isolated compatibility check against the *published* Nornyx 1.7.0 core.

This harness proves the example runs on the Nornyx distribution from PyPI, not
on the editable repository checkout. It:

1. creates a clean virtual environment;
2. installs only ``nornyx==1.7.0`` and ``crewai==1.15.4`` (plus their own
   dependencies) — no editable repo install;
3. makes the repository's ``integrations/`` directory importable for the
   unpackaged adapter, WITHOUT placing the repo root ahead of site-packages;
4. asserts the imported ``nornyx`` resolves to the installed distribution;
5. records the versions, the ``nornyx`` file path, and the adapter source; and
6. runs a governed smoke (real ``Crew.kickoff()`` + evidence validation).

The CrewAI adapter is deliberately NOT part of the ``nornyx`` wheel. This check
uses the wheel for the core and the repository's ``integrations/`` tree for the
adapter — exactly how a real consumer would wire it in Nornyx 1.7.0.

Unlike the offline example itself, this harness intentionally uses the network
and subprocesses: it installs packages with pip. Run it as a validation step,
not as part of the offline demonstration.

Usage::

    python examples/crewai_nornyx_comparison/verify_published_nornyx.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parents[1]
INTEGRATIONS = REPO_ROOT / "integrations"
CONTRACT = REPO_ROOT / "examples" / "agentic_network_support" / "support_network.nyx"

NORNYX_PIN = "nornyx==1.7.0"
CREWAI_PIN = "crewai==1.15.4"

# The child runs in the clean venv. It puts ONLY integrations/ on sys.path (not
# the repo root), so `import nornyx` must resolve to the installed wheel while
# `import nornyx_agentic_adapters` resolves to the unpackaged reference adapter.
CHILD = r'''
import os, sys, json, socket, subprocess, importlib.metadata as md
from pathlib import Path

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_TESTING", "true")

INTEGRATIONS = os.environ["AB_INTEGRATIONS"]
REPO_ROOT = os.environ["AB_REPO_ROOT"]
CONTRACT = os.environ["AB_CONTRACT"]
AS_OF = "2026-07-17T00:00:00Z"
MISSION = "GOAL-SUPPORT-001"

# Only the adapter tree goes on the path; never the repo root.
sys.path.insert(0, INTEGRATIONS)

import nornyx
nornyx_version = md.version("nornyx")
nornyx_file = str(Path(nornyx.__file__).resolve())
site_packages = str((Path(sys.prefix) / "Lib" / "site-packages").resolve())

resolves_to_installed = nornyx_file.startswith(site_packages)
not_repo_checkout = not nornyx_file.startswith(str(Path(REPO_ROOT).resolve()))

import asyncio  # bind windows_utils.Popen before any guard
_ = asyncio
import crewai
from crewai import Agent, BaseLLM, Crew, Process, Task
from crewai.tools import BaseTool

from nornyx.agentic_artifacts import build_agentic_network_lock, write_agentic_network_lock
from nornyx.agentic_evidence import validate_runtime_events
from nornyx.governance import GovernanceRegistry, compose_governance
from nornyx.parser import load_nyx
import nornyx_agentic_adapters
from nornyx_agentic_adapters.governance_kernel import GovernanceKernel, DeterministicClock
from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter

adapter_source = str(Path(nornyx_agentic_adapters.__file__).resolve())

class DeterministicLLM(BaseLLM):
    def __init__(self, tool_name, final_answer):
        super().__init__(model="nornyx-deterministic-offline")
        self._tool_name = tool_name
        self._final = final_answer
        self._n = 0
    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kw):
        self._n += 1
        if self._tool_name is not None and self._n == 1:
            return "Thought: t.\nAction: %s\nAction Input: {}" % self._tool_name
        return "Thought: done.\nFinal Answer: %s" % self._final
    def supports_function_calling(self): return False
    def supports_stop_words(self): return False
    def get_context_window_size(self): return 8192

class Tool(BaseTool):
    name: str = "classify_tool"
    description: str = "classify"
    def _run(self, *a, **k): return self._guarded()

registry = GovernanceRegistry.builtins()
document = load_nyx(CONTRACT)
composition = compose_governance(registry, profile_identity="agentic_network")
out = Path(os.environ["AB_OUT"]); out.mkdir(parents=True, exist_ok=True)
lock_path = write_agentic_network_lock(build_agentic_network_lock(document, composition), out / "n.lock")
kernel = GovernanceKernel.from_local_controls(CONTRACT, lock_path, framework="crewai", as_of=AS_OF, clock=DeterministicClock())
adapter = CrewAIGovernanceAdapter(kernel)

agent = Agent(role="support_coordinator", goal="g", backstory="b", allow_delegation=False, verbose=False, llm=DeterministicLLM("classify_tool", "refund_under_limit"))
identity = adapter.resolve_identity(agent)
guarded = adapter.guarded_task(agent, "classify_support_request", lambda: "refund_under_limit", mission_id=MISSION)
tool = Tool(); object.__setattr__(tool, "_guarded", guarded)
task = Task(description="Classify.", expected_output="a class", agent=agent, tools=[tool])

# loopback-only guard around kickoff
real_connect = socket.socket.connect
def loopback_only(sock, address):
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host in ("127.0.0.1","::1","localhost"):
        return real_connect(sock, address)
    raise AssertionError("external connect blocked")
def forbid(*a, **k): raise AssertionError("external op blocked")
socket.socket.connect = loopback_only
socket.create_connection = forbid
socket.getaddrinfo = forbid
subprocess.run = forbid
subprocess.Popen = forbid
os.system = forbid
result = str(Crew(agents=[agent], tasks=[task], process=Process.sequential).kickoff())
socket.socket.connect = real_connect

report = validate_runtime_events(
    document,
    composition,
    build_agentic_network_lock(document, composition),
    kernel.events_payload(),
    events_root=out,
)

print("AB_RESULT " + json.dumps({
    "nornyx_version": nornyx_version,
    "nornyx_file": nornyx_file,
    "resolves_to_installed_distribution": resolves_to_installed,
    "not_repo_checkout": not_repo_checkout,
    "crewai_version": getattr(crewai, "__version__", None),
    "adapter_source": adapter_source,
    "adapter_in_wheel": adapter_source.startswith(site_packages),
    "identity": identity,
    "contract_digest": kernel.contract_digest,
    "lock_digest": kernel.lock_digest,
    "kickoff_output": result,
    "evidence_status": report["status"],
    "event_count": report["event_count"],
}))
'''


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def verify(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    env_dir = out_dir / "clean_venv"
    print(f"[verify] creating clean venv at {env_dir}")
    venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
    if sys.platform == "win32":
        py = env_dir / "Scripts" / "python.exe"
    else:
        py = env_dir / "bin" / "python"

    print(f"[verify] installing {NORNYX_PIN} and {CREWAI_PIN} (published core)")
    _run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    _run([str(py), "-m", "pip", "install", "--quiet", NORNYX_PIN, CREWAI_PIN])

    child_path = out_dir / "_child_smoke.py"
    child_path.write_text(CHILD, encoding="utf-8")

    child_env = dict(os.environ)
    child_env.update(
        {
            "AB_INTEGRATIONS": str(INTEGRATIONS),
            "AB_REPO_ROOT": str(REPO_ROOT),
            "AB_CONTRACT": str(CONTRACT),
            "AB_OUT": str(out_dir / "smoke"),
            # Ensure the repo root is never inherited on the child's path.
            "PYTHONPATH": "",
            "PYTHONSAFEPATH": "1",
        }
    )
    print("[verify] running governed smoke on the installed core")
    proc = subprocess.run(
        [str(py), str(child_path)],
        cwd=str(out_dir),  # not the repo root, so cwd cannot shadow nornyx
        env=child_env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            "child smoke failed:\n" + proc.stdout + "\n" + proc.stderr
        )
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("AB_RESULT ")), None
    )
    if line is None:
        raise SystemExit("no AB_RESULT from child:\n" + proc.stdout + proc.stderr)
    data = json.loads(line[len("AB_RESULT "):])

    problems = []
    if data["nornyx_version"] != "1.7.0":
        problems.append(f"nornyx version is {data['nornyx_version']}, expected 1.7.0")
    if not data["resolves_to_installed_distribution"]:
        problems.append("nornyx did not resolve to the installed distribution")
    if not data["not_repo_checkout"]:
        problems.append("nornyx resolved to the repo checkout")
    if data["crewai_version"] != "1.15.4":
        problems.append(f"crewai version is {data['crewai_version']}, expected 1.15.4")
    if data["adapter_in_wheel"]:
        problems.append("adapter unexpectedly resolved inside the wheel/site-packages")
    if data["evidence_status"] != "pass":
        problems.append(f"evidence status is {data['evidence_status']}")
    data["ok"] = not problems
    data["problems"] = problems
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(tempfile.gettempdir()) / "nornyx_ab_published_verify"),
    )
    args = parser.parse_args(argv)
    data = verify(Path(args.out))
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
