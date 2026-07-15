from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from nornyx.governance import (
    GovernanceError,
    GovernanceRegistry,
    compose_governance,
    import_architecture_evidence,
)
from nornyx.governance.runtime import evaluate_document_governance
from nornyx.profiles import profile_document

from symlink_support import create_symlink_or_skip


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
AS_OF = "2026-06-01T00:00:00Z"


def _document() -> dict[str, Any]:
    return yaml.safe_load(
        (EXAMPLES / "architecture_governance.nyx").read_text(encoding="utf-8")
    )


def _diagnostics(document: dict[str, Any], *, root: Path = EXAMPLES) -> tuple[Any, ...]:
    return evaluate_document_governance(
        document,
        registry=GovernanceRegistry.builtins(),
        as_of=AS_OF,
        document_root=root,
    )


def _codes(document: dict[str, Any]) -> set[str]:
    return {item.code for item in _diagnostics(document)}


def _evidence(document: dict[str, Any]) -> dict[str, Any]:
    return document["architecture_evidence"][0]


def _architecture(document: dict[str, Any]) -> dict[str, Any]:
    return document["architecture"]


def _wrong_schema(document: dict[str, Any]) -> None:
    _evidence(document)["schema"] = "nornyx.architecture_evidence.v2"


def _missing_subject_revision(document: dict[str, Any]) -> None:
    _evidence(document).pop("subject_revision")


def _revision_mismatch(document: dict[str, Any]) -> None:
    _evidence(document)["subject_revision"] = "git:other"


def _missing_hash(document: dict[str, Any]) -> None:
    _evidence(document).pop("artifact_sha256")


def _invalid_status(document: dict[str, Any]) -> None:
    _evidence(document)["status"] = "unknown"


def _different_check(document: dict[str, Any]) -> None:
    _evidence(document)["check_id"] = "different-check"


def _stale_evidence(document: dict[str, Any]) -> None:
    _evidence(document)["expires_at"] = "2026-05-01T00:00:00Z"


def _future_evidence(document: dict[str, Any]) -> None:
    _evidence(document)["generated_at"] = "2026-07-01T00:00:00Z"


def _missing_evidence(document: dict[str, Any]) -> None:
    document["architecture_evidence"] = []


def _failed_check(document: dict[str, Any]) -> None:
    _evidence(document)["status"] = "fail"


def _passing_violations(document: dict[str, Any]) -> None:
    _evidence(document)["violations"] = [
        {"id": "violation-1", "severity": "error", "message": "Forbidden edge."}
    ]


def _wrong_artifact_hash(document: dict[str, Any]) -> None:
    _evidence(document)["artifact_sha256"] = "sha256:" + "0" * 64


def _wrong_tool(document: dict[str, Any]) -> None:
    _evidence(document)["tool"] = "import-linter"


def _duplicate_evidence(document: dict[str, Any]) -> None:
    document["architecture_evidence"].append(deepcopy(_evidence(document)))


def _duplicate_component(document: dict[str, Any]) -> None:
    _architecture(document)["components"].append(
        deepcopy(_architecture(document)["components"][0])
    )


def _unknown_layer(document: dict[str, Any]) -> None:
    _architecture(document)["components"][0]["layer"] = "layer.unknown"


def _invalid_dependency_direction(document: dict[str, Any]) -> None:
    _architecture(document)["layers"][0]["may_depend_on"] = []


def _unknown_constraint_verifier(document: dict[str, Any]) -> None:
    _architecture(document)["constraints"][0]["verified_by"] = "missing-check"


def _unknown_exception(document: dict[str, Any]) -> None:
    _architecture(document)["architecture_exceptions"] = ["EXC-MISSING"]


Mutation = Callable[[dict[str, Any]], None]


def test_architecture_example_and_neutral_report_import_are_valid() -> None:
    document = _document()

    assert _diagnostics(document) == ()
    imported = import_architecture_evidence(
        "architecture_reports/dependency_boundaries.json",
        allowed_root=EXAMPLES,
    )
    assert imported == _evidence(document)


def test_architecture_profile_resolves_the_existing_module_chain() -> None:
    registry = GovernanceRegistry.builtins()
    profile = registry.resolve_profile("architecture_governance")
    module = registry.resolve_module("architecture_conformance")
    result = compose_governance(registry, profile_identity=profile.name)

    assert profile.required_modules == (module.id,)
    assert [item.name for item in result.modules] == [
        "evidence_integrity",
        "human_approval",
        "separation_of_duties",
        "exception_management",
        "change_control",
        "architecture_conformance",
    ]
    assert {item.block for item in result.block_schemas} >= {
        "architecture",
        "architecture_evidence",
    }
    assert module.content_hash.startswith("sha256:")
    assert any("architecture radar" in item for item in module.non_goals)


