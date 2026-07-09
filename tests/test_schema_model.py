from __future__ import annotations

import json
from pathlib import Path

import nornyx.governed_package as governed_package
from nornyx.cli import main
from nornyx.checker import CORE_TOP_LEVEL_BLOCKS, EXTENSION_TOP_LEVEL_BLOCKS
from nornyx.schema_model import (
    FORMAL_GRAMMAR_V0_1,
    SCHEMA_REGISTRY,
    load_schema,
    load_v01_schema,
    schema_model_summary,
    schema_path_for_version,
    schema_registry_summary,
    schema_top_level_blocks,
    validate_schema_model,
)


ROOT = Path(__file__).resolve().parents[1]
VERSIONED_SCHEMA_FILES = [
    "nornyx_v0_1.schema.json",
    "nornyx_v0_2.schema.json",
    "nornyx_v1_0.schema.json",
]


def test_root_and_bundled_versioned_schemas_stay_in_sync() -> None:
    for name in VERSIONED_SCHEMA_FILES:
        root_schema = ROOT / "schemas" / name
        bundled_schema = ROOT / "nornyx" / "schemas" / name

        assert root_schema.read_text(encoding="utf-8") == bundled_schema.read_text(encoding="utf-8")


def test_governed_package_schema_tracks_validator_contract() -> None:
    schema = json.loads((ROOT / "nornyx" / "schemas" / "governed_package.schema.json").read_text(encoding="utf-8"))

    assert set(schema["required"]) == governed_package.REQUIRED_PACKAGE_FIELDS
    assert schema["properties"]["profile"]["const"] == governed_package.PROFILE_NAME
    assert set(schema["properties"]["risk_tier"]["enum"]) == governed_package.RISK_TIERS
    for field, expected in governed_package.SAFE_INSTALLATION_POLICY.items():
        assert schema["properties"]["installation_policy"]["properties"][field]["const"] is expected
    for field, expected in governed_package.SAFE_BOUNDARY.items():
        assert schema["properties"]["safety_boundary"]["properties"][field]["const"] is expected


def test_schema_model_matches_frozen_checker_surface() -> None:
    schema_blocks = set(schema_top_level_blocks())
    expected_blocks = set(CORE_TOP_LEVEL_BLOCKS + EXTENSION_TOP_LEVEL_BLOCKS)

    assert validate_schema_model() == []
    assert schema_blocks == expected_blocks
    assert validate_schema_model("0.2") == []
    assert validate_schema_model("1.0") == []


def test_schema_requires_yaml_compatible_migration_blocks() -> None:
    schema = load_v01_schema()

    assert schema["required"] == ["nornyx", "project"]
    assert schema["x-nornyx-schema-role"] == "compatibility_schema"
    assert schema["x-nornyx-supported-versions"] == ["0.1", "0.2"]
    assert schema["properties"]["nornyx"]["oneOf"][0]["const"] == "0.1"
    assert {"const": "0.2"} in schema["properties"]["nornyx"]["oneOf"]
    assert schema["properties"]["goals"]["items"]["$ref"] == "#/$defs/goal"
    assert schema["properties"]["graph"]["properties"]["nodes"]["items"]["$ref"] == "#/$defs/graphNode"
    assert schema["properties"]["contracts"]["items"]["$ref"] == "#/$defs/contract"
    assert "stop_rules" in schema["$defs"]["goal"]["required"]


def test_schema_registry_routes_versioned_schema_files() -> None:
    registry = schema_registry_summary()

    assert set(SCHEMA_REGISTRY) == {"compat", "0.1", "0.2", "1.0"}
    assert registry["compat"] == "schemas/nornyx_v0_1.schema.json"
    assert registry["0.1"] == "schemas/nornyx_v0_1.schema.json"
    assert registry["0.2"] == "schemas/nornyx_v0_2.schema.json"
    assert registry["1.0"] == "schemas/nornyx_v1_0.schema.json"
    assert schema_path_for_version("v0.2").as_posix().endswith("schemas/nornyx_v0_2.schema.json")


