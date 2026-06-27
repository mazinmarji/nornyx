from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .checker import CORE_TOP_LEVEL_BLOCKS, EXTENSION_TOP_LEVEL_BLOCKS

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "nornyx_v0_1.schema.json"
SCHEMA_REGISTRY = {
    "compat": SCHEMA_PATH,
    "0.1": SCHEMA_PATH,
    "0.2": ROOT / "schemas" / "nornyx_v0_2.schema.json",
    "1.0": ROOT / "schemas" / "nornyx_v1_0.schema.json",
}

FORMAL_GRAMMAR_V0_1 = """\
nornyx_document ::= yaml_mapping
yaml_mapping ::= version_block project_block core_block*
version_block ::= "nornyx" ":" "0.1"
project_block ::= "project" ":" mapping_with_name
core_block ::= constitution_block | intents_block | contexts_block | skills_block
             | policies_block | agents_block | harnesses_block | traces_block
             | evals_block | evidence_block | approvals_block | budgets_block
             | goals_block | deferred_extension_block
named_list_block ::= block_name ":" list(named_mapping)
graph_block ::= "graph" ":" mapping(nodes: list(graph_node), edges: list(graph_edge))
graph_node ::= mapping(id, kind, ref?)
graph_edge ::= mapping(from, to, relation?)
contract_block ::= "contracts" ":" list(mapping(name, nodes?, edges?, approval?, budget?))
adapter_block ::= "adapters" ":" list(mapping(name, kind, target_profile?, connector_refs?, policy_refs?, eval_refs?, evidence_refs?))
goal_entry ::= mapping(id, phase, goal, scope, non_goals, validation, evidence, approval, stop_rules)
deferred_extension_block ::= experimental | graph | contracts | adapters | connectors | guardrails
                           | capabilities | incidents | containment | supply_chain
"""


def _normalize_schema_version(version: str | float | int | None = "compat") -> str:
    if version is None:
        return "compat"
    text = str(version).strip().lower()
    aliases = {
        "": "compat",
        "default": "compat",
        "current": "compat",
        "v0.1": "0.1",
        "v0_1": "0.1",
        "v0.2": "0.2",
        "v0_2": "0.2",
        "v1.0": "1.0",
        "v1_0": "1.0",
    }
    return aliases.get(text, text)


def schema_path_for_version(version: str | float | int | None = "compat") -> Path:
    key = _normalize_schema_version(version)
    try:
        return SCHEMA_REGISTRY[key]
    except KeyError as exc:
        choices = ", ".join(sorted(SCHEMA_REGISTRY))
        raise ValueError(f"Unknown Nornyx schema version {version!r}; expected one of: {choices}") from exc


def schema_registry_summary() -> dict[str, str]:
    return {
        version: path.relative_to(ROOT).as_posix()
        for version, path in SCHEMA_REGISTRY.items()
    }


def load_schema(version: str | float | int | None = "compat") -> dict[str, Any]:
    return json.loads(schema_path_for_version(version).read_text(encoding="utf-8"))


def load_v01_schema(path: str | Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def schema_top_level_blocks(
    schema: dict[str, Any] | None = None,
    *,
    version: str | float | int | None = "compat",
) -> list[str]:
    active_schema = schema or load_schema(version)
    return list(active_schema.get("properties", {}).keys())


def schema_model_summary(version: str | float | int | None = "compat") -> dict[str, Any]:
    normalized_version = _normalize_schema_version(version)
    schema = load_schema(normalized_version)
    top_level_blocks = schema_top_level_blocks(schema)
    supported_versions = schema.get("x-nornyx-supported-versions", ["0.1"])
    release_version = schema.get("x-nornyx-release-version")
    summary_version = release_version or (
        supported_versions[-1] if isinstance(supported_versions, list) and supported_versions else normalized_version
    )
    return {
        "schema": schema.get("$id"),
        "schema_path": schema_path_for_version(normalized_version).relative_to(ROOT).as_posix(),
        "requested_version": normalized_version,
        "version": summary_version,
        "syntax": "yaml-compatible",
        "schema_role": schema.get("x-nornyx-schema-role", "compatibility_schema"),
        "supported_versions": supported_versions,
        "version_note": schema.get("x-nornyx-version-note", ""),
        "registry": schema_registry_summary(),
        "v0_2_contract_surface": {
            "graph": "Declared node/edge model for static semantic checks.",
            "contracts": "Generic contract list for graph, approval, and budget references.",
        },
        "v0_4_adapter_surface": {
            "adapters": "Contract-only ecosystem bridge metadata; no live connector execution.",
            "connector_conformance": "MCP/A2A manifests remain disabled by default and approval-gated.",
        },
        "v0_5_graph_validation_surface": {
            "relation_pairs": "Static checks for recognized graph relation source/target kinds.",
            "auditability": "Warnings for duplicate edges, self-edges, and missing contract approval/budget/evidence graph coverage.",
            "execution": "Graph validation is diagnostic only and does not execute graph edges.",
        },
        "core_top_level_blocks": CORE_TOP_LEVEL_BLOCKS,
        "deferred_extension_blocks": EXTENSION_TOP_LEVEL_BLOCKS,
        "schema_top_level_blocks": top_level_blocks,
        "migration": "YAML-compatible v0.1 documents remain valid inputs for the checker.",
    }


def validate_schema_model(version: str | float | int | None = "compat") -> list[str]:
    normalized_version = _normalize_schema_version(version)
    schema = load_schema(normalized_version)
    schema_blocks = set(schema_top_level_blocks(schema))
    expected = set(CORE_TOP_LEVEL_BLOCKS + EXTENSION_TOP_LEVEL_BLOCKS)
    issues: list[str] = []
    missing = sorted(expected - schema_blocks)
    extra = sorted(schema_blocks - expected)
    if missing:
        issues.append(f"schema missing top-level blocks: {missing}")
    if extra:
        issues.append(f"schema has unknown top-level blocks: {extra}")
    required = set(schema.get("required", []))
    if required != {"nornyx", "project"}:
        issues.append("schema required blocks must be exactly ['nornyx', 'project']")
    versions = set(schema.get("x-nornyx-supported-versions", []))
    expected_versions = {
        "compat": {"0.1", "0.2"},
        "0.1": {"0.1", "0.2"},
        "0.2": {"0.2"},
        "1.0": {"0.1", "0.2"},
    }[normalized_version]
    if expected_versions - versions:
        issues.append(f"schema {normalized_version} must declare support for {sorted(expected_versions)}")
    if normalized_version == "0.2" and "graph" not in schema.get("properties", {}):
        issues.append("v0.2 schema must include graph support")
    if normalized_version == "0.2" and "contracts" not in schema.get("properties", {}):
        issues.append("v0.2 schema must include contracts support")
    if normalized_version == "1.0" and schema.get("x-nornyx-schema-role") != "stable_generalized_contract_language_schema":
        issues.append("v1.0 schema must name the stable generalized contract-language role")
    return issues
