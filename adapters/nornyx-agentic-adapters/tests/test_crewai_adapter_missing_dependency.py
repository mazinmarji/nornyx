"""The CrewAI submodule must give a precise, actionable diagnostic — not a
bare ``ImportError`` — when the ``crewai`` extra is not installed.

Runs unconditionally (no ``importorskip``), including in environments where
crewai actually is installed, by simulating its absence at the
``importlib.import_module`` layer the adapter's own ``require_extra()``
helper calls. This is a wiring-correctness test: it confirms
``crewai_adapter.py`` calls ``require_extra`` with ``extra="crewai"`` (so the
error names the right install command), not a re-test of ``require_extra``
itself (already exhaustively covered by ``test_compat.py``).
"""

from __future__ import annotations

import importlib
import sys

import pytest

from nornyx_agentic_adapters import MissingOptionalDependencyError


def test_importing_crewai_adapter_without_crewai_raises_precise_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name in ("crewai", "crewai.tools"):
            raise ImportError(f"No module named {name!r} (simulated absence)")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    monkeypatch.delitem(sys.modules, "nornyx_agentic_adapters.crewai_adapter", raising=False)

    with pytest.raises(MissingOptionalDependencyError, match=r"pip install nornyx-agentic-adapters\[crewai\]"):
        importlib.import_module("nornyx_agentic_adapters.crewai_adapter")

    # Python's import machinery evicts a module that raised mid-execution from
    # sys.modules automatically; once monkeypatch reverts at teardown, a later
    # test's fresh import of this module sees the real crewai install again.
