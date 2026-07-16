from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = (
    ROOT
    / "docs"
    / "planning"
    / "governance-extension"
    / "AUDIT_REMEDIATION_LEDGER.json"
)


def test_every_audit_finding_has_executable_closure_evidence() -> None:
    payload = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert payload["schema"] == "nornyx.audit_remediation_ledger.v2"
    findings = payload["findings"]
    assert [item["id"] for item in findings] == [
        f"AUD-{index:03d}" for index in range(1, 23)
    ]
    for finding in findings:
        assert finding["root_cause"]
        assert finding["reproducer"]
        assert finding["affected_files"]
        assert finding["correction"]
        assert finding["implementation_reference"]
        assert finding["tests"]
        for reference in finding["tests"]:
            test_path, separator, test_name = reference.partition("::")
            resolved_test_path = ROOT / test_path
            assert resolved_test_path.is_file(), reference
            if separator:
                assert test_name in resolved_test_path.read_text(encoding="utf-8"), reference
        assert finding["validation"]["status"] == "passed"
        assert finding["validation"]["evidence"]
        expected_reopened = {
            "AUD-011": "reopened_as_AUD-011-R1",
            "AUD-017": "reopened_as_AUD-017-R1",
            "AUD-021": "reopened_as_AUD-021-R1",
        }
        assert finding["final_status"] == expected_reopened.get(finding["id"], "closed")

    reopened = payload["reopened_findings"]
    assert [item["reopened_id"] for item in reopened] == [
        "AUD-011-R1",
        "AUD-017-R1",
        "AUD-021-R1",
        "PRMETA-001",
    ]
    for finding in reopened:
        assert finding["original_finding"]["id"]
        assert finding["reopening_audit"]["candidate"] == (
            "3a0e840c3229dbf58959df1e3a161318bffd94ac"
        )
        assert finding["reopening_audit"]["verdict"] == "NO-GO"
        assert finding["reopening_audit"]["evidence"]
        assert finding["remediation"]["implementation_references"]
        assert finding["remediation"]["test_references"]
        for reference in finding["remediation"]["test_references"]:
            test_path, separator, test_name = reference.partition("::")
            resolved_test_path = ROOT / test_path
            assert resolved_test_path.is_file(), reference
            if separator:
                assert test_name in resolved_test_path.read_text(encoding="utf-8"), reference
        closure = finding["closure"]
        assert closure["code_closure"]["status"] in {"implemented", "not_applicable"}
        assert closure["hosted_ci_closure"] == {
            "status": "required_for_external_final_head",
            "candidate": None,
            "run_id": None,
        }
        assert closure["independent_audit_closure"] == {
            "status": "required_after_green_exact_head_ci",
            "verdict": None,
        }
        assert closure["human_authorization"] == {
            "status": "not_granted",
            "authorized": False,
        }
        assert finding["external_exact_head_ci_requirement"] is True

    audit = payload["audit"]
    assert audit["residual_remediation"]["status"] == (
        "implemented_pending_external_final_head_verification"
    )
    assert audit["residual_remediation"]["documentation_commit"] == {
        "kind": "containing_commit",
        "sha": None,
        "self_embedding_avoided": True,
    }
    assert set(payload["authorization"]) == {
        "approve",
        "mark_ready",
        "auto_merge",
        "merge",
        "release",
        "tag",
        "publish",
        "deploy",
    }
    assert all(value is False for value in payload["authorization"].values())
