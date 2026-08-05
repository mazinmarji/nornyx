"""Supported LangGraph node adapter (ADR-0039 M2-C / ADR-0042).

The adapter consumes only LangGraph's public ``Runtime.execution_info``. It
maps a governed node surface to a logical operation, the public task id to an
occurrence, and the public one-based node attempt to a Nornyx attempt. On
checkpoint resume LangGraph restarts ``node_attempt`` at one; the adapter uses
the validated recorder prefix to offset that new execution segment.

Only synchronous StateGraph node callables are covered. Async nodes, remote
execution, undocumented internals, subgraph-wide interception, and tool-node
internals are explicitly outside this first supported surface.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import threading
from collections.abc import Callable
from typing import Any

from nornyx.agentic import (
    SPI_VERSION,
    Authorizer,
    CapabilityRequest,
    EvaluationContext,
    EvidenceRecorder,
    RuntimeOccurrence,
)

from ._compat import require_extra
from .binding import SurfaceBinding, validate_binding
from .coverage import CoverageInventory, SurfaceCoverage, SurfaceStatus
from .errors import AdapterConfigurationError, AdapterDenied
from .metadata import AdapterMetadata

_REQUIRED_LANGGRAPH_VERSION = "1.2.2"

_runtime_module = require_extra("langgraph.runtime", extra="langgraph")
_errors_module = require_extra("langgraph.errors", extra="langgraph")
Runtime = _runtime_module.Runtime
GraphBubbleUp = _errors_module.GraphBubbleUp


def _installed_langgraph_version() -> str:
    try:
        version = importlib.metadata.version("langgraph")
    except Exception as exc:
        raise AdapterConfigurationError(
            "Unable to determine the installed 'langgraph' version; this "
            f"adapter requires exactly langgraph=={_REQUIRED_LANGGRAPH_VERSION}."
        ) from exc
    if not isinstance(version, str) or not version.strip():
        raise AdapterConfigurationError(
            "The installed 'langgraph' distribution reports an empty or "
            f"malformed version; expected {_REQUIRED_LANGGRAPH_VERSION}."
        )
    return version


def _check_langgraph_version(installed: str) -> None:
    if installed != _REQUIRED_LANGGRAPH_VERSION:
        raise AdapterConfigurationError(
            f"Unsupported LangGraph version {installed!r}: this M2-C adapter is "
            f"tested only with langgraph=={_REQUIRED_LANGGRAPH_VERSION}."
        )


_check_langgraph_version(_installed_langgraph_version())

FRAMEWORK = "langgraph"

METADATA = AdapterMetadata(
    adapter_name="nornyx-agentic-adapters-langgraph",
    adapter_version="0.3.0",
    spi_version=SPI_VERSION,
    framework_name=FRAMEWORK,
    framework_version_range=f"=={_REQUIRED_LANGGRAPH_VERSION}",
    nornyx_version_range=">=1.10,<2",
)

COVERAGE_INVENTORY = CoverageInventory(
    entries=(
        SurfaceCoverage(
            surface="sync_node_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.WRAPPED,
            reason=(
                "Synchronous StateGraph node execution is authorized through "
                "public Runtime.execution_info metadata, including native retry, "
                "loop, parallel-branch, interrupt, and checkpoint-resume behavior."
            ),
        ),
        SurfaceCoverage(
            surface="async_node_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason="M2-C supplies no asynchronous node wrapper.",
        ),
        SurfaceCoverage(
            surface="graph_topology",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNWRAPPED,
            reason=(
                "The caller owns StateGraph construction and must wrap each "
                "governed node explicitly."
            ),
        ),
        SurfaceCoverage(
            surface="remote_or_distributed_execution",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason="No remote service or distributed executor is attested.",
        ),
        SurfaceCoverage(
            surface="subgraph_and_tool_node_internals",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "Subgraphs and prebuilt ToolNode internals are not implicitly "
                "intercepted; their callable surfaces require separate wrappers."
            ),
        ),
    )
)


def node_identity_key(node_key: str) -> str:
    """Return one non-blank public LangGraph node key for identity mapping."""

    if not isinstance(node_key, str) or not node_key.strip():
        raise AdapterConfigurationError(
            "LangGraph node keys must be non-empty strings for identity mapping."
        )
    return node_key


def resolve_identity(authorizer: Authorizer, node_key: str) -> str:
    """Resolve a LangGraph node key through declared framework bindings."""

    return authorizer.resolve_identity(FRAMEWORK, node_identity_key(node_key))


def make_governed_node(
    *,
    binding: SurfaceBinding,
    authorizer: Authorizer,
    context: EvaluationContext,
    recorder: EvidenceRecorder,
    mission_id: str,
    action: Callable[[Any], Any],
) -> Callable[[Any, Runtime], Any]:
    """Wrap one synchronous LangGraph node with occurrence-aware enforcement.

    The caller must pass an explicit-mode ``EvidenceRecorder`` and reuse the
    same mission id and resumed recorder for the whole graph run. ``action`` is
    called with the node state only and is never invoked after a denied policy
    decision or malformed execution metadata.
    """

    validate_binding(binding)
    if not callable(action):
        raise AdapterConfigurationError("LangGraph action must be callable.")
    if inspect.iscoroutinefunction(action):
        raise AdapterConfigurationError(
            "M2-C supports synchronous LangGraph node actions only."
        )
    try:
        RuntimeOccurrence(binding.surface, "langgraph.probe", 1)
        recorder.max_recorded_attempt(
            mission_id=mission_id,
            operation_id=binding.surface,
            occurrence_id="langgraph.probe",
        )
    except (TypeError, ValueError) as exc:
        raise AdapterConfigurationError(
            "LangGraph nodes require a schema-valid SurfaceBinding.surface and "
            "an explicit occurrence-aware EvidenceRecorder."
        ) from exc

    attempt_bases: dict[tuple[str, str, str], int] = {}
    attempt_lock = threading.Lock()

    def governed_node(state: Any, runtime: Runtime) -> Any:
        execution_info = getattr(runtime, "execution_info", None)
        if execution_info is None:
            raise AdapterConfigurationError(
                "LangGraph Runtime.execution_info is required for governed nodes."
            )
        task_id = getattr(execution_info, "task_id", None)
        node_attempt = getattr(execution_info, "node_attempt", None)
        if not isinstance(task_id, str) or not task_id:
            raise AdapterConfigurationError(
                "LangGraph ExecutionInfo.task_id must be a non-empty string."
            )
        if type(node_attempt) is not int or node_attempt < 1:
            raise AdapterConfigurationError(
                "LangGraph ExecutionInfo.node_attempt must be a positive integer."
            )

        cache_key = (mission_id, binding.surface, task_id)
        with attempt_lock:
            if node_attempt == 1:
                base = recorder.max_recorded_attempt(
                    mission_id=mission_id,
                    operation_id=binding.surface,
                    occurrence_id=task_id,
                )
                attempt_bases[cache_key] = base
            else:
                base = attempt_bases.get(cache_key)
                if base is None:
                    highest = recorder.max_recorded_attempt(
                        mission_id=mission_id,
                        operation_id=binding.surface,
                        occurrence_id=task_id,
                    )
                    base = max(0, highest - (node_attempt - 1))
                    attempt_bases[cache_key] = base

        try:
            occurrence = RuntimeOccurrence(
                binding.surface, task_id, base + node_attempt
            )
        except (TypeError, ValueError) as exc:
            raise AdapterConfigurationError(
                "LangGraph execution metadata cannot be represented by the "
                "runtime-events occurrence schema."
            ) from exc

        request = CapabilityRequest(
            identity_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
        )
        decision = authorizer.evaluate(request, context=context)
        recorder.record_occurrence_decision(
            decision, mission_id=mission_id, occurrence=occurrence
        )
        if not decision.allowed:
            with attempt_lock:
                attempt_bases.pop(cache_key, None)
            raise AdapterDenied(decision)

        try:
            result = action(state)
        except GraphBubbleUp:
            # LangGraph bubble-up exceptions (including interrupts and parent
            # commands) are control flow, not execution failure. Drop the
            # in-process base so a resumed/re-entered node offsets from the
            # now-validated incomplete prefix when node_attempt restarts at 1.
            with attempt_lock:
                attempt_bases.pop(cache_key, None)
            raise
        except Exception:
            recorder.record_occurrence_observation(
                "runtime_failed",
                mission_id=mission_id,
                occurrence=occurrence,
                actor_ref=binding.identity_ref,
                capability_ref=binding.capability_ref,
            )
            raise

        recorder.record_occurrence_observation(
            "agent_invoked",
            mission_id=mission_id,
            occurrence=occurrence,
            actor_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
        )
        with attempt_lock:
            attempt_bases.pop(cache_key, None)
        return result

    return governed_node


__all__ = [
    "COVERAGE_INVENTORY",
    "FRAMEWORK",
    "METADATA",
    "make_governed_node",
    "node_identity_key",
    "resolve_identity",
]
