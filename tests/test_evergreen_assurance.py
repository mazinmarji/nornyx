from __future__ import annotations

from nornyx.evergreen import (
    STABLE_KERNEL_BLOCKS,
    evergreen_summary,
    is_enterprise_ready,
    validate_evergreen_assurance,
)


def valid_assurance() -> dict:
    return {
        "nornyx_version": "0.1",
        "kernel": {"stable_blocks": sorted(STABLE_KERNEL_BLOCKS)},
        "extensions": [
            {
                "name": "mcp",
                "status": "candidate",
                "provides": ["connector_manifest"],
                "conformance": ["schemas/connector_manifest.schema.json"],
                "security": {"requires_approval": True, "default_mode": "read_only"},
            }
        ],
        "compatibility": {"profiles": ["minimal", "standard", "ai_coding"]},
        "maturity": {"level": 2, "name": "checked_contracts"},
    }


def test_valid_evergreen_assurance_has_no_errors() -> None:
    issues = validate_evergreen_assurance(valid_assurance())
    assert not any(issue.severity == "error" for issue in issues)


def test_candidate_extension_requires_conformance() -> None:
    data = valid_assurance()
    data["extensions"][0]["conformance"] = []
    issues = validate_evergreen_assurance(data)
    assert any("requires conformance" in issue.message for issue in issues)


def test_duplicate_extensions_are_rejected() -> None:
    data = valid_assurance()
    data["extensions"].append(dict(data["extensions"][0]))
    issues = validate_evergreen_assurance(data)
    assert any("duplicate extension" in issue.message for issue in issues)


def test_enterprise_ready_requires_no_errors_and_level_2() -> None:
    assert is_enterprise_ready(valid_assurance()) is True
    data = valid_assurance()
    data["maturity"]["level"] = 1
    assert is_enterprise_ready(data) is False


def test_evergreen_summary() -> None:
    summary = evergreen_summary(valid_assurance())
    assert "extensions=1" in summary
    assert "maturity=L2:checked_contracts" in summary
