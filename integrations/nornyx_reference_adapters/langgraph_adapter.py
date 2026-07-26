"""LangGraph reference adapter (AN-005, ADR-0037).

Wraps LangGraph node callables with Nornyx kernel enforcement so every node
execution maps to a declared identity and capability and emits standardized
runtime-event evidence. LangGraph is imported lazily and only when building a
real `StateGraph`; guarded node callables themselves are framework-free.
"""

from __future__ import annotations

from typing import Any, Callable

from .governance_kernel import GovernanceKernel, GovernanceViolation

FRAMEWORK = "langgraph"


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401
    except Exception:
        return False
    return True


class LangGraphGovernanceAdapter:
    """Enforcement hook between LangGraph nodes and one Nornyx kernel."""

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

    def guard_node(
        self,
        node_key: str,
        capability: str,
        work: Callable[[dict], dict],
        *,
        mission_id: str,
    ) -> Callable[[dict], dict]:
        """Wrap one LangGraph node callable with capability enforcement."""

        identity = self.kernel.resolve_identity(node_key)

        def node(state: dict) -> dict:
            self.kernel.invoke_tool(identity, capability, mission_id=mission_id)
            return work(state)

        return node

    def build_governed_graph(
        self,
        nodes: dict[str, tuple[str, str, Callable[[dict], dict]]],
        edges: list[tuple[str, str]],
        *,
        mission_id: str,
        state_schema: Any = dict,
    ) -> Any:
        """Build a real LangGraph StateGraph with every node guarded.

        ``nodes`` maps node names to (framework agent key, capability, work).
        Requires the ``langgraph`` package; callers should check
        :func:`langgraph_available` first.
        """

        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(state_schema)
        for name, (node_key, capability, work) in nodes.items():
            graph.add_node(
                name,
                self.guard_node(node_key, capability, work, mission_id=mission_id),
            )
        for source, target in edges:
            graph.add_edge(
                START if source == "START" else source,
                END if target == "END" else target,
            )
        return graph.compile()
