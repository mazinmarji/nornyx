from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOSURE_REPORT = (
    ROOT
    / "docs"
    / "planning"
    / "governance-extension"
    / "21_PROGRAM_CLOSURE_REPORT.md"
)
FINAL_AUDIT = (
    ROOT
    / "docs"
    / "planning"
    / "governance-extension"
    / "22_FINAL_INDEPENDENT_AUDIT.md"
)
ROADMAP = (
    ROOT
    / "docs"
    / "planning"
    / "governance-extension"
    / "12_IMPLEMENTATION_ROADMAP.md"
)
RELEASE_CANDIDATE = (
    ROOT / "docs" / "releases" / "RELEASE_CANDIDATE_GOVERNANCE_PROGRAM.md"
)
LEDGER = (
    ROOT
    / "docs"
    / "planning"
    / "governance-extension"
    / "AUDIT_REMEDIATION_LEDGER.json"
)

ALLOWED_FINAL_STATUSES = {
    "implemented",
    "implemented_as_external_evidence_integration",
    "rejected_with_ADR",
    "superseded",
    "not_required_after_GSA",
    "future_proposal_outside_current_program",
}

REQUIRED_DISPOSITIONS = {
    "Architecture Radar": "rejected_with_ADR",
    "Supply-chain governance placement": (
        "implemented_as_external_evidence_integration"
    ),
    "Data-protection governance placement": "not_required_after_GSA",
    "Common lifecycle management module": "not_required_after_GSA",
    "Release control module": "superseded",
    "Incident-response module": "not_required_after_GSA",
    "GSA runtime schema and analyze CLI": "not_required_after_GSA",
    "Remote packs, entry-point discovery, and executable governance plugins": (
        "rejected_with_ADR"
    ),
}


def _closure_rows() -> list[list[str]]:
    lines = CLOSURE_REPORT.read_text(encoding="utf-8").splitlines()
    header_index = lines.index(
        "| Item | Original status | Final status | Implementation location | "
        "Tests | Documentation | Residual risk | Future re-entry condition |"
    )
    rows: list[list[str]] = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip().strip("`") for cell in line.strip("|").split("|")])
    return rows


def test_closure_matrix_is_complete_unique_and_unambiguous() -> None:
    rows = _closure_rows()

    assert len(rows) >= 35
    assert all(len(row) == 8 for row in rows)
    items = [row[0] for row in rows]
    assert len(items) == len(set(items))
    assert all(all(cell for cell in row) for row in rows)
    assert {row[2] for row in rows} <= ALLOWED_FINAL_STATUSES

    dispositions = {row[0]: row[2] for row in rows}
    for item, expected in REQUIRED_DISPOSITIONS.items():
        assert dispositions[item] == expected


def test_required_program_records_and_catalog_counts_exist() -> None:
    planning = ROOT / "docs" / "planning" / "governance-extension"
    for number in range(15, 23):
        assert list(planning.glob(f"{number:02d}_*.md")), number

    profiles = list((ROOT / "nornyx" / "profiles_data").glob("*.yaml"))
    modules = [path for path in profiles if path.name.startswith("module_")]
    profile_packs = [path for path in profiles if not path.name.startswith("module_")]
    assert len(modules) == 6
    assert len(profile_packs) == 12


def test_current_audit_and_candidate_preserve_external_gate_boundary() -> None:
    audit = FINAL_AUDIT.read_text(encoding="utf-8")
    roadmap = ROADMAP.read_text(encoding="utf-8")
    candidate = RELEASE_CANDIDATE.read_text(encoding="utf-8")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))

    assert "AUD-001 through AUD-022" in audit
    assert "Status: residual remediation implemented; external final-head verification required." in roadmap
    assert "3a0e840c3229dbf58959df1e3a161318bffd94ac" in audit
    assert "29373272295" in audit
    assert "not the final approved" in audit
    assert "returns exactly `GO`" in audit
    assert all(
        finding in audit
        for finding in ("AUD-011-R1", "AUD-017-R1", "AUD-021-R1", "PRMETA-001")
    )
    assert "PR state: draft" in candidate
    assert "## Prepared PR Description" in candidate
    assert candidate.count("```markdown") == 1
    prepared_body = candidate.split("```markdown", 1)[1].split("```", 1)[0]
    assert all(
        placeholder in prepared_body
        for placeholder in (
            "{{FINAL_HEAD}}",
            "{{FINAL_CI_RUN_ID}}",
            "{{FINAL_WINDOWS_RESULT}}",
            "{{FINAL_LINUX_RESULT}}",
            "{{FINAL_AUDIT_VERDICT}}",
        )
    )
    assert "81899aaac5e54781dfe9c8002f557a874854c8b8" in prepared_body
    assert "AUD-001 through AUD-022" in prepared_body
    assert "now closed on the final exact head" in prepared_body
    assert all(
        finding in prepared_body
        for finding in ("AUD-011-R1", "AUD-017-R1", "AUD-021-R1", "PRMETA-001")
    )
    assert "Candidate-aware diff" in prepared_body
    assert "Source and wheel builds: passed" in prepared_body
    assert "Twine checks: passed" in prepared_body
    assert "network_attempts=[]" in prepared_body
    assert "network_used=false" in prepared_body
    assert "five verified migrations" in prepared_body
    assert "separately\nrecorded additive architecture starter" in prepared_body
    assert "PR #30 remains draft" in prepared_body
    assert "does not\nauthorize merge" in prepared_body
    assert all(
        boundary in prepared_body
        for boundary in (
            "readiness transition",
            "auto-merge",
            "release",
            "tagging",
            "publication",
            "deployment",
        )
    )
    assert "29373272295" not in prepared_body
    assert "913 passed" not in prepared_body
    assert "958 passed" not in prepared_body
    assert ledger["audit"]["historical_exact_head_ci"]["is_final_approved_candidate"] is False
    assert ledger["audit"]["external_final_head_verification"] == {
        "resolve_candidate_from": "git_and_github",
        "hosted_ci": "required_for_resolved_exact_head",
        "independent_audit": "required_after_green_exact_head_ci",
    }
    assert [item["reopened_id"] for item in ledger["reopened_findings"]] == [
        "AUD-011-R1",
        "AUD-017-R1",
        "AUD-021-R1",
        "PRMETA-001",
    ]
    assert set(ledger["authorization"]) == {
        "approve",
        "mark_ready",
        "auto_merge",
        "merge",
        "release",
        "tag",
        "publish",
        "deploy",
    }
    assert all(value is False for value in ledger["authorization"].values())


def test_current_specs_do_not_claim_the_runtime_is_unimplemented() -> None:
    current_specs = [
        "05_PROFILE_AND_MODULE_PACK_SPEC.md",
        "11_MIGRATION_AND_COMPATIBILITY.md",
        "12_IMPLEMENTATION_ROADMAP.md",
        "15_CURRENT_IMPLEMENTATION_INVENTORY.md",
        "21_PROGRAM_CLOSURE_REPORT.md",
    ]
    forbidden = (
        "no runtime evaluator is implemented",
        "no loader, registry, composition engine",
        "profile yaml files remain outside the wheel",
    )
    for filename in current_specs:
        text = (planning := ROOT / "docs" / "planning" / "governance-extension" / filename).read_text(
            encoding="utf-8"
        ).lower()
        assert all(phrase not in text for phrase in forbidden), planning
