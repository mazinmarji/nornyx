from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nornyx import __version__
from nornyx.checker import check_document, has_errors
from nornyx.cli import main
from nornyx.doctor import run_doctor
from nornyx.fmt import format_file
from nornyx.profiles import (
    DOMAIN_PROFILE_NAMES,
    GENERAL_CORE_CONCEPTS,
    PROFILE_NAMES,
    profile_document,
    profile_conformance_report,
    profile_compatibility_matrix,
    profile_pack,
    validate_profile_conformance,
    validate_profile_pack_catalog,
)


def test_profiles_command_lists_expected_profiles(capsys) -> None:
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert "ai_coding" in out
    assert "nornyx_language" in out
    assert "agentic_repo_harness" in out
    assert "telecom_ops" in out


def test_version_flag_reports_package_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    assert f"nornyx {__version__}" in capsys.readouterr().out


def test_init_check_fmt_explain_roundtrip(tmp_path: Path, capsys) -> None:
    target = tmp_path / "project.nyx"
    assert main(["init", "--profile", "ai_coding", "--name", "Demo", "--out", str(target)]) == 0
    assert target.exists()
    assert main(["check", str(target)]) == 0
    assert main(["fmt", str(target), "--write"]) == 0
    assert main(["fmt", str(target), "--check"]) == 0
    assert main(["explain", str(target), "GOAL-001"]) == 0
    out = capsys.readouterr().out
    assert "GOAL-001" in out


def test_doctor_json_shape(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    report = run_doctor(tmp_path)
    assert "repo_root" in report
    assert isinstance(report["checks"], list)


def test_doctor_command_reports_readiness(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "Nornyx doctor" in out
    assert "Overall: ready" in out


def test_doctor_command_can_emit_json(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    out = capsys.readouterr().out
    assert '"repo_root"' in out
    assert '"checks"' in out


def test_format_file_is_deterministic(tmp_path: Path) -> None:
    target = tmp_path / "sample.nyx"
    target.write_text("nornyx: '0.1'\nproject:\n  name: Demo\n", encoding="utf-8")
    first = format_file(target)
    target.write_text(first, encoding="utf-8")
    second = format_file(target)
    assert first == second


def test_builtin_profile_names_are_stable() -> None:
    expected = {
        "minimal",
        "standard",
        "ai_coding",
        "regulated",
        "legacy_upgrade",
        "nornyx_language",
        "agentic_repo_harness",
        "telecom_ops",
        "business_ops",
        "ai_governance",
        "finance_ops",
    }
    assert expected.issubset(set(PROFILE_NAMES))


def test_builtin_profile_metadata_files_exist() -> None:
    for profile in PROFILE_NAMES:
        assert Path("profiles", f"{profile}.yaml").exists()


def test_v03_domain_profile_pack_catalog_is_valid() -> None:
    assert validate_profile_pack_catalog() == []
    assert validate_profile_conformance() == []
    assert DOMAIN_PROFILE_NAMES == [
        "ai_coding",
        "agentic_repo_harness",
        "telecom_ops",
        "business_ops",
        "ai_governance",
        "finance_ops",
    ]


def test_v03_domain_profile_metadata_files_match_pack_contract() -> None:
    for name in DOMAIN_PROFILE_NAMES:
        path = Path("profiles", f"{name}.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        pack = profile_pack(name)

        assert payload["name"] == name
        assert payload["version"] == "v0.3"
        assert payload["core_surface"] == "v0.2"
        assert payload["status"] == "optional_profile"
        assert payload["core_concepts"] == GENERAL_CORE_CONCEPTS
        assert payload["conformance"]["migration"]
        assert payload == pack


def test_v03_domain_profile_generated_documents_are_checkable() -> None:
    for name in DOMAIN_PROFILE_NAMES:
        doc = profile_document(name, "DemoProject")
        diagnostics = check_document(doc)

        assert doc["nornyx"] == "0.2"
        assert doc["project"]["profile_pack"]["status"] == "optional_profile"
        assert "graph" in doc
        assert "contracts" in doc
        assert not diagnostics, [d.to_dict() for d in diagnostics]


def test_v03_domain_profiles_do_not_promote_domain_concepts_to_core() -> None:
    profile_only_terms = {"telecom_ops", "business_ops", "ai_governance", "finance_ops"}
    for name in DOMAIN_PROFILE_NAMES:
        pack = profile_pack(name)

        assert profile_only_terms.isdisjoint(pack["core_concepts"])
        assert "live agent runtime" in pack["non_goals"]
        assert "automatic approvals" in pack["non_goals"]
        assert "production deployment" in pack["non_goals"]


def test_v06_profile_conformance_report_is_complete() -> None:
    report = profile_conformance_report()

    assert report["schema"] == "nornyx.profile_conformance.v0.6"
    assert report["status"] == "conformant"
    assert report["conformance_level"] == "v0.6"
    assert report["issues"] == []
    assert {profile["name"] for profile in report["profiles"]} == set(DOMAIN_PROFILE_NAMES)
    assert set(report["compatibility_matrix"]) == set(DOMAIN_PROFILE_NAMES)


def test_v06_profile_compatibility_matrix_has_no_conflicts_or_unknown_profiles() -> None:
    matrix = profile_compatibility_matrix()
    known = set(DOMAIN_PROFILE_NAMES)

    for name, row in matrix.items():
        assert name in known
        assert set(row["compatible_with"]) <= known
        assert set(row["requires_review_with"]) <= known
        assert set(row["conflicts_with"]) <= known
        assert name not in row["compatible_with"]
        assert name not in row["requires_review_with"]
        assert name not in row["conflicts_with"]
        assert not (set(row["compatible_with"]) & set(row["conflicts_with"]))


def test_v06_profile_stability_decisions_are_explicit() -> None:
    readiness = {profile_pack(name)["conformance"]["v1_readiness"] for name in DOMAIN_PROFILE_NAMES}

    assert "stable_candidate" in readiness
    assert "profile_candidate" in readiness
    assert "optional_candidate" in readiness
    assert profile_pack("finance_ops")["conformance"]["v1_readiness"] == "optional_candidate"


def test_distinct_language_showcase_is_checkable() -> None:
    assert main(["check", "examples/nornyx_distinct_language_showcase.nyx"]) == 0
