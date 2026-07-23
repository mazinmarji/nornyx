"""CrewAI adapter (ADR-0039 M2-B): the supported, framework-specific submodule
for CrewAI, built on this package's public contract (``AdapterMetadata``,
``CoverageInventory``, ``SurfaceBinding``, ``enforce``) and the core
``nornyx.agentic`` authorization SPI.

Requires the ``crewai`` extra (``pip install nornyx-agentic-adapters[crewai]``).
Importing this submodule without it installed raises
``MissingOptionalDependencyError`` with an actionable message, not a bare
``ImportError``.

The only CrewAI extension point this package has verified is subclassing
``crewai.tools.BaseTool`` and overriding ``_run`` — reached through
``Crew.kickoff()``'s native ReAct executor. CrewAI exposes no callback or
event-bus hook this package uses. Agent invocation, task invocation, and
CrewAI's own internal coworker-delegation mechanism have no verified, stable
public hook distinct from tool-level interception; ``COVERAGE_INVENTORY``
below declares them ``unsupported`` rather than wrapping them through
undocumented CrewAI internals.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nornyx.agentic import (
    SPI_VERSION,
    Authorizer,
    CapabilityRequest,
    EvaluationContext,
    EvidenceRecorder,
)

from ._compat import require_extra
from .binding import SurfaceBinding, validate_binding
from .coverage import CoverageInventory, SurfaceCoverage, SurfaceStatus
from .enforcement import enforce
from .errors import AdapterConfigurationError
from .metadata import AdapterMetadata

_crewai_tools = require_extra("crewai.tools", extra="crewai")
BaseTool = _crewai_tools.BaseTool

FRAMEWORK = "crewai"

METADATA = AdapterMetadata(
    adapter_name="nornyx-agentic-adapters-crewai",
    adapter_version="0.1.0",
    spi_version=SPI_VERSION,
    framework_name=FRAMEWORK,
    framework_version_range="==1.15.4",
    nornyx_version_range=">=1.8,<2",
)

COVERAGE_INVENTORY = CoverageInventory(
    entries=(
        SurfaceCoverage(
            surface="tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.WRAPPED,
            reason=(
                "Wrapped via a crewai.tools.BaseTool._run override, reached "
                "through Crew.kickoff()'s native ReAct executor."
            ),
        ),
        SurfaceCoverage(
            surface="agent_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "No public, stable CrewAI hook fires on agent invocation "
                "distinct from tool-level interception."
            ),
        ),
        SurfaceCoverage(
            surface="task_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "No public, stable CrewAI hook fires on task invocation "
                "distinct from tool-level interception."
            ),
        ),
        SurfaceCoverage(
            surface="delegation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "CrewAI's coworker delegation is implemented via its own "
                "internally generated tools; wrapping it would depend on "
                "undocumented CrewAI internals rather than a stable public "
                "hook."
            ),
        ),
        SurfaceCoverage(
            surface="handoff",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "CrewAI has no distinct handoff concept or public hook "
                "separate from delegation."
            ),
        ),
    )
)


def agent_identity_key(agent: Any) -> str:
    """The stable CrewAI-side key used for identity mapping: the agent's role.

    Fails closed with ``AdapterConfigurationError`` if the agent exposes no
    non-blank ``role`` string; never guesses at an identity from other agent
    attributes.
    """
    role = getattr(agent, "role", None)
    if not isinstance(role, str) or not role.strip():
        raise AdapterConfigurationError(
            "CrewAI agents must expose a non-empty 'role' string for identity mapping."
        )
    return role


def resolve_identity(authorizer: Authorizer, agent: Any) -> str:
    """Resolve a CrewAI agent to its declared Nornyx identity ref.

    Thin pass-through to ``Authorizer.resolve_identity``. An unknown or
    ambiguous framework binding raises ``nornyx.agentic.IdentityResolutionError``
    unchanged — already a fail-closed error, distinct from a policy ``Decision``.
    """
    return authorizer.resolve_identity(FRAMEWORK, agent_identity_key(agent))


class _GovernedTool(BaseTool):  # type: ignore[misc, valid-type]
    """A ``BaseTool`` whose ``_run`` enforces one declared (identity,
    capability) binding before running the adapter-owned action, exactly once.

    Per-instance enforcement state is attached via ``object.__setattr__``
    (bypassing pydantic field validation, the same pattern already proven by
    this repository's existing CrewAI reference adapter) rather than declared
    pydantic fields, since it carries live SPI objects, not tool configuration.
    """

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        binding: SurfaceBinding = self._nornyx_binding  # type: ignore[attr-defined]
        authorizer: Authorizer = self._nornyx_authorizer  # type: ignore[attr-defined]
        context: EvaluationContext = self._nornyx_context  # type: ignore[attr-defined]
        recorder: EvidenceRecorder = self._nornyx_recorder  # type: ignore[attr-defined]
        mission_id: str = self._nornyx_mission_id  # type: ignore[attr-defined]
        action: Callable[..., Any] = self._nornyx_action  # type: ignore[attr-defined]

        request = CapabilityRequest(
            identity_ref=binding.identity_ref, capability_ref=binding.capability_ref
        )
        result = enforce(
            authorizer,
            request,
            context=context,
            recorder=recorder,
            mission_id=mission_id,
            action=lambda: action(*args, **kwargs),
        )
        recorder.record_observation(
            "tool_invoked",
            mission_id=mission_id,
            actor_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
        )
        return result


def make_governed_tool(
    *,
    name: str,
    description: str,
    binding: SurfaceBinding,
    authorizer: Authorizer,
    context: EvaluationContext,
    recorder: EvidenceRecorder,
    mission_id: str,
    action: Callable[..., Any],
) -> Any:
    """Build a CrewAI ``BaseTool`` instance enforcing ``binding`` around ``action``.

    ``action`` is the adapter-owned callable performing the tool's real work;
    it never runs unless the SPI evaluates ALLOW for the declared
    ``(identity_ref, capability_ref)`` capability request. On completion, a
    ``tool_invoked`` post-action observation is recorded — never before
    ``action`` actually returns. ``binding`` is validated (fails closed on any
    blank required field) before the tool is constructed.
    """
    validate_binding(binding)
    tool = _GovernedTool(name=name, description=description)
    object.__setattr__(tool, "_nornyx_binding", binding)
    object.__setattr__(tool, "_nornyx_authorizer", authorizer)
    object.__setattr__(tool, "_nornyx_context", context)
    object.__setattr__(tool, "_nornyx_recorder", recorder)
    object.__setattr__(tool, "_nornyx_mission_id", mission_id)
    object.__setattr__(tool, "_nornyx_action", action)
    return tool


__all__ = [
    "COVERAGE_INVENTORY",
    "FRAMEWORK",
    "METADATA",
    "agent_identity_key",
    "make_governed_tool",
    "resolve_identity",
]
