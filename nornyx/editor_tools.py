from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .checker import CORE_TOP_LEVEL_BLOCKS, EXTENSION_TOP_LEVEL_BLOCKS, check_document
from .errors import Diagnostic


LSP_SEVERITY = {"error": 1, "warning": 2, "info": 3, "hint": 4}
COMPLETION_KIND = {
    "text": 1,
    "method": 2,
    "property": 10,
    "value": 12,
    "reference": 18,
    "snippet": 15,
}
NAMED_BLOCKS = {
    "goals": ("goal", "id"),
    "contexts": ("context", "name"),
    "skills": ("skill", "name"),
    "policies": ("policy", "name"),
    "agents": ("agent", "name"),
    "harnesses": ("harness", "name"),
    "traces": ("trace", "name"),
    "evals": ("eval", "name"),
    "approvals": ("approval", "name"),
    "budgets": ("budget", "name"),
}
REFERENCE_FIELDS = {
    "agent.policy": "policies",
    "agent.skills": "skills",
    "harness.context": "contexts",
    "flow.agent": "agents",
    "flow.eval": "evals",
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _named_values(doc: dict[str, Any], block: str) -> list[str]:
    values = []
    key = NAMED_BLOCKS.get(block, ("", "name"))[1]
    for item in _as_list(doc.get(block)):
        if isinstance(item, dict) and item.get(key):
            values.append(str(item[key]))
    return values


def syntax_highlighting_spec() -> dict[str, Any]:
    top_blocks = sorted(CORE_TOP_LEVEL_BLOCKS + EXTENSION_TOP_LEVEL_BLOCKS)
    return {
        "schema": "nornyx.syntax_highlighting.v0.1",
        "scope_name": "source.nornyx",
        "file_extensions": [".nyx"],
        "base_language": "yaml-compatible",
        "patterns": [
            {
                "name": "keyword.control.nornyx.top-level",
                "match": rf"^({'|'.join(top_blocks)}):",
                "description": "Canonical and deferred Nornyx top-level blocks.",
            },
            {
                "name": "entity.name.type.nornyx.named-entry",
                "match": r"^\s*-\s+(name|id):\s*.+$",
                "description": "Named block entries used for references and symbols.",
            },
            {
                "name": "variable.other.nornyx.reference-field",
                "match": r"^\s*(policy|context|agent|eval|tool|connector|model):\s*.+$",
                "description": "Reference-like fields that editor tooling can complete.",
            },
            {
                "name": "string.quoted.nornyx",
                "match": r"\"[^\"\\]*(?:\\.[^\"\\]*)*\"|'[^']*'",
                "description": "YAML-compatible quoted strings.",
            },
            {
                "name": "comment.line.number-sign.nornyx",
                "match": r"#.*$",
                "description": "YAML-compatible comments.",
            },
        ],
        "note": "This is a local editor metadata scaffold, not a Tree-sitter grammar.",
    }


def editor_manifest() -> dict[str, Any]:
    return {
        "schema": "nornyx.editor_manifest.v0.1",
        "file_extensions": [".nyx"],
        "language_id": "nornyx",
        "formatting": {
            "command": "python -m nornyx.cli fmt ${file} --write",
            "check_command": "python -m nornyx.cli fmt ${file} --check",
        },
        "diagnostics": {
            "command": "python -m nornyx.cli lsp-diagnostics ${file}",
            "source": "nornyx",
        },
        "autocomplete": {
            "command": "python -m nornyx.cli complete ${file}",
            "top_level_blocks": sorted(CORE_TOP_LEVEL_BLOCKS),
            "deferred_extension_blocks": sorted(EXTENSION_TOP_LEVEL_BLOCKS),
        },
        "syntax_highlighting": syntax_highlighting_spec(),
        "safety": {
            "starts_language_server": False,
            "network_used": False,
            "connectors_enabled": False,
            "files_mutated": False,
        },
    }


def completion_items(
    doc: dict[str, Any] | None = None,
    *,
    path: str | None = None,
    prefix: str = "",
) -> list[dict[str, Any]]:
    items = []

    def add(label: str, kind: str, detail: str, insert_text: str | None = None) -> None:
        if prefix and not label.lower().startswith(prefix.lower()):
            return
        items.append(
            {
                "label": label,
                "kind": COMPLETION_KIND[kind],
                "detail": detail,
                "insertText": insert_text or label,
            }
        )

    if not path or path in {"", "$", "top", "top-level"}:
        for block in CORE_TOP_LEVEL_BLOCKS:
            insert = f"{block}:\n  - name: " if block in NAMED_BLOCKS else f"{block}: "
            add(block, "property", "Nornyx core top-level block", insert)
        for block in EXTENSION_TOP_LEVEL_BLOCKS:
            add(block, "property", "Deferred extension top-level block", f"{block}: ")
        return sorted(items, key=lambda item: item["label"])

    if doc:
        normalized_path = path.lower()
        reference_block = None
        for key, block in REFERENCE_FIELDS.items():
            if key in normalized_path:
                reference_block = block
                break
        if reference_block:
            for value in _named_values(doc, reference_block):
                add(value, "reference", f"Reference from `{reference_block}`")
            return sorted(items, key=lambda item: item["label"])

    for field in ["name", "role", "purpose", "policy", "context", "flow", "metrics", "required"]:
        add(field, "property", "Common Nornyx field", f"{field}: ")
    return sorted(items, key=lambda item: item["label"])


def document_symbols(doc: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = []
    project = doc.get("project")
    if isinstance(project, dict) and project.get("name"):
        symbols.append({"name": str(project["name"]), "kind": "project", "containerName": "project"})
    for block, (kind, key) in NAMED_BLOCKS.items():
        for item in _as_list(doc.get(block)):
            if isinstance(item, dict) and item.get(key):
                symbols.append(
                    {
                        "name": str(item[key]),
                        "kind": kind,
                        "containerName": block,
                    }
                )
    return symbols


def _top_level_line(lines: list[str], block: str) -> int:
    pattern = re.compile(rf"^{re.escape(block)}\s*:")
    for index, line in enumerate(lines):
        if pattern.search(line):
            return index
    return 0


def _named_entry_line(lines: list[str], block: str, name: str) -> int | None:
    start = _top_level_line(lines, block)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith((" ", "-")):
            break
        if re.search(rf"^\s*-\s+(name|id):\s*['\"]?{re.escape(name)}['\"]?\s*$", line):
            return index
    return None


def _line_for_path(text: str, path: str | None) -> int:
    if not path:
        return 0
    lines = text.splitlines()
    head = path.split(".")[0].split("[")[0]
    if head in CORE_TOP_LEVEL_BLOCKS or head in EXTENSION_TOP_LEVEL_BLOCKS:
        parts = path.split(".")
        if len(parts) >= 2:
            maybe_line = _named_entry_line(lines, parts[0], parts[1])
            if maybe_line is not None:
                if len(parts) >= 3:
                    field = parts[2]
                    for index in range(maybe_line + 1, len(lines)):
                        line = lines[index]
                        if re.search(r"^\s*-\s+(name|id):", line) or (
                            line and not line.startswith((" ", "-"))
                        ):
                            break
                        if re.search(rf"^\s*{re.escape(field)}\s*:", line):
                            return index
                return maybe_line
        return _top_level_line(lines, head)
    return 0


def _lsp_range(line: int, character: int = 0) -> dict[str, Any]:
    return {
        "start": {"line": max(0, line), "character": max(0, character)},
        "end": {"line": max(0, line), "character": max(1, character + 1)},
    }


def _diagnostic_to_lsp(diagnostic: Diagnostic, text: str) -> dict[str, Any]:
    line = _line_for_path(text, diagnostic.path)
    payload = {
        "range": _lsp_range(line),
        "severity": LSP_SEVERITY.get(diagnostic.level, 3),
        "code": diagnostic.code,
        "source": "nornyx",
        "message": diagnostic.message,
    }
    data = {}
    if diagnostic.path:
        data["path"] = diagnostic.path
    if diagnostic.hint:
        data["hint"] = diagnostic.hint
    if data:
        payload["data"] = data
    return payload


def lsp_diagnostics_for_text(text: str) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = int(mark.line) if mark else 0
        character = int(mark.column) if mark else 0
        return [
            {
                "range": _lsp_range(line, character),
                "severity": 1,
                "code": "PARSE_ERROR",
                "source": "nornyx",
                "message": f"Invalid Nornyx/YAML syntax: {exc}",
            }
        ]
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return [
            {
                "range": _lsp_range(0),
                "severity": 1,
                "code": "INVALID_TOP_LEVEL",
                "source": "nornyx",
                "message": "Top-level Nornyx document must be a mapping/object",
            }
        ]
    return [_diagnostic_to_lsp(diagnostic, text) for diagnostic in check_document(data)]


def lsp_diagnostics_for_file(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).read_text(encoding="utf-8")
    return lsp_diagnostics_for_text(source)


def write_json_payload(payload: Any, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output
