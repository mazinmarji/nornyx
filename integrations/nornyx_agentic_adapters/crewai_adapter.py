"""CrewAI reference adapter (AN-005, ADR-0037).

Maps CrewAI agents onto declared Nornyx identities via `framework_bindings`
entries labeled ``crewai`` and wraps task work in kernel enforcement. CrewAI
is imported lazily and only when actually installed; the adapter degrades to
duck-typed objects exposing a ``role`` attribute so the enforcement path is
fully testable without the framework. The adapter never calls external
models, tools, networks, or credentials itself.
"""

from __future__ import annotations

from typing import Any, Callable

from .governance_kernel import GovernanceKernel, GovernanceViolation

FRAMEWORK = "crewai"


def crewai_available() -> bool:
    try:
        import crewai  # noqa: F401
    except Exception:
        return False
    return True


def agent_key(agent: Any) -> str:
    """Extract the stable framework key from a CrewAI-style agent."""

    role = getattr(agent, "role", None)
    if not isinstance(role, str) or not role:
        raise GovernanceViolation(
            "AN_ADAPTER_IDENTITY_UNKNOWN",
            "CrewAI agents must expose a non-empty role for identity mapping.",
        )
    return role


class CrewAIGovernanceAdapter:
    """Enforcement hook between CrewAI-style agents and one Nornyx kernel."""

    def __init__(self, kernel: GovernanceKernel | None):
        if kernel is None:
            raise GovernanceViolation(
                "AN_ADAPTER_HOOK_MISSING",
                "Enforcement requires a loaded, lock-verified governance "
                "kernel; refusing to run ungoverned.",
            )
        if kernel.framework != FRAMEWORK:
            raise GovernanceViolation(
                "AN_ADAPTER_FRAMEWORK_MISMATCH",
                f"The kernel was loaded for {kernel.framework!r}, not "
                f"{FRAMEWORK!r}.",
            )
        self.kernel = kernel

    def resolve_identity(self, agent: Any) -> str:
        return self.kernel.resolve_identity(agent_key(agent))

    def guarded_task(
        self,
        agent: Any,
        capability: str,
        work: Callable[..., Any],
        *,
        mission_id: str,
    ) -> Callable[..., Any]:
        """Wrap one unit of CrewAI task work with capability enforcement."""

        identity = self.resolve_identity(agent)

        def run(*args: Any, **kwargs: Any) -> Any:
            self.kernel.invoke_tool(identity, capability, mission_id=mission_id)
            return work(*args, **kwargs)

        return run
