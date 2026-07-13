from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from nornyx.governance import GovernanceRegistry
from nornyx.governance.runtime import evaluate_document_governance


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
AS_OF = "2026-06-01T00:00:00Z"


def _document() -> dict[str, Any]:
    return yaml.safe_load(
        (EXAMPLES / "governance_foundations.nyx").read_text(encoding="utf-8")
    )


def _codes(document: dict[str, Any]) -> set[str]:
    return {
        item.code
        for item in evaluate_document_governance(
            document,
            registry=GovernanceRegistry.builtins(),
            as_of=AS_OF,
            document_root=EXAMPLES,
        )
    }


def test_aud008_empty_sod_assignment_fails_schema_and_structure() -> None:
    document = _document()
    document["separation_of_duties"]["assignments"][0]["approvers"] = []

    codes = _codes(document)
    assert "GOVERNANCE_BLOCK_SCHEMA_INVALID" in codes
    assert "SOD_APPROVER_REQUIRED" in codes


@pytest.mark.parametrize("mutation", ["expired_without_closure", "overlap"])
def test_aud013_expired_and_overlapping_exceptions_fail(mutation: str) -> None:
    document = _document()
    exception = document["exceptions"]["entries"][0]
    if mutation == "expired_without_closure":
        exception["status"] = "expired"
        exception["expires_at"] = "2026-05-15T00:00:00Z"
        exception["closure_evidence"] = []
        expected = "EXCEPTION_CLOSURE_EVIDENCE_MISSING"
    else:
        overlapping = deepcopy(exception)
        overlapping["id"] = "EXC-OVERLAP"
        document["exceptions"]["entries"].append(overlapping)
        expected = "EXCEPTION_SCOPE_OVERLAP"

    assert expected in _codes(document)
