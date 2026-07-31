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

# NOTE: this module deliberately does NOT put ``BENCHMARK_DIR`` on ``sys.path``.
# Doing so would publish generic module names (``config``, ``scenarios``,
# ``runtime``, ``report``…) as importable top-level modules for the rest of the
# process. In a full-suite run that collides with the identically named modules
# in ``examples/crewai_nornyx_comparison``, and whichever test imports first
# wins. Every module here is imported as ``crewai_governance_benchmark.<name>``
# instead; ``benchmark.py`` bootstraps ``examples/`` onto ``sys.path`` when it is
# run as a script. The repo root is never added: ``nornyx`` and
# ``nornyx_agentic_adapters`` must resolve from installed distributions, never
# from an accidental source-tree import.

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


# ------------------------------------------------- supported-adapter resolution
# The repository's unpackaged AN-005 reference adapters live at
# ``integrations/nornyx_reference_adapters/``. They used to claim the same import
# name as the supported ``nornyx-agentic-adapters`` distribution, so any process
# that put ``integrations/`` on ``sys.path`` — several of this repo's own tests
# do — silently rebound the name to the legacy tree. That collision is fixed at
# the source (finding F3, resolved), so this benchmark imports the supported
# adapter by its plain name and needs no import-shadowing workaround at all.
INTEGRATIONS_DIR = REPO_ROOT / "integrations"
LEGACY_REFERENCE_PACKAGE = "nornyx_reference_adapters"
SUPPORTED_ADAPTER_PACKAGE = "nornyx_agentic_adapters"


def load_supported_adapter():
    """Return ``(package, crewai_submodule)`` from the installed distribution.

    Fails closed rather than silently continuing if the name ever resolves to a
    source tree under ``integrations/`` again: the benchmark's entire claim is
    that it exercises the *supported* adapter.
    """
    import importlib

    package = importlib.import_module(SUPPORTED_ADAPTER_PACKAGE)
    resolved = Path(package.__file__ or "").resolve()
    if resolved == INTEGRATIONS_DIR or INTEGRATIONS_DIR in resolved.parents:
        raise RuntimeError(
            f"{SUPPORTED_ADAPTER_PACKAGE!r} resolved to {resolved} under "
            f"{INTEGRATIONS_DIR}; the benchmark requires the installed "
            "nornyx-agentic-adapters distribution."
        )
    return package, importlib.import_module(f"{SUPPORTED_ADAPTER_PACKAGE}.crewai_adapter")


def _install_kind(module: object) -> str:
    """Classify where an installed distribution's code actually came from.

    Records the *kind* rather than the path: an absolute local path is
    machine-specific noise in a committed artifact, but whether a distribution
    resolves to a built wheel in ``site-packages`` or to an editable checkout is
    a real, reviewable difference. Both are installed distributions; only one is
    a wheel.
    """
    raw = getattr(module, "__file__", None)
    if not raw:  # pragma: no cover - namespace package
        return "unknown"
    parts = {part.lower() for part in Path(raw).resolve().parts}
    if "site-packages" in parts or "dist-packages" in parts:
        return "site-packages (built distribution)"
    return "editable or source checkout"


def _repo_relative(path: Path) -> str:
    """A repository-relative path, never an absolute one from this machine."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:  # pragma: no cover - benchmark run from outside the repo
        return resolved.name


def capture_environment() -> dict[str, object]:
    """Record the exact runtime for the environment.json artifact.

    Every version is read from *installed distribution metadata*
    (``importlib.metadata``), not from a source path, so the report states what
    is genuinely installed.

    No absolute local path is recorded. Committed results are read by people on
    other machines, and a path like ``/home/someone/checkout/...`` is neither
    reproducible nor useful — it only makes a snapshot look more portable than
    it is. What matters about the location is captured as ``*_install_kind``,
    and governance inputs are recorded repository-relative.
    """

    import nornyx
    import nornyx_agentic_adapters
    from nornyx.agentic import SPI_VERSION

    import crewai

    crewai_version = getattr(crewai, "__version__", None) or _distribution_version("crewai")

    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": _PLATFORM,  # cached at import; never a subprocess under the guard
        "nornyx_version": _distribution_version("nornyx"),
        "nornyx_install_kind": _install_kind(nornyx),
        "nornyx_agentic_spi_version": SPI_VERSION,
        "adapters_version": _distribution_version("nornyx-agentic-adapters"),
        "adapters_install_kind": _install_kind(nornyx_agentic_adapters),
        "adapters_package_published_on_pypi": True,
        "adapters_install_source": (
            "installed distribution (0.2.0 is published; actual location is "
            "reported by adapters_install_kind)"
        ),
        "crewai_version": crewai_version,
        "contract_path": _repo_relative(CONTRACT),
        "lock_path": _repo_relative(LOCK),
        "as_of": AS_OF,
        "mission_id": MISSION,
    }
