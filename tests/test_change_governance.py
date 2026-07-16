from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from nornyx.governance import GovernanceRegistry, change_scope_hash
from nornyx.governance.runtime import evaluate_document_governance
from nornyx.governed_package import validate_governed_package
from nornyx.parser import load_nyx


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
GOVERNED_PACKAGE_EXAMPLES = EXAMPLES / "governed_package"
AS_OF = "2026-06-01T00:00:00Z"


def _document() -> dict[str, Any]:
    return yaml.safe_load(
        (EXAMPLES / "governance_foundations.nyx").read_text(encoding="utf-8")
    )


def _codes(document: dict[str, Any]) -> set[str]:
    return {
        diagnostic.code
        for diagnostic in evaluate_document_governance(
            document,
            registry=GovernanceRegistry.builtins(),
            as_of=AS_OF,
            document_root=EXAMPLES,
        )
    }


def _change(document: dict[str, Any]) -> dict[str, Any]:
    return document["changes"][0]


def _duplicate_change(document: dict[str, Any]) -> None:
    document["changes"].append(deepcopy(_change(document)))


def _invalid_transition(document: dict[str, Any]) -> None:
    _change(document)["transition"]["to"] = "approved"


def _missing_transition_evidence(document: dict[str, Any]) -> None:
    _change(document)["transition"]["evidence"] = []


def _missing_high_risk_gates(document: dict[str, Any]) -> None:
    _change(document)["approver_roles"] = []
    _change(document)["required_evidence"] = []


def _missing_evidence(document: dict[str, Any]) -> None:
    _change(document)["required_evidence"] = ["missing-record"]


def _unknown_exception(document: dict[str, Any]) -> None:
    _change(document)["exceptions"] = ["EXC-MISSING"]


def _missing_sod_assignment(document: dict[str, Any]) -> None:
    document["separation_of_duties"]["assignments"] = []


def _changed_scope(document: dict[str, Any]) -> None:
    _change(document)["scope"].append("src/other.py")


def _stale_revision(document: dict[str, Any]) -> None:
    document["approvals"][0]["revision_binding"]["revision"] = "git:other"


def _missing_invalidation(document: dict[str, Any]) -> None:
    _change(document)["approval_invalidated_on"] = ["revision_change"]


def _missing_irreversible_authority(document: dict[str, Any]) -> None:
    change = _change(document)
    change["reversibility"] = "irreversible"
    change["rollback_required"] = True
    change["rollback_plan_artifact"] = "artifact:rollback-plan"


def _missing_irreversible_rollback(document: dict[str, Any]) -> None:
    change = _change(document)
    change["reversibility"] = "irreversible"
    change["irreversible_authority"] = "reviewer"


def _missing_rollback_artifact(document: dict[str, Any]) -> None:
    _change(document)["rollback_required"] = True


def _missing_architecture_evidence(document: dict[str, Any]) -> None:
    _change(document)["impacts"]["architecture"] = "major"


def _missing_closure_evidence(document: dict[str, Any]) -> None:
    _change(document)["status"] = "closed"
    _change(document)["closure_evidence"] = []


def _missing_matching_approval(document: dict[str, Any]) -> None:
    _change(document)["approval_ids"] = ["MissingGate"]
    document["approvals"][0]["required_for"] = ["merge"]


Mutation = Callable[[dict[str, Any]], None]


def test_change_control_example_is_valid_and_scope_hash_is_deterministic() -> None:
    document = _document()
    change = _change(document)

    assert _codes(document) == set()
    assert change_scope_hash(change) == change["revision_binding"]["scope_hash"]
    assert change_scope_hash(change) == change_scope_hash(deepcopy(change))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (_duplicate_change, "CHANGE_DUPLICATE_ID"),
        (_invalid_transition, "CHANGE_LIFECYCLE_TRANSITION_INVALID"),
        (_missing_transition_evidence, "CHANGE_TRANSITION_EVIDENCE_MISSING"),
        (_missing_high_risk_gates, "CHANGE_HIGH_RISK_GATES_MISSING"),
        (_missing_evidence, "CHANGE_EVIDENCE_MISSING"),
        (_unknown_exception, "CHANGE_EXCEPTION_UNKNOWN"),
        (_missing_sod_assignment, "CHANGE_SOD_ASSIGNMENT_MISSING"),
        (_changed_scope, "APPROVAL_STALE_FOR_SCOPE"),
        (_stale_revision, "APPROVAL_STALE_FOR_REVISION"),
        (_missing_invalidation, "CHANGE_APPROVAL_INVALIDATION_MISSING"),
        (_missing_irreversible_authority, "CHANGE_IRREVERSIBLE_AUTHORITY_MISSING"),
        (_missing_irreversible_rollback, "CHANGE_ROLLBACK_REQUIRED"),
        (_missing_rollback_artifact, "CHANGE_ROLLBACK_ARTIFACT_MISSING"),
        (_missing_architecture_evidence, "CHANGE_ARCHITECTURE_EVIDENCE_MISSING"),
        (_missing_closure_evidence, "CHANGE_CLOSURE_EVIDENCE_MISSING"),
        (_missing_matching_approval, "CHANGE_APPROVAL_MISSING"),
    ],
)
def test_change_control_fails_closed(mutation: Mutation, expected: str) -> None:
    document = _document()
    mutation(document)

    assert expected in _codes(document)


@pytest.mark.parametrize(
    "name",
    [
        "basic.nyx",
        "external_evidence_adapters.nyx",
        "register_existing.nyx",
        "software_change.nyx",
    ],
)
def test_valid_governed_package_examples_keep_the_shared_change_minimum(
    name: str,
) -> None:
    package = load_nyx(GOVERNED_PACKAGE_EXAMPLES / name)["governed_package"]

    assert not {
        diagnostic.code
        for diagnostic in validate_governed_package(package)
        if diagnostic.level == "error"
    }


def test_governed_package_rejects_malformed_shared_change() -> None:
    package = load_nyx(GOVERNED_PACKAGE_EXAMPLES / "basic.nyx")["governed_package"]
    package["changes"][0].pop("type")

    assert "INVALID_GOVERNED_PACKAGE_CHANGE" in {
        diagnostic.code for diagnostic in validate_governed_package(package)
    }