def test_versioned_schema_files_name_contract_surfaces() -> None:
    v02 = load_schema("0.2")
    v10 = load_schema("1.0")

    assert v02["$id"].endswith("nornyx_v0_2.schema.json")
    assert v02["x-nornyx-schema-role"] == "versioned_schema"
    assert v02["x-nornyx-supported-versions"] == ["0.2"]
    assert v02["properties"]["graph"]["properties"]["nodes"]["items"]["$ref"] == "#/$defs/graphNode"
    assert v02["properties"]["contracts"]["items"]["$ref"] == "#/$defs/contract"
    assert "does not enable graph runtime execution" in v02["x-nornyx-version-note"]

    assert v10["$id"].endswith("nornyx_v1_0.schema.json")
    assert v10["x-nornyx-schema-role"] == "stable_generalized_contract_language_schema"
    assert v10["x-nornyx-release-version"] == "1.0.0"
    assert "static graph and generic contract model" in v10["x-nornyx-stable-surface"]
    assert "unlock GOAL-100" in v10["x-nornyx-safety-boundary"]


def test_schema_summary_and_grammar_are_available_through_cli(capsys) -> None:
    assert main(["schema"]) == 0
    payload = capsys.readouterr().out
    assert "nornyx_v0_1.schema.json" in payload
    assert "yaml-compatible" in payload

    assert main(["schema", "--version", "0.2"]) == 0
    payload = capsys.readouterr().out
    assert "nornyx_v0_2.schema.json" in payload

    assert main(["schema", "--version", "1.0"]) == 0
    payload = capsys.readouterr().out
    assert "stable_generalized_contract_language_schema" in payload

    assert main(["schema", "--format", "grammar"]) == 0
    grammar = capsys.readouterr().out
    assert FORMAL_GRAMMAR_V0_1.strip() in grammar
    assert "goal_entry" in grammar
    assert "graph_block" in grammar
    assert "contract_block" in grammar


def test_schema_model_summary_keeps_migration_explicit() -> None:
    summary = schema_model_summary()

    assert summary["version"] == "0.2"
    assert summary["requested_version"] == "compat"
    assert summary["syntax"] == "yaml-compatible"
    assert summary["schema_role"] == "compatibility_schema"
    assert summary["supported_versions"] == ["0.1", "0.2"]
    assert "YAML-compatible v0.1 documents remain valid" in summary["migration"]
    assert "historical v0.1 schema path" in summary["version_note"]
    assert summary["v0_2_contract_surface"]["graph"].startswith("Declared node/edge")
    assert summary["v0_5_graph_validation_surface"]["execution"].startswith("Graph validation is diagnostic")
    assert summary["registry"]["0.2"] == "schemas/nornyx_v0_2.schema.json"
    assert schema_model_summary("1.0")["version"] == "1.0.0"


def test_schema_version_split_plan_names_target_files_and_boundaries() -> None:
    plan = Path("docs/51_SCHEMA_VERSION_SPLIT_PLAN.md").read_text(encoding="utf-8")

    assert "schemas/nornyx_v0_1.schema.json" in plan
    assert "schemas/nornyx_v0_2.schema.json" in plan
    assert "schemas/nornyx_v1_0.schema.json" in plan
    assert "This is a planning artifact only" in plan
    assert "enable runtime execution" in plan
    assert "unlock GOAL-100" in plan


def test_schema_targets_guide_aligns_examples_and_boundaries() -> None:
    guide = Path("docs/52_SCHEMA_TARGETS_AND_EXAMPLES.md").read_text(encoding="utf-8")

    assert "python -m nornyx.cli schema --version 0.2" in guide
    assert "python -m nornyx.cli schema --version 1.0" in guide
    assert "examples/governed_delivery_control_plane.nyx" in guide
    assert "examples/nornyx_graph_demo.nyx" in guide
    assert "execute graph edges" in guide
    assert "unlock GOAL-100" in guide


def test_five_minute_adoption_includes_schema_targets_and_boundary() -> None:
    guide = Path("docs/49_NORNYX_5_MINUTE_ADOPTION.md").read_text(encoding="utf-8")

    assert "python -m nornyx.cli schema" in guide
    assert "python -m nornyx.cli schema --version 0.2" in guide
    assert "python -m nornyx.cli schema --version 1.0" in guide
    assert "Schema inspection is not document validation" in guide
    assert "unlock GOAL-100" in guide
