"""CrewAI adapter (ADR-0039 M2-B): the supported, framework-specific submodule
for CrewAI, built on this package's public contract (``AdapterMetadata``,
``CoverageInventory``, ``SurfaceBinding``, ``enforce``) and the core
``nornyx.agentic`` authorization SPI.

Requires the ``crewai`` extra (``pip install nornyx-agentic-adapters[crewai]``).
Importing this submodule without it installed raises
``MissingOptionalDependencyError`` with an actionable message, not a bare
``ImportError``.

The only CrewAI extension point this package has verified is subclassing
``crewai.tools.BaseTool`` and overriding ``_run`` (the SYNCHRONOUS tool path)
— reached through ``Crew.kickoff()``'s native ReAct executor. CrewAI exposes
no callback or event-bus hook this package uses. This adapter does NOT override
``_arun``: CrewAI's asynchronous tool path (``arun``/``_arun``) is not a
governed surface — the inherited ``BaseTool._arun`` raises
``NotImplementedError``, so the wrapped action never runs and no observation is
recorded. Agent invocation, task invocation, and CrewAI's own internal
coworker-delegation mechanism likewise have no verified, stable public hook
distinct from tool-level interception; ``COVERAGE_INVENTORY`` below declares
async tool invocation and all of these ``unsupported`` rather than wrapping
them through undocumented CrewAI internals.

Importing this module fails closed unless the installed ``crewai`` distribution
is exactly the single tested version (``METADATA.framework_version_range``): a
different installed version raises ``AdapterConfigurationError``, a missing
distribution raises ``MissingOptionalDependencyError``.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from typing import Any

from nornyx.agentic import (
    SPI_VERSION,
    Authorizer,
    CapabilityRequest,
    Decision,
    EvaluationContext,
    EvidenceRecorder,
)

from ._compat import require_extra
from .binding import SurfaceBinding, validate_binding
from .coverage import CoverageInventory, SurfaceCoverage, SurfaceStatus
from .enforcement import enforce
from .errors import AdapterConfigurationError
from .metadata import AdapterMetadata

# The single CrewAI version this M2-B adapter is tested and supported against.
# ``METADATA.framework_version_range`` and the import-time compatibility check
# both derive from this constant, so they can never drift apart.
_REQUIRED_CREWAI_VERSION = "1.15.4"

_crewai_tools = require_extra("crewai.tools", extra="crewai")
BaseTool = _crewai_tools.BaseTool

# The crewai extra guarantees pydantic; import it only after require_extra has
# confirmed the framework is present, so a missing extra still yields the
# precise MissingOptionalDependencyError rather than a bare pydantic ImportError.
from pydantic import BaseModel as _PydanticBaseModel  # noqa: E402


def _installed_crewai_version() -> str:
    """Return the installed ``crewai`` distribution version, or fail closed.

    Missing or malformed installed-version metadata is treated as an
    unsupported configuration (``AdapterConfigurationError``), never assumed
    compatible.
    """
    try:
        version = importlib.metadata.version("crewai")
    except Exception as exc:  # PackageNotFoundError / malformed metadata: fail closed
        raise AdapterConfigurationError(
            "Unable to determine the installed 'crewai' version (missing or "
            "malformed distribution metadata); this adapter requires exactly "
            f"crewai=={_REQUIRED_CREWAI_VERSION}."
        ) from exc
    if not isinstance(version, str) or not version.strip():
        raise AdapterConfigurationError(
            "The installed 'crewai' distribution reports an empty or malformed "
            f"version; this adapter requires exactly crewai=={_REQUIRED_CREWAI_VERSION}."
        )
    return version


def _check_crewai_version(installed: str) -> None:
    """Fail closed unless ``installed`` is exactly the supported CrewAI version.

    A wider range is never assumed: this adapter names exactly one tested
    framework version and refuses any other, rather than silently running
    against an untested CrewAI.
    """
    if installed != _REQUIRED_CREWAI_VERSION:
        raise AdapterConfigurationError(
            f"Unsupported CrewAI version {installed!r}: this adapter (ADR-0039 "
            f"M2-B) is tested and supported only against "
            f"crewai=={_REQUIRED_CREWAI_VERSION}. Install the pinned version, "
            f"e.g. 'pip install nornyx-agentic-adapters[crewai]'."
        )


_check_crewai_version(_installed_crewai_version())

FRAMEWORK = "crewai"

METADATA = AdapterMetadata(
    adapter_name="nornyx-agentic-adapters-crewai",
    adapter_version="0.3.0",
    spi_version=SPI_VERSION,
    framework_name=FRAMEWORK,
    framework_version_range=f"=={_REQUIRED_CREWAI_VERSION}",
    nornyx_version_range=">=1.10,<2",
)

COVERAGE_INVENTORY = CoverageInventory(
    entries=(
        SurfaceCoverage(
            surface="tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.WRAPPED,
            reason=(
                "Synchronous tool execution wrapped via a "
                "crewai.tools.BaseTool._run override, reached through "
                "Crew.kickoff()'s native ReAct executor. Covers the sync "
                "_run path only; see async_tool_invocation for the async path."
            ),
        ),
        SurfaceCoverage(
            surface="async_tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "M2-B overrides only the synchronous BaseTool._run and does NOT "
                "override _arun. CrewAI's asynchronous tool path (arun/_arun) is "
                "not a governed surface: the inherited BaseTool._arun raises "
                "NotImplementedError, so the wrapped action never executes and no "
                "tool_invoked observation is recorded. Callers must not infer that "
                "synchronous tool coverage extends to async execution."
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
        # The authorizing delegation, when the identity holds this capability
        # only by delegation. Read from the decision's own public basis — never
        # inferred from the tool's arguments, which are caller-controlled.
        authorizing: list[str] = []

        def capture(decision: Decision) -> None:
            if decision.allowed:
                authorizing.extend(
                    item.ref for item in decision.basis if item.kind == "delegation"
                )

        def run_action() -> Any:
            # A failure here is a runtime failure of an ALREADY-AUTHORIZED
            # action: enforce() calls this only on ALLOW. Recording it states
            # the same failure the LangGraph adapter states on its equivalent
            # path, instead of leaving an authorized-but-failed execution with
            # no observation at all. A denial never reaches this callable, so
            # it can never produce a runtime_failed.
            try:
                return action(*args, **kwargs)
            except Exception:
                recorder.record_observation(
                    "runtime_failed",
                    mission_id=mission_id,
                    actor_ref=binding.identity_ref,
                    capability_ref=binding.capability_ref,
                    delegation_ref=authorizing[0] if authorizing else None,
                )
                raise

        result = enforce(
            authorizer,
            request,
            context=context,
            recorder=recorder,
            mission_id=mission_id,
            action=run_action,
            on_decision=capture,
        )
        recorder.record_observation(
            "tool_invoked",
            mission_id=mission_id,
            actor_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
            # Omitted entirely when the capability was held directly: the
            # recorder drops None fields, so a directly-held capability's
            # observation is byte-identical to what it was before.
            delegation_ref=authorizing[0] if authorizing else None,
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
    args_schema: type | None = None,
) -> Any:
    """Build a CrewAI ``BaseTool`` instance enforcing ``binding`` around ``action``.

    ``action`` is the adapter-owned callable performing the tool's real work;
    it never runs unless the SPI evaluates ALLOW for the declared
    ``(identity_ref, capability_ref)`` capability request. On completion, a
    ``tool_invoked`` post-action observation is recorded — never before
    ``action`` actually returns. ``binding`` is validated (fails closed on any
    blank required field) before the tool is constructed.

    When the ALLOW decision's public basis names a delegation — that is, when
    the identity holds the capability only by delegation — that delegation is
    carried into the ``tool_invoked`` observation as ``delegation_ref``, so the
    observation states the same possession ground the ``capability_allowed``
    decision event does and the stream validates. It is read from the decision,
    never from the tool's arguments, and is absent when the capability is held
    directly.

    ``args_schema`` is an optional CrewAI-compatible pydantic ``BaseModel``
    subclass describing the tool's structured inputs. When supplied it is
    exposed to CrewAI so the executor validates and passes structured arguments
    through the governed ``_run`` — the validated arguments reach ``action``
    only after an ALLOW decision, never bypassing authorization. When omitted
    (the default), behavior is unchanged: a no-argument governed tool. An
    ``args_schema`` that is not a pydantic ``BaseModel`` subclass fails closed
    at construction with ``AdapterConfigurationError``. The schema describes
    tool inputs only; the authorizer, recorder, binding, and other governance
    state are attached out-of-band via ``object.__setattr__`` and are never
    part of the schema (and so are never serialized as tool arguments).

    This is NOT arbitrary CrewAI-tool wrapping: it constructs a governed tool
    from an explicit ``action`` and (optional) ``args_schema``.
    """
    validate_binding(binding)
    if args_schema is not None and not (
        isinstance(args_schema, type) and issubclass(args_schema, _PydanticBaseModel)
    ):
        raise AdapterConfigurationError(
            "args_schema must be a CrewAI-compatible pydantic BaseModel subclass "
            f"or None; got {args_schema!r}."
        )
    if args_schema is None:
        tool = _GovernedTool(name=name, description=description)
    else:
        tool = _GovernedTool(name=name, description=description, args_schema=args_schema)
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
