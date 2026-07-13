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
            test_path = reference.split("::", 1)[0]
            assert (ROOT / test_path).is_file(), reference
        assert finding["validation"]["status"] == "passed"
        assert finding["validation"]["evidence"]
        assert finding["final_status"] == "closed"

    assert payload["audit"]["status"] == "ready_for_independent_audit"
    assert all(value is False for value in payload["authorization"].values())
