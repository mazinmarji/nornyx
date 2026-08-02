"""Import-boundary tests: no framework leakage in either direction."""

from __future__ import annotations

import subprocess
import sys


def test_base_import_works_with_no_framework_installed() -> None:
    """A clean subprocess import must succeed and touch neither crewai nor langgraph.

    Run in a fresh subprocess (not the current process) so an earlier test in
    the same run that happens to import crewai/langgraph elsewhere cannot mask
    a real leak.
    """
    code = (
        "import sys\n"
        "import nornyx_agentic_adapters as naa\n"
        "assert naa.__version__ == '0.2.0'\n"
        "assert 'crewai' not in sys.modules\n"
        "assert 'langgraph' not in sys.modules\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_nornyx_core_never_imports_the_adapter_package() -> None:
    """Importing nornyx (core) alone must never pull in nornyx_agentic_adapters."""
    code = (
        "import sys\n"
        "import nornyx\n"
        "assert 'nornyx_agentic_adapters' not in sys.modules\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_no_module_level_framework_import_in_source() -> None:
    """Static check: no module-level `import crewai`/`import langgraph` anywhere
    in the base package's source.

    The framework-specific submodules (``crewai_adapter``, ``langgraph``) and
    the conformance suites reach their framework through
    ``_compat.require_extra``, which is a call rather than an import statement,
    so a missing extra raises an actionable ``MissingOptionalDependencyError``
    and importing the base package still pulls in neither framework.
    """
    import ast
    from pathlib import Path

    src_root = Path(__file__).resolve().parents[1] / "src" / "nornyx_agentic_adapters"
    for path in sorted(src_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        # Only the module's direct top-level statements count as "module-level"
        # imports; imports nested inside a function/class body are lazy and
        # permitted.
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # `level > 0` is a relative import of a sibling module inside
                # this package (for example `from ...langgraph import ...`,
                # which is this package's own adapter module, not the
                # framework). Only an absolute import can reach the framework.
                if node.level != 0:
                    continue
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not (name == "crewai" or name.startswith("crewai.")), (path, name)
                assert not (name == "langgraph" or name.startswith("langgraph.")), (path, name)
