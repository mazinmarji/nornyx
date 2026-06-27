"""Optional Portal Contract helpers.

This module is intentionally small and read-only. It validates and normalizes
portal contract dictionaries. It does not render a full portal or execute work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ALLOWED_SOURCES = {"delivery_state", "goal_state", "pmo_status"}
ALLOWED_RENDER_TARGETS = {
    "shell",
    "markdown",
    "json",
    "developer_pmo_portal",
    "ide_panel",
    "html_static",
    "ci_summary",
}


@dataclass(frozen=True)
class RoleView:
    name: str
    sees: tuple[str, ...]


@dataclass(frozen=True)
class PortalContract:
    name: str
    source: str
    role_views: tuple[RoleView, ...]
    render_targets: tuple[str, ...]
    read_only: bool = True


def validate_portal_contract(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required")

    source = data.get("source")
    if source not in ALLOWED_SOURCES:
        errors.append(f"source must be one of {sorted(ALLOWED_SOURCES)}")

    role_views = data.get("role_views")
    if not isinstance(role_views, list) or not role_views:
        errors.append("role_views must be a non-empty list")
    else:
        for index, view in enumerate(role_views):
            if not isinstance(view, dict):
                errors.append(f"role_views[{index}] must be an object")
                continue
            if not isinstance(view.get("name"), str) or not view.get("name", "").strip():
                errors.append(f"role_views[{index}].name is required")
            sees = view.get("sees")
            if not isinstance(sees, list) or not all(isinstance(item, str) and item for item in sees):
                errors.append(f"role_views[{index}].sees must be a non-empty string list")

    render_targets = data.get("render_targets")
    if not isinstance(render_targets, list) or not render_targets:
        errors.append("render_targets must be a non-empty list")
    else:
        invalid = [target for target in render_targets if target not in ALLOWED_RENDER_TARGETS]
        if invalid:
            errors.append(f"invalid render_targets: {invalid}")

    safety = data.get("safety", {})
    if isinstance(safety, dict):
        if safety.get("read_only") is False:
            errors.append("portal contracts must be read-only by default")
        if safety.get("no_shell_execution") is False:
            errors.append("portal contracts must not enable shell execution")
        if safety.get("no_secret_exposure") is False:
            errors.append("portal contracts must not expose secrets")
    elif safety is not None:
        errors.append("safety must be an object")

    return errors


def normalize_portal_contract(data: dict[str, Any]) -> PortalContract:
    errors = validate_portal_contract(data)
    if errors:
        raise ValueError("; ".join(errors))

    safety = data.get("safety", {}) if isinstance(data.get("safety", {}), dict) else {}
    return PortalContract(
        name=str(data["name"]),
        source=str(data["source"]),
        role_views=tuple(
            RoleView(name=str(view["name"]), sees=tuple(str(item) for item in view["sees"]))
            for view in data["role_views"]
        ),
        render_targets=tuple(str(target) for target in data["render_targets"]),
        read_only=bool(safety.get("read_only", True)),
    )
