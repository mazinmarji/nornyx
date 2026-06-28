from __future__ import annotations

from pathlib import Path


README = Path("README.md")
AUDIT = Path("docs/53_README_COMMAND_CONSISTENCY_AUDIT.md")


def test_readme_quick_start_commands_are_valid() -> None:
    readme = README.read_text(encoding="utf-8")

    # Adoption quickstart uses the installed console script against the example
    # contract, and documents the `python -m nornyx.cli` fallback.
    assert "nornyx check examples/governed_delivery_control_plane.nyx" in readme
    assert "nornyx generate examples/governed_delivery_control_plane.nyx" in readme
    assert "nornyx schema --version 1.0" in readme
    assert "python -m nornyx.cli" in readme


def test_readme_command_audit_preserves_safety_boundary() -> None:
    audit = AUDIT.read_text(encoding="utf-8")

    assert "python -m nornyx.cli" in audit
    assert "console script remains valid after install" in audit
    assert "does not change CLI behavior" in audit
    assert "GOAL-100" in audit
