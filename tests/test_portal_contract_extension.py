from __future__ import annotations

from nornyx.portal_contract import normalize_portal_contract, validate_portal_contract


def valid_contract() -> dict:
    return {
        "name": "NornyxPortal",
        "source": "delivery_state",
        "role_views": [
            {"name": "Developer", "sees": ["assigned_goals", "validation_commands"]},
            {"name": "PMO", "sees": ["roadmap", "risks", "evidence"]},
        ],
        "render_targets": ["shell", "markdown", "json", "developer_pmo_portal"],
        "safety": {
            "read_only": True,
            "no_shell_execution": True,
            "no_external_calls": True,
            "no_secret_exposure": True,
        },
    }


def test_valid_portal_contract_has_no_errors() -> None:
    assert validate_portal_contract(valid_contract()) == []


def test_normalize_portal_contract() -> None:
    contract = normalize_portal_contract(valid_contract())
    assert contract.name == "NornyxPortal"
    assert contract.source == "delivery_state"
    assert contract.read_only is True
    assert contract.role_views[0].name == "Developer"


def test_rejects_write_or_shell_contracts() -> None:
    data = valid_contract()
    data["safety"]["read_only"] = False
    data["safety"]["no_shell_execution"] = False
    errors = validate_portal_contract(data)
    assert any("read-only" in err for err in errors)
    assert any("shell execution" in err for err in errors)


def test_rejects_invalid_render_target() -> None:
    data = valid_contract()
    data["render_targets"] = ["production_control_panel"]
    errors = validate_portal_contract(data)
    assert any("invalid render_targets" in err for err in errors)
