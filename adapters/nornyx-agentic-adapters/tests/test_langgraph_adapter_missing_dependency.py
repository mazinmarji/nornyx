"""The LangGraph submodule reports its missing optional extra precisely."""

from __future__ import annotations

import importlib
import sys

import pytest

from nornyx_agentic_adapters import MissingOptionalDependencyError


def test_importing_langgraph_adapter_without_extra_raises_precise_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "langgraph" or name.startswith("langgraph."):
            raise ImportError(f"No module named {name!r} (simulated absence)")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.delitem(sys.modules, "nornyx_agentic_adapters.langgraph", raising=False)

    with pytest.raises(
        MissingOptionalDependencyError,
        match=r"pip install nornyx-agentic-adapters\[langgraph\]",
    ):
        importlib.import_module("nornyx_agentic_adapters.langgraph")
