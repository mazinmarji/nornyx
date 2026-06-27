from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.editor_tools import (
    completion_items,
    document_symbols,
    editor_manifest,
    lsp_diagnostics_for_text,
    syntax_highlighting_spec,
)
from nornyx.parser import load_nyx


def test_editor_manifest_exposes_safe_local_tooling_contract() -> None:
    manifest = editor_manifest()

    assert manifest["schema"] == "nornyx.editor_manifest.v0.1"
    assert ".nyx" in manifest["file_extensions"]
    assert manifest["safety"]["starts_language_server"] is False
    assert manifest["safety"]["network_used"] is False
    assert "nornyx.cli fmt" in manifest["formatting"]["command"]


def test_syntax_highlighting_spec_mentions_core_and_extension_blocks() -> None:
    spec = syntax_highlighting_spec()
    top_pattern = spec["patterns"][0]["match"]

    assert spec["scope_name"] == "source.nornyx"
    assert "project" in top_pattern
    assert "connectors" in top_pattern


def test_lsp_diagnostics_convert_checker_diagnostics_to_lsp_shape() -> None:
    diagnostics = lsp_diagnostics_for_text(
        """
nornyx: "0.1"
project: {}
agents:
  - name: Builder
    policy: MissingPolicy
""".strip()
    )
    by_code = {item["code"]: item for item in diagnostics}

    assert by_code["MISSING_PROJECT_NAME"]["severity"] == 1
    assert by_code["UNKNOWN_POLICY_REFERENCE"]["source"] == "nornyx"
    assert by_code["UNKNOWN_POLICY_REFERENCE"]["data"]["path"] == "agents.Builder.policy"


def test_lsp_diagnostics_return_parse_error_with_range() -> None:
    diagnostics = lsp_diagnostics_for_text("nornyx: [\n")

    assert diagnostics[0]["code"] == "PARSE_ERROR"
    assert diagnostics[0]["severity"] == 1
    assert diagnostics[0]["range"]["start"]["line"] == 1


def test_completion_items_include_references_from_document() -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    items = completion_items(doc, path="agent.policy", prefix="Safe")

    assert items == [
        {
            "label": "SafeEditPolicy",
            "kind": 18,
            "detail": "Reference from `policies`",
            "insertText": "SafeEditPolicy",
        }
    ]


def test_document_symbols_include_project_and_named_blocks() -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    symbols = document_symbols(doc)
    names = {item["name"] for item in symbols}

    assert "GovernedDeliveryControlPlane" in names
    assert "Builder" in names
    assert "DevHarness" in names


def test_editor_cli_commands_write_json(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "editor_manifest.json"
    diagnostics_path = tmp_path / "diagnostics.json"
    completions_path = tmp_path / "completions.json"
    symbols_path = tmp_path / "symbols.json"

    assert main(["editor-manifest", "--out", str(manifest_path)]) == 0
    assert (
        main(
            [
                "lsp-diagnostics",
                "examples/governed_delivery_control_plane.nyx",
                "--out",
                str(diagnostics_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "complete",
                "examples/governed_delivery_control_plane.nyx",
                "--path",
                "agent.policy",
                "--prefix",
                "Safe",
                "--out",
                str(completions_path),
            ]
        )
        == 0
    )
    assert main(["symbols", "examples/governed_delivery_control_plane.nyx", "--out", str(symbols_path)]) == 0

    out = capsys.readouterr().out
    assert "Editor manifest written" in out
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["language_id"] == "nornyx"
    assert json.loads(diagnostics_path.read_text(encoding="utf-8")) == []
    assert json.loads(completions_path.read_text(encoding="utf-8"))[0]["label"] == "SafeEditPolicy"
    assert any(
        item["name"] == "DevHarness"
        for item in json.loads(symbols_path.read_text(encoding="utf-8"))
    )
