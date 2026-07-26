"""Shared, deterministic configuration for the CrewAI x Nornyx governance benchmark.

Importing this module sets the CrewAI telemetry/tracing kill switches *before*
any ``crewai`` import happens anywhere in the process, so the benchmark produces
no telemetry, no tracing-preference file, and no first-run banner. Nothing here
uses an API key, a network, an external model, or a subprocess.

The same values feed Variant A (plain) and Variant B (governed) so the only
intended difference between them is the presence of Nornyx governance.

Why the evaluation instant is pinned
------------------------------------
``nornyx.agentic`` deliberately reads no wall clock: ``validation_as_of``
governs load-time contract validation and ``EvaluationContext.decision_at``
governs every temporal action semantic (identity/membership/delegation/
approval/revocation validity). A benchmark that wants byte-reproducible results
must therefore pin both. ``AS_OF`` below is that pin; it sits inside the
contract's approval and evidence validity windows.
"""

from __future__ import annotations

import os

# These must be set before the first `crewai` import in this process.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
# `false` keeps tracing off; `CREWAI_TESTING=true` short-circuits CrewAI's
# first-run tracing consent (no banner, no preference file written). Neither
# flag changes the LLM or the Crew.kickoff() execution path.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_TESTING", "true")

import platform  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

# ---------------------------------------------------------------- repo layout
BENCHMARK_DIR = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARK_DIR.parents[1]
CONTRACT_DIR = BENCHMARK_DIR / "contract"
CONTRACT = CONTRACT_DIR / "remediation_network.nyx"
LOCK = CONTRACT_DIR / "nornyx.agentic_network.lock"
GENERATED_ARTIFACTS = CONTRACT_DIR / "control_artifacts"

# Make this benchmark's own modules importable whether the entrypoint is
# ``benchmark.py`` (run as a script) or an importing test. The repo root is
# deliberately NOT added: ``nornyx`` and ``nornyx_agentic_adapters`` must resolve
# from installed distributions, never from an accidental source-tree import.
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

# Contain any incidental CrewAI storage (memory/knowledge) writes in a temp dir
# — never inside the source tree.
os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(tempfile.gettempdir()) / "crewai_nornyx_benchmark_storage"),
)

# ---------------------------------------------------------------- constants
# The pinned evaluation instant (see the module docstring). It sits inside the
# contract's approval window and its governance-evidence validity window.
AS_OF = "2026-07-17T00:00:00Z"
MISSION = "GOAL-REMEDIATION-001"

# The producer label this benchmark stamps on every emitted runtime event.
PRODUCER_ID = "examples.crewai_governance_benchmark"
PRODUCER_TYPE = "framework_adapter"

# CrewAI agent roles. These are exactly the `crewai` framework_bindings
# agent_key values declared in remediation_network.nyx — except ROLE_UNMAPPED,
# which is deliberately declared nowhere (the unknown-identity scenario).
ROLE_INTAKE = "intake_agent"
ROLE_ANALYST = "case_analyst"
ROLE_REMEDIATION = "remediation_agent"
ROLE_COMPLIANCE = "compliance_officer"
ROLE_UNMAPPED = "billing_bot"

# The approval requirement id declared by the agentic_network profile module.
APPROVAL_REF = "agentic_network_authority"
# The evidence refs that approval requires; an approval missing either is
# rejected with APPROVAL_EVIDENCE_MISSING.
APPROVAL_EVIDENCE = ("approval_record", "agentic_network_contract_review")
HUMAN_APPROVER_ROLE = "network_governance_owner"

# Composed from subprocess-free fields ONLY. ``platform.platform()`` is avoided
# entirely (not merely cached) because on Linux it lazily shells out via
# ``uname`` for the processor — and the complete benchmark, including this
# module's import, must never spawn a subprocess. ``system``/``release``/
# ``machine`` read ``os.uname()`` or environment variables, never a child process.
try:
    _PLATFORM = "-".join(
        part
        for part in (platform.system(), platform.release(), platform.machine())
        if part
    )
except Exception:  # pragma: no cover - last-resort, still subprocess-free
    _PLATFORM = sys.platform


@contextmanager
def no_external_io():
    """Forbid external sockets, DNS, subprocess, and os.system; allow loopback.

    Must be entered AFTER crewai (and therefore asyncio) are imported: patching
    subprocess.Popen before asyncio imports its platform event loop would break
    it. CrewAI's event bus uses a loopback socketpair, so loopback stays
    permitted; anything reaching off-box raises instead.
    """

    import crewai  # noqa: F401  ensure crewai + asyncio are already imported

    real_connect = socket.socket.connect

    def loopback_only_connect(sock: socket.socket, address: object):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(sock, address)
        raise AssertionError(f"external connection blocked: {address!r}")

    def forbidden(*_args: object, **_kwargs: object):
        raise AssertionError("external operation blocked in the offline benchmark")

    saved = (
        socket.socket.connect,
        socket.create_connection,
        socket.getaddrinfo,
        subprocess.run,
        subprocess.Popen,
        os.system,
    )
    socket.socket.connect = loopback_only_connect
    socket.create_connection = forbidden
    socket.getaddrinfo = forbidden
    subprocess.run = forbidden
    subprocess.Popen = forbidden
    os.system = forbidden
    try:
        yield
    finally:
        (
            socket.socket.connect,
            socket.create_connection,
            socket.getaddrinfo,
            subprocess.run,
            subprocess.Popen,
            os.system,
        ) = saved


def _distribution_version(dist: str) -> str | None:
    import importlib.metadata as md

    try:
        return md.version(dist)
    except Exception:  # pragma: no cover - distribution not installed
        return None


def capture_environment() -> dict[str, object]:
    """Record the exact runtime for the environment.json artifact.

    Every version is read from *installed distribution metadata*
    (``importlib.metadata``), not from a source path, so the report states what
    is genuinely installed. ``*_module_file`` is recorded alongside it so a
    reviewer can see whether a distribution resolves to a site-packages copy or
    to an editable checkout — both are installed distributions, but only one is
    a wheel.
    """

    import nornyx
    import nornyx_agentic_adapters
    from nornyx.agentic import SPI_VERSION

    import crewai

    crewai_version = getattr(crewai, "__version__", None) or _distribution_version("crewai")

    return {
        "python_version": platform.python_version(),
        "platform": _PLATFORM,  # cached at import; never a subprocess under the guard
        "executable": sys.executable,
        "nornyx_version": _distribution_version("nornyx"),
        "nornyx_module_file": str(Path(nornyx.__file__).resolve()),
        "nornyx_agentic_spi_version": SPI_VERSION,
        "adapters_version": _distribution_version("nornyx-agentic-adapters"),
        "adapters_module_file": str(Path(nornyx_agentic_adapters.__file__).resolve()),
        "adapters_package_published_on_pypi": False,
        "adapters_install_source": "repository (adapters/nornyx-agentic-adapters)",
        "crewai_version": crewai_version,
        "contract_path": str(CONTRACT.resolve()),
        "lock_path": str(LOCK.resolve()),
        "as_of": AS_OF,
        "mission_id": MISSION,
    }
