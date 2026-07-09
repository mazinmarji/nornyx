from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-public-boundary.py"


def _load_public_boundary_module():
    spec = importlib.util.spec_from_file_location("check_public_boundary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_boundary_script_passes_repository_tree() -> None:
    module = _load_public_boundary_module()

    assert module.check_public_boundary(ROOT) == []


def test_public_boundary_script_reports_neutral_marker_without_echoing_value(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    marker = "PRIVATE_DOWNSTREAM_PLATFORM"
    (tmp_path / "README.md").write_text(marker, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "term_fingerprint=" in output
    assert "README.md:1" in output
    assert marker not in output


def test_public_boundary_script_uses_ignored_local_terms_without_echoing_values(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    (tmp_path / "notes.md").write_text(local_marker, encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert "term_fingerprint=" in output
    assert "notes.md:1" in output
    assert ".private-boundary-terms.txt" not in output
    assert local_marker not in output


def test_public_boundary_script_ignores_local_term_file_itself(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_public_boundary_module()
    local_marker = "LOCAL_PRIVATE_BOUNDARY_MARKER"
    (tmp_path / ".private-boundary-terms.txt").write_text(local_marker, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Clean public tree\n", encoding="utf-8")

    result = module.main(["--repo", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "public boundary check passed" in output
    assert local_marker not in output