def test_architecture_starter_is_deterministic_and_fails_closed_until_evidenced() -> None:
    first = profile_document("architecture_governance", "ArchitectureDemo")
    second = profile_document("architecture_governance", "ArchitectureDemo")

    assert first == second
    assert first["project"]["profile"] == "architecture_governance"
    assert first["architecture"]["schema"] == "nornyx.architecture.v1"
    assert first["architecture_evidence"] == []
    codes = _codes(first)
    assert "ARCH_EVIDENCE_MISSING" in codes
    assert "EVIDENCE_REQUIRED_MISSING" in codes
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" not in codes


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (_wrong_schema, "GOVERNANCE_BLOCK_SCHEMA_INVALID"),
        (_missing_subject_revision, "GOVERNANCE_BLOCK_SCHEMA_INVALID"),
        (_revision_mismatch, "ARCH_EVIDENCE_REVISION_MISMATCH"),
        (_missing_hash, "GOVERNANCE_BLOCK_SCHEMA_INVALID"),
        (_invalid_status, "GOVERNANCE_BLOCK_SCHEMA_INVALID"),
        (_different_check, "ARCH_EVIDENCE_CHECK_UNKNOWN"),
        (_stale_evidence, "ARCH_EVIDENCE_STALE"),
        (_future_evidence, "ARCH_EVIDENCE_GENERATED_IN_FUTURE"),
        (_missing_evidence, "ARCH_EVIDENCE_MISSING"),
        (_failed_check, "ARCH_REQUIRED_CHECK_FAILED"),
        (_passing_violations, "ARCH_EVIDENCE_STATUS_INCONSISTENT"),
        (_wrong_artifact_hash, "ARCH_EVIDENCE_ARTIFACT_HASH_MISMATCH"),
        (_wrong_tool, "ARCH_EVIDENCE_TOOL_MISMATCH"),
        (_duplicate_evidence, "ARCH_EVIDENCE_DUPLICATE_CHECK"),
        (_duplicate_component, "ARCH_DUPLICATE_ID"),
        (_unknown_layer, "ARCH_REFERENCE_UNKNOWN"),
        (_invalid_dependency_direction, "ARCH_DEPENDENCY_DIRECTION_VIOLATION"),
        (_unknown_constraint_verifier, "ARCH_REFERENCE_UNKNOWN"),
        (_unknown_exception, "ARCH_REFERENCE_UNKNOWN"),
    ],
)
def test_architecture_governance_fails_closed(
    mutation: Mutation,
    expected: str,
) -> None:
    document = _document()
    mutation(document)

    assert expected in _codes(document)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"schema": "wrong"}, "ARCH_REPORT_INVALID"),
        (
            {
                "schema": "nornyx.architecture_report.v1",
                "check_id": "dependency-boundaries",
                "tool": "dependency-cruiser",
                "tool_version": "1.0",
                "status": "pass",
                "subject_revision": "git:abc",
                "generated_at": "2026-01-01T00:00:00Z",
                "expires_at": "2027-01-01T00:00:00Z",
                "violations": [
                    {"id": "v1", "severity": "error", "message": "Violation."}
                ],
            },
            "ARCH_REPORT_STATUS_INCONSISTENT",
        ),
    ],
)
def test_architecture_importer_rejects_invalid_envelopes(
    payload: dict[str, Any],
    expected: str,
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(report, allowed_root=tmp_path)
    assert expected in {item.code for item in caught.value.diagnostics}


def test_architecture_importer_rejects_duplicate_keys_and_traversal(tmp_path: Path) -> None:
    report = tmp_path / "duplicate.json"
    report.write_text('{"schema":"first","schema":"second"}', encoding="utf-8")
    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(report, allowed_root=tmp_path)
    assert {item.code for item in caught.value.diagnostics} == {"ARCH_REPORT_INVALID"}

    outside = tmp_path.parent / "outside-architecture-report.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(outside, allowed_root=tmp_path)
    assert {item.code for item in caught.value.diagnostics} == {
        "ARCH_REPORT_PATH_OUTSIDE_ROOT"
    }


def test_architecture_importer_rejects_symlinked_root_ancestor(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real_root"
    report_root = real_root / "reports"
    report_root.mkdir(parents=True)
    report = report_root / "report.json"
    report.write_text("{}", encoding="utf-8")
    link_root = tmp_path / "link_root"
    create_symlink_or_skip(link_root, real_root, target_is_directory=True)

    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(
            link_root / "reports" / report.name,
            allowed_root=link_root / "reports",
        )
    assert {item.code for item in caught.value.diagnostics} == {
        "ARCH_REPORT_SYMLINK_REJECTED"
    }


def test_architecture_importer_rejects_resource_exhaustion(tmp_path: Path) -> None:
    report = tmp_path / "large.json"
    report.write_bytes(b" " * (4 * 1024 * 1024 + 1))

    with pytest.raises(GovernanceError) as caught:
        import_architecture_evidence(report, allowed_root=tmp_path)
    assert {item.code for item in caught.value.diagnostics} == {
        "ARCH_REPORT_LIMIT_EXCEEDED"
    }


def test_architecture_importer_contains_no_execution_or_network_surface() -> None:
    source = (ROOT / "nornyx" / "governance" / "architecture.py").read_text(
        encoding="utf-8"
    )

    assert "subprocess" not in source
    assert "os.system" not in source
    assert "Popen" not in source
    assert "requests" not in source
    assert "urllib" not in source
    assert "socket" not in source
