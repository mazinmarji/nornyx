"""Shared, deterministic configuration for the CrewAI x Nornyx A/B example.

Importing this module sets the CrewAI telemetry/tracing kill switches *before*
any ``crewai`` import happens anywhere in the process, so the demonstration
produces no telemetry, no tracing-preference file, and no first-run banner.
Nothing here uses an API key, a network, a model, a subprocess, or an external
write. The same values feed both the plain (Variant A) and the Nornyx-governed
(Variant B) runs so the only intended difference is the presence of governance.
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
EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parents[1]
INTEGRATIONS = REPO_ROOT / "integrations"
SUPPORT_DIR = REPO_ROOT / "examples" / "agentic_network_support"
CONTRACT = SUPPORT_DIR / "support_network.nyx"

# Make the repo, the unpackaged adapters, and this example importable whether
# the entrypoint is ``compare.py`` (a script) or an importing test.
for _entry in (str(REPO_ROOT), str(INTEGRATIONS), str(EXAMPLE_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

# Contain any incidental CrewAI storage (memory/knowledge) writes in a temp dir
# — never inside the source tree.
os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(tempfile.gettempdir()) / "crewai_nornyx_ab_storage"),
)

# ---------------------------------------------------------------- constants
# `AS_OF` sits inside the contract's approval validity window and is passed
# explicitly for reproducibility. `MISSION` matches the contract goal id.
AS_OF = "2026-07-17T00:00:00Z"
MISSION = "GOAL-SUPPORT-001"

# Captured once at import — BEFORE any offline guard is installed — so that
# capturing the environment never triggers a subprocess inside the guard. On
# Linux ``platform.platform()`` lazily shells out (``uname``) for the processor;
# the offline demonstration itself must remain subprocess-free.
try:
    _PLATFORM = platform.platform()
except Exception:  # pragma: no cover - degrade to subprocess-free fields
    _PLATFORM = f"{platform.system()} {platform.release()} {platform.machine()}"

# CrewAI agent roles are exactly the `crewai` framework_bindings agent_key
# values declared in support_network.nyx.
ROLE_COORDINATOR = "support_coordinator"
ROLE_ADVISOR = "policy_advisor"
ROLE_REFUND = "refund_agent"
ROLE_ESCALATION = "escalation_agent"
ROLE_UNKNOWN = "billing_bot"  # deliberately unbound in the contract (S13)

# Externally supplied approval records. The adapter never creates these; it only
# validates a record that a human governance owner supplies out of band.
HUMAN_APPROVAL = {"role": "network_governance_owner", "actor_type": "human", "granted": True}
AI_APPROVAL = {"role": "network_governance_owner", "actor_type": "model", "granted": True}

# Deterministic, sanitized business input — fake data only.
SANITIZED_REQUEST = {
    "case_id": "case-1001",
    "text": "duplicate $12 charge on my order, please refund",
    "amount_usd": 12,
}

# Deterministic business outputs. Both variants must produce these identically
# on the allowed path.
CLASSIFICATION = "refund_under_limit"
POLICY_TEXT = "Policy P-12: refunds at or under $50 are auto-approvable."
REFUND_PROPOSAL = "Proposed refund of $12 for case-1001 (under the $50 limit)."
CUSTOMER_RESPONSE = "Your duplicate $12 charge is refunded. Reference: R-1001."
DELETE_RECORDS_OUTPUT = "removed 42 customer records"  # S2/S14 destructive stub


@contextmanager
def no_external_io():
    """Forbid external sockets, DNS, subprocess, and os.system; allow loopback.

    Must be entered AFTER crewai (and therefore asyncio) are imported: patching
    subprocess.Popen before asyncio.windows_events imports would break it, which
    is why the native tests install this kind of guard inside the test body.
    CrewAI's event bus uses a loopback socketpair, so loopback stays permitted.
    """

    import crewai  # noqa: F401  ensure crewai + asyncio are already imported

    real_connect = socket.socket.connect

    def loopback_only_connect(sock: socket.socket, address: object):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost"):
            return real_connect(sock, address)
        raise AssertionError(f"external connection blocked: {address!r}")

    def forbidden(*_args: object, **_kwargs: object):
        raise AssertionError("external operation blocked in the offline demonstration")

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


def capture_environment() -> dict[str, object]:
    """Record the exact runtime for the environment.json artifact."""

    import importlib.metadata as md

    import nornyx

    def _version(dist: str) -> str | None:
        try:
            return md.version(dist)
        except Exception:  # pragma: no cover - dist not installed
            return None

    try:
        import crewai

        crewai_version = getattr(crewai, "__version__", None) or _version("crewai")
    except Exception:  # pragma: no cover - crewai absent
        crewai_version = None

    return {
        "python_version": platform.python_version(),
        "platform": _PLATFORM,  # cached at import; never a subprocess under the guard
        "executable": sys.executable,
        "nornyx_version": _version("nornyx"),
        "nornyx_file": str(Path(nornyx.__file__).resolve()),
        "crewai_version": crewai_version,
        "langgraph_version": _version("langgraph"),
        "adapter_source": str((INTEGRATIONS / "nornyx_agentic_adapters").resolve()),
        "contract_path": str(CONTRACT.resolve()),
        "as_of": AS_OF,
        "mission_id": MISSION,
    }
