from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from . import __version__
from .errors import Diagnostic
from .parser import load_nyx


PROFILE_NAME = "governed_package"
PROFILE_VERSION = "1.0"
GENERATOR_NAME = "nornyx-governed-package-generator"
SAFE_INSTALLATION_POLICY = {
    "installed": False,
    "executable_by_default": False,
    "requires_explicit_install": True,
}
SAFE_BOUNDARY = {
    "secrets_allowed": False,
    "production_data_allowed": False,
    "autonomous_execution_allowed": False,
    "external_writes_allowed": False,
    "deployment_allowed": False,
    "approval_required": True,
}

REQUIRED_PACKAGE_FIELDS = {
    "profile",
    "schema_version",
    "package_id",
    "name",
    "mission",
    "tasks",
    "changes",
    "evidence",
    "approval_gates",
    "risk_tier",
    "artifacts",
    "installation_policy",
    "safety_boundary",
    "provenance",
}
RISK_TIERS = {"low", "medium", "high", "critical"}
APPROVER_FIELDS = (
    "eligible_approver_roles",
    "approver_roles",
    "approvers",
    "eligible_approvers",
)
AI_TOOL_MARKERS = {"ai_tool", "ai_tools", "tool", "tools", "execution_surface"}
SECRET_RE = re.compile(
    r"(api[_-]?key|token|secret|password|credential|private[_-]?key)\s*[:=]\s*([^\s]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GovernedPackage:
    data: dict[str, Any]


class GovernedPackageValidator:
    def validate(self, package: dict[str, Any], *, base_dir: str | Path | None = None) -> list[Diagnostic]:
        return validate_governed_package(package, base_dir=base_dir)

    def verify_lock(self, package_dir: str | Path) -> list[Diagnostic]:
        return verify_package_lock(package_dir)


class GovernedPackageGenerator:
    def generate(self, source_file: str | Path, out_dir: str | Path) -> list[Path]:
        return generate_governed_package(source_file, out_dir)

    def register(
        self,
        source_dir: str | Path,
        out_dir: str | Path,
        *,
        contract: str | Path | None = None,
    ) -> list[Path]:
        return register_existing_package(source_dir, out_dir, contract=contract)

    def radar(
        self,
        source_dir: str | Path,
        out: str | Path,
        *,
        suggest_contract: bool = False,
    ) -> dict[str, Any]:
        return radar_governed_packages(source_dir, out, suggest_contract=suggest_contract)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _portable_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _id_values(items: Any) -> list[str]:
    return [
        str(item["id"])
        for item in _as_list(items)
        if isinstance(item, dict) and _non_empty_string(item.get("id"))
    ]


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _evidence_requirements(package: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = package.get("evidence")
    if isinstance(evidence, dict):
        return [item for item in _as_list(evidence.get("requirements")) if isinstance(item, dict)]
    return []


def _evidence_ids(package: dict[str, Any]) -> set[str]:
    return {str(item["id"]) for item in _evidence_requirements(package) if _non_empty_string(item.get("id"))}


def _surface_ids(package: dict[str, Any]) -> set[str]:
    surfaces = package.get("execution_surfaces", [])
    ids = {
        str(item["id"])
        for item in _as_list(surfaces)
        if isinstance(item, dict) and _non_empty_string(item.get("id"))
    }
    ids.update(
        str(item["type"])
        for item in _as_list(surfaces)
        if isinstance(item, dict) and _non_empty_string(item.get("type"))
    )
    return ids


def _flatten_approver_values(gate: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in APPROVER_FIELDS:
        raw = gate.get(field)
        if isinstance(raw, list):
            values.update(str(item) for item in raw if _non_empty_string(item))
        elif _non_empty_string(raw):
            values.add(str(raw))
    return values


def _diag(
    code: str,
    message: str,
    path: str,
    *,
    hint: str | None = None,
    level: str = "error",
) -> Diagnostic:
    return Diagnostic(level, code, message, path, hint)


def load_governed_package_source(source: str | Path) -> dict[str, Any]:
    path = Path(source)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return payload
    doc = load_nyx(path)
    package = doc.get("governed_package")
    if not isinstance(package, dict):
        raise ValueError(f"{path} does not declare a governed_package block")
    return deepcopy(package)


def validate_governed_package(
    package: dict[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(package, dict):
        return [_diag("INVALID_GOVERNED_PACKAGE", "governed_package must be a mapping", "governed_package")]

    missing = sorted(field for field in REQUIRED_PACKAGE_FIELDS if field not in package)
    for field in missing:
        diagnostics.append(
            _diag(
                f"MISSING_GOVERNED_PACKAGE_{field.upper()}",
                f"governed_package.{field} is required",
                f"governed_package.{field}",
            )
        )

    if package.get("profile") != PROFILE_NAME:
        diagnostics.append(
            _diag(
                "INVALID_GOVERNED_PACKAGE_PROFILE",
                "governed_package.profile must be 'governed_package'",
                "governed_package.profile",
            )
        )

    for field in ("schema_version", "package_id", "name", "risk_tier"):
        if field in package and not _non_empty_string(package.get(field)):
            diagnostics.append(
                _diag(
                    f"INVALID_GOVERNED_PACKAGE_{field.upper()}",
                    f"governed_package.{field} must be a non-empty string",
                    f"governed_package.{field}",
                )
            )
    if _non_empty_string(package.get("risk_tier")) and package["risk_tier"] not in RISK_TIERS:
        diagnostics.append(
            _diag(
                "INVALID_GOVERNED_PACKAGE_RISK_TIER",
                f"governed_package.risk_tier must be one of {sorted(RISK_TIERS)}",
                "governed_package.risk_tier",
            )
        )

    mission = package.get("mission")
    if not isinstance(mission, dict) or not _non_empty_string(mission.get("objective")):
        diagnostics.append(
            _diag(
                "INVALID_GOVERNED_PACKAGE_MISSION",
                "governed_package.mission must include an objective",
                "governed_package.mission.objective",
            )
        )

    for block in ("tasks", "changes", "approval_gates", "artifacts"):
        if block in package and not isinstance(package[block], list):
            diagnostics.append(
                _diag(
                    f"INVALID_GOVERNED_PACKAGE_{block.upper()}",
                    f"governed_package.{block} must be a list",
                    f"governed_package.{block}",
                )
            )

    for block in ("tasks", "changes"):
        duplicates = _duplicate_values(_id_values(package.get(block)))
        for duplicate in duplicates:
            diagnostics.append(
                _diag(
                    f"DUPLICATE_GOVERNED_PACKAGE_{block.upper()}_ID",
                    f"governed_package.{block} id {duplicate!r} is duplicated",
                    f"governed_package.{block}",
                )
            )

    requirements = _evidence_requirements(package)
    requirement_ids = _id_values(requirements)
    for index, item in enumerate(requirements):
        if not _non_empty_string(item.get("id")):
            diagnostics.append(
                _diag(
                    "MISSING_EVIDENCE_REQUIREMENT_ID",
                    "evidence requirements must declare id",
                    f"governed_package.evidence.requirements[{index}].id",
                )
            )
        if not _non_empty_string(item.get("type")):
            diagnostics.append(
                _diag(
                    "MISSING_EVIDENCE_REQUIREMENT_TYPE",
                    "evidence requirements must declare type",
                    f"governed_package.evidence.requirements[{index}].type",
                )
            )
    for duplicate in _duplicate_values(requirement_ids):
        diagnostics.append(
            _diag(
                "DUPLICATE_EVIDENCE_REQUIREMENT_ID",
                f"evidence requirement id {duplicate!r} is duplicated",
                "governed_package.evidence.requirements",
            )
        )

    evidence_ids = _evidence_ids(package)
    surface_ids = _surface_ids(package)
    for index, surface in enumerate(_as_list(package.get("execution_surfaces"))):
        if not isinstance(surface, dict):
            continue
        if surface.get("can_approve") is True:
            diagnostics.append(
                _diag(
                    "EXECUTION_SURFACE_CANNOT_APPROVE",
                    "execution surfaces are tools and cannot approve governed packages",
                    f"governed_package.execution_surfaces[{index}].can_approve",
                )
            )

    for index, gate in enumerate(_as_list(package.get("approval_gates"))):
        path = f"governed_package.approval_gates[{index}]"
        if not isinstance(gate, dict):
            diagnostics.append(_diag("INVALID_APPROVAL_GATE", "approval gate must be a mapping", path))
            continue
        required_evidence = gate.get("required_evidence")
        if not isinstance(required_evidence, list) or not required_evidence:
            diagnostics.append(
                _diag(
                    "APPROVAL_GATE_REQUIRES_EVIDENCE",
                    "approval gates must require at least one evidence item",
                    f"{path}.required_evidence",
                )
            )
        else:
            for evidence_ref in required_evidence:
                if evidence_ref not in evidence_ids:
                    diagnostics.append(
                        _diag(
                            "UNKNOWN_APPROVAL_GATE_EVIDENCE",
                            f"approval gate references unknown evidence {evidence_ref!r}",
                            f"{path}.required_evidence",
                        )
                    )
        approver_values = _flatten_approver_values(gate)
        denied_types = {
            str(item)
            for item in _as_list(gate.get("denied_approver_types"))
            if _non_empty_string(item)
        }
        invalid_markers = (approver_values & surface_ids) | (approver_values & AI_TOOL_MARKERS)
        if invalid_markers:
            diagnostics.append(
                _diag(
                    "INVALID_APPROVER_EXECUTION_SURFACE",
                    "execution surfaces and AI tools cannot be eligible approvers",
                    path,
                )
            )
        if "execution_surface" not in denied_types:
            diagnostics.append(
                _diag(
                    "APPROVAL_GATE_SHOULD_DENY_EXECUTION_SURFACE",
                    "approval gates must deny execution surfaces as approvers",
                    f"{path}.denied_approver_types",
                )
            )
        if "ai_tool" not in denied_types:
            diagnostics.append(
                _diag(
                    "APPROVAL_GATE_SHOULD_DENY_AI_TOOL",
                    "approval gates must deny AI tools as approvers",
                    f"{path}.denied_approver_types",
                )
            )

    for index, artifact in enumerate(_as_list(package.get("artifacts"))):
        path = f"governed_package.artifacts[{index}]"
        if not isinstance(artifact, dict):
            diagnostics.append(_diag("INVALID_ARTIFACT", "artifact must be a mapping", path))
            continue
        for field in ("id", "path", "type"):
            if not _non_empty_string(artifact.get(field)):
                diagnostics.append(
                    _diag(
                        f"MISSING_ARTIFACT_{field.upper()}",
                        f"artifact.{field} is required",
                        f"{path}.{field}",
                    )
                )
        if package.get("registration_mode") == "existing" and not _non_empty_string(artifact.get("sha256")):
            diagnostics.append(
                _diag(
                    "MISSING_REGISTERED_ARTIFACT_HASH",
                    "registered artifacts must include sha256",
                    f"{path}.sha256",
                )
            )

    installation = package.get("installation_policy")
    if not isinstance(installation, dict):
        diagnostics.append(
            _diag(
                "INVALID_INSTALLATION_POLICY",
                "installation_policy must be a mapping",
                "governed_package.installation_policy",
            )
        )
    else:
        for field, expected in SAFE_INSTALLATION_POLICY.items():
            if installation.get(field) is not expected:
                diagnostics.append(
                    _diag(
                        f"UNSAFE_INSTALLATION_POLICY_{field.upper()}",
                        f"installation_policy.{field} must be {expected!r}",
                        f"governed_package.installation_policy.{field}",
                    )
                )

    safety = package.get("safety_boundary")
    if not isinstance(safety, dict):
        diagnostics.append(
            _diag(
                "INVALID_SAFETY_BOUNDARY",
                "safety_boundary must be a mapping",
                "governed_package.safety_boundary",
            )
        )
    else:
        for field, expected in SAFE_BOUNDARY.items():
            if safety.get(field) is not expected:
                diagnostics.append(
                    _diag(
                        f"UNSAFE_SAFETY_BOUNDARY_{field.upper()}",
                        f"safety_boundary.{field} must be {expected!r}",
                        f"governed_package.safety_boundary.{field}",
                    )
                )

    provenance = package.get("provenance")
    if not isinstance(provenance, dict):
        diagnostics.append(
            _diag("INVALID_PROVENANCE", "provenance must be a mapping", "governed_package.provenance")
        )
    else:
        for field in ("source_sha256", "generator_version", "profile_version"):
            if not _non_empty_string(provenance.get(field)):
                diagnostics.append(
                    _diag(
                        f"MISSING_PROVENANCE_{field.upper()}",
                        f"provenance.{field} is required",
                        f"governed_package.provenance.{field}",
                    )
                )

    package_lock = package.get("package_lock")
    if isinstance(package_lock, dict) and base_dir is not None:
        lock_path = Path(base_dir) / str(package_lock.get("path", "package_lock.json"))
        if lock_path.exists():
            diagnostics.extend(verify_package_lock(lock_path.parent))

    return diagnostics


def _artifact_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".rst"}:
        return "documentation"
    if suffix in {".diff", ".patch"}:
        return "patch"
    if suffix in {".json", ".yaml", ".yml", ".toml"}:
        return "manifest"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
        return "image"
    return "file"


def _artifact_hashes(out: Path, paths: list[Path]) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(out).as_posix(), "sha256": _sha256_file(path)}
        for path in sorted(paths, key=lambda item: item.relative_to(out).as_posix())
    ]


def _provenance(source_file: Path, source_sha256: str) -> dict[str, Any]:
    return {
        "source_contract": _portable_ref(source_file),
        "source_sha256": source_sha256,
        "generator_name": GENERATOR_NAME,
        "generator_version": __version__,
        "profile_version": PROFILE_VERSION,
        "generated_at": _utc_now(),
    }


def _safe_package(package: dict[str, Any]) -> dict[str, Any]:
    safe = deepcopy(package)
    safe["profile"] = PROFILE_NAME
    safe["installation_policy"] = dict(SAFE_INSTALLATION_POLICY)
    safe["safety_boundary"] = dict(SAFE_BOUNDARY)
    return safe


def _manifest_from_source(source_file: Path) -> dict[str, Any]:
    package = load_governed_package_source(source_file)
    source_sha = _sha256_file(source_file)
    manifest = _safe_package(package)
    manifest["provenance"] = {
        **{
            key: value
            for key, value in manifest.get("provenance", {}).items()
            if key not in {"source_sha256", "generator_name", "generator_version", "generated_at"}
        },
        **_provenance(source_file, source_sha),
    }
    return manifest


def _render_agents(package: dict[str, Any]) -> str:
    lines = [
        f"# {package['name']} Actors\n\n",
        "Generated by Nornyx as an inert governed package contract.\n\n",
        "Assignments describe responsible roles. Tools and execution surfaces are not approvers.\n\n",
    ]
    for assignment in _as_list(package.get("agent_assignments")):
        if isinstance(assignment, dict):
            lines.append(f"## {assignment.get('id', 'assignment')}\n\n")
            lines.append(f"- Role: {assignment.get('role', '')}\n")
            lines.append(
                f"- Accountable actor type: {assignment.get('accountable_actor_type', '')}\n\n"
            )
    return "".join(lines)


def _render_evidence(package: dict[str, Any]) -> str:
    lines = ["# Evidence Contract\n\n", "Generated by Nornyx. This document declares required evidence only.\n\n"]
    for requirement in _evidence_requirements(package):
        lines.append(f"- `{requirement.get('id')}` ({requirement.get('type')}), required: {requirement.get('required', False)}\n")
    return "".join(lines)


def _render_approvals(package: dict[str, Any]) -> str:
    lines = ["# Approval Contract\n\n", "Generated by Nornyx. Approval gates are declarative decision points.\n\n"]
    for gate in _as_list(package.get("approval_gates")):
        if not isinstance(gate, dict):
            continue
        lines.append(f"## {gate.get('id', 'approval-gate')}\n\n")
        lines.append("Required evidence:\n")
        for item in _as_list(gate.get("required_evidence")):
            lines.append(f"- `{item}`\n")
        lines.append("\nEligible approver roles:\n")
        for item in _as_list(gate.get("eligible_approver_roles")):
            lines.append(f"- `{item}`\n")
        lines.append("\nDenied approver types:\n")
        for item in _as_list(gate.get("denied_approver_types")):
            lines.append(f"- `{item}`\n")
        lines.append("\n")
    return "".join(lines)


def _render_safety(package: dict[str, Any]) -> str:
    lines = ["# Safety Boundary\n\n", "Generated by Nornyx. The governed package is inert.\n\n"]
    lines.append("## Installation Policy\n\n")
    for key, value in package["installation_policy"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`\n")
    lines.append("\n## Safety Flags\n\n")
    for key, value in package["safety_boundary"].items():
        lines.append(f"- `{key}`: `{str(value).lower()}`\n")
    return "".join(lines)


def generate_governed_package(source_file: str | Path, out_dir: str | Path) -> list[Path]:
    source = Path(source_file)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_from_source(source)
    diagnostics = validate_governed_package(manifest)
    if any(item.level == "error" for item in diagnostics):
        messages = "; ".join(item.message for item in diagnostics)
        raise ValueError(f"governed package validation failed: {messages}")

    generated: list[Path] = []
    manifest_path = out / "package_manifest.json"
    _write_json(manifest_path, manifest)
    generated.append(manifest_path)

    renderers = {
        "AGENTS.md": _render_agents(manifest),
        "evidence_contract.md": _render_evidence(manifest),
        "approval_contract.md": _render_approvals(manifest),
        "safety_boundary.md": _render_safety(manifest),
        "provenance.json": json.dumps(manifest["provenance"], indent=2, sort_keys=True) + "\n",
    }
    for filename, content in renderers.items():
        path = out / filename
        _write_text(path, content)
        generated.append(path)

    lock = {
        "source_file": _portable_ref(source),
        "source_sha256": manifest["provenance"]["source_sha256"],
        "generator_name": GENERATOR_NAME,
        "generator_version": __version__,
        "profile": PROFILE_NAME,
        "profile_version": PROFILE_VERSION,
        "generated_at": manifest["provenance"]["generated_at"],
        "artifact_hashes": _artifact_hashes(out, generated),
        "manifest_sha256": _sha256_file(manifest_path),
    }
    lock_path = out / "package_lock.json"
    _write_json(lock_path, lock)
    generated.append(lock_path)
    return generated


def verify_package_lock(package_dir: str | Path) -> list[Diagnostic]:
    directory = Path(package_dir)
    lock_path = directory / "package_lock.json"
    diagnostics: list[Diagnostic] = []
    if not lock_path.exists():
        return [_diag("MISSING_PACKAGE_LOCK", "package_lock.json is required", lock_path.as_posix())]
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [_diag("INVALID_PACKAGE_LOCK_JSON", f"package_lock.json is invalid JSON: {exc}", lock_path.as_posix())]
    manifest_path = directory / "package_manifest.json"
    if not manifest_path.exists():
        diagnostics.append(
            _diag("MISSING_PACKAGE_MANIFEST", "package_manifest.json is required", manifest_path.as_posix())
        )
    elif lock.get("manifest_sha256") != _sha256_file(manifest_path):
        diagnostics.append(
            _diag(
                "PACKAGE_LOCK_MANIFEST_HASH_MISMATCH",
                "package_manifest.json hash does not match package_lock.json",
                manifest_path.as_posix(),
            )
        )
    for item in _as_list(lock.get("artifact_hashes")):
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        expected = item.get("sha256")
        if not _non_empty_string(rel) or not _non_empty_string(expected):
            diagnostics.append(_diag("INVALID_PACKAGE_LOCK_ENTRY", "artifact hash entries require path and sha256", "package_lock.artifact_hashes"))
            continue
        path = directory / str(rel)
        if not path.exists():
            diagnostics.append(_diag("PACKAGE_LOCK_ARTIFACT_MISSING", f"locked artifact missing: {rel}", path.as_posix()))
        elif _sha256_file(path) != expected:
            diagnostics.append(
                _diag(
                    "PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH",
                    f"artifact hash mismatch for {rel}",
                    path.as_posix(),
                )
            )
    return diagnostics


def _inventory_existing(source_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        rel = path.relative_to(source_dir).as_posix()
        artifacts.append(
            {
                "id": re.sub(r"[^A-Za-z0-9_.-]+", "-", rel).strip(".-") or "artifact",
                "path": rel,
                "type": _artifact_type(path),
                "sha256": _sha256_file(path),
            }
        )
    return artifacts


def _registration_manifest(source_dir: Path, contract: str | Path | None) -> dict[str, Any]:
    if contract:
        manifest = _manifest_from_source(Path(contract))
    else:
        folder_name = source_dir.name or "existing-package"
        manifest = {
            "profile": PROFILE_NAME,
            "schema_version": PROFILE_VERSION,
            "package_id": f"registered-{folder_name}",
            "name": f"Registered {folder_name}",
            "mission": {
                "id": "mission-register-existing",
                "objective": "Describe and hash-lock an existing artifact set.",
            },
            "tasks": [],
            "changes": [],
            "evidence": {"requirements": []},
            "approval_gates": [],
            "risk_tier": "low",
            "artifacts": [],
            "installation_policy": dict(SAFE_INSTALLATION_POLICY),
            "safety_boundary": dict(SAFE_BOUNDARY),
            "provenance": {
                "source_contract": _portable_ref(source_dir),
                "source_path": _portable_ref(source_dir),
                "source_sha256": _sha256_bytes(_portable_ref(source_dir).encode("utf-8")),
                "generator_name": GENERATOR_NAME,
                "generator_version": __version__,
                "profile_version": PROFILE_VERSION,
                "generated_at": _utc_now(),
            },
        }
    manifest = _safe_package(manifest)
    manifest["registration_mode"] = "existing"
    manifest["source_path"] = _portable_ref(source_dir)
    manifest["artifacts"] = _inventory_existing(source_dir)
    manifest["artifact_hashes"] = [
        {"path": item["path"], "sha256": item["sha256"]} for item in manifest["artifacts"]
    ]
    manifest["provenance"] = {
        **manifest.get("provenance", {}),
        "generator_name": GENERATOR_NAME,
        "generator_version": __version__,
        "profile_version": PROFILE_VERSION,
        "generated_at": _utc_now(),
    }
    return manifest


def register_existing_package(
    source_dir: str | Path,
    out_dir: str | Path,
    *,
    contract: str | Path | None = None,
) -> list[Path]:
    source = Path(source_dir)
    if not source.is_dir():
        raise ValueError(f"existing package source is not a directory: {source}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = _registration_manifest(source, contract)
    diagnostics = validate_governed_package(manifest)
    if any(item.level == "error" for item in diagnostics):
        messages = "; ".join(item.message for item in diagnostics)
        raise ValueError(f"registered package validation failed: {messages}")

    written: list[Path] = []
    manifest_path = out / "package_manifest.json"
    provenance_path = out / "provenance.json"
    _write_json(manifest_path, manifest)
    _write_json(provenance_path, manifest["provenance"])
    written.extend([manifest_path, provenance_path])

    report = {
        "status": "registered",
        "profile": PROFILE_NAME,
        "registration_mode": "existing",
        "source_path": _portable_ref(source),
        "artifact_count": len(manifest["artifacts"]),
        "artifacts": manifest["artifacts"],
        "safety_boundary": manifest["safety_boundary"],
        "installation_policy": manifest["installation_policy"],
        "provenance": manifest["provenance"],
    }
    report_path = out / "registration_report.json"
    _write_json(report_path, report)
    written.append(report_path)

    lock = {
        "source_file": _portable_ref(source),
        "source_sha256": manifest["provenance"]["source_sha256"],
        "generator_name": GENERATOR_NAME,
        "generator_version": __version__,
        "profile": PROFILE_NAME,
        "profile_version": PROFILE_VERSION,
        "generated_at": manifest["provenance"]["generated_at"],
        "artifact_hashes": _artifact_hashes(out, written),
        "registered_artifact_hashes": manifest["artifact_hashes"],
        "manifest_sha256": _sha256_file(manifest_path),
    }
    lock_path = out / "package_lock.json"
    _write_json(lock_path, lock)
    written.append(lock_path)
    return written


def _is_secret_like(path: Path, text: str) -> bool:
    if path.name.lower() in {".env", ".env.local"}:
        return True
    return bool(SECRET_RE.search(text))


def _read_small_text(path: Path) -> str:
    try:
        if path.stat().st_size > 64_000:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _radar_contract(report: dict[str, Any]) -> dict[str, Any]:
    candidate = report["candidate_packages"][0]
    return {
        "nornyx": "0.1",
        "project": {"name": candidate["name"].replace(" ", "")},
        "governed_package": {
            "profile": PROFILE_NAME,
            "schema_version": PROFILE_VERSION,
            "package_id": candidate["candidate_id"],
            "name": candidate["name"],
            "risk_tier": candidate["suggested_risk_tier"],
            "mission": {
                "id": "mission-radar-suggested",
                "objective": candidate["mission_hint"],
            },
            "tasks": candidate["tasks_hint"],
            "changes": candidate["changes_hint"],
            "evidence": {"requirements": candidate["suggested_evidence"]},
            "approval_gates": candidate["suggested_approval_gates"],
            "agent_assignments": [],
            "execution_surfaces": [
                {
                    "id": "local-review-tooling",
                    "type": "tool",
                    "can_approve": False,
                    "produces_evidence": ["inventory_report"],
                }
            ],
            "artifacts": candidate["artifacts"],
            "installation_policy": dict(SAFE_INSTALLATION_POLICY),
            "safety_boundary": dict(SAFE_BOUNDARY),
            "provenance": {
                "source_contract": "radar-proposal",
                "source_sha256": report["source_sha256"],
                "generator_name": GENERATOR_NAME,
                "generator_version": __version__,
                "profile_version": PROFILE_VERSION,
                "generated_at": report["generated_at"],
            },
        },
    }


def radar_governed_packages(
    source_dir: str | Path,
    out: str | Path,
    *,
    suggest_contract: bool = False,
) -> dict[str, Any]:
    source = Path(source_dir)
    if not source.is_dir():
        raise ValueError(f"radar source is not a directory: {source}")

    detected: list[dict[str, Any]] = []
    safety_findings: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        rel = path.relative_to(source).as_posix()
        text = _read_small_text(path)
        secret_like = _is_secret_like(path, text)
        if secret_like:
            safety_findings.append(
                {
                    "path": rel,
                    "finding": "possible_secret",
                    "detail": "Secret-like material was detected and not copied into output.",
                }
            )
        detected.append(
            {
                "path": rel,
                "type": _artifact_type(path),
                "sha256": _sha256_file(path),
                "secret_like": secret_like,
            }
        )

    safe_artifacts = [
        {"id": item["path"].replace("/", "-"), "path": item["path"], "type": item["type"]}
        for item in detected
        if not item["secret_like"]
    ]
    inferred_risk = "medium" if safety_findings else "low"
    evidence = [
        {"id": "inventory_report", "type": "inventory", "required": True},
        {"id": "review_record", "type": "review", "required": True},
    ]
    gates = [
        {
            "id": "gate-review",
            "required_evidence": ["inventory_report", "review_record"],
            "eligible_approver_roles": ["reviewer"],
            "denied_approver_types": ["execution_surface", "ai_tool"],
        }
    ]
    source_sha = _sha256_bytes(
        json.dumps(
            [{"path": item["path"], "sha256": item["sha256"]} for item in detected],
            sort_keys=True,
        ).encode("utf-8")
    )
    report: dict[str, Any] = {
        "profile": PROFILE_NAME,
        "mode": "radar",
        "proposal_only": True,
        "source_path": _portable_ref(source),
        "source_sha256": source_sha,
        "generated_at": _utc_now(),
        "installed": False,
        "executable_by_default": False,
        "candidate_packages": [
            {
                "candidate_id": f"radar-{source.name or 'source'}",
                "name": f"{source.name or 'Source'} governed package candidate",
                "reason_detected": "Folder contains files that can be described as governed artifacts.",
                "mission_hint": "Review and govern the detected artifact set.",
                "tasks_hint": [
                    {
                        "id": "task-inventory",
                        "title": "Review detected artifact inventory",
                        "assigned_to": "reviewer",
                        "required_evidence": ["inventory_report"],
                    }
                ],
                "changes_hint": [
                    {
                        "id": "change-adopt-artifacts",
                        "type": "artifact_registration",
                        "expected_artifacts": [item["id"] for item in safe_artifacts],
                    }
                ],
                "artifacts": safe_artifacts,
                "suggested_risk_tier": inferred_risk,
                "suggested_evidence": evidence,
                "suggested_approval_gates": gates,
                "confidence": 0.74 if detected else 0.2,
                "limitations": [
                    "Radar output is advisory and does not approve, install, execute, or deploy.",
                    "Secret-like files are flagged by path only.",
                ],
            }
        ],
        "detected_artifacts": detected,
        "inferred_risk_tier": inferred_risk,
        "missing_evidence": ["review_record"],
        "suggested_evidence_requirements": evidence,
        "suggested_approval_gates": gates,
        "safety_findings": safety_findings,
        "confidence_score": 0.74 if detected else 0.2,
        "installation_policy": dict(SAFE_INSTALLATION_POLICY),
        "safety_boundary": dict(SAFE_BOUNDARY),
        "provenance": {
            "source_contract": _portable_ref(source),
            "source_sha256": source_sha,
            "generator_name": GENERATOR_NAME,
            "generator_version": __version__,
            "profile_version": PROFILE_VERSION,
            "generated_at": _utc_now(),
        },
    }

    out_path = Path(out)
    if suggest_contract:
        contract_path = out_path
        report_path = contract_path.parent / "radar_report.json"
        contract = _radar_contract(report)
        _write_text(contract_path, yaml.safe_dump(contract, sort_keys=False, width=100))
        report["suggested_contract_ref"] = contract_path.as_posix()
        _write_json(report_path, report)
    else:
        report_path = out_path
        if report_path.suffix.lower() != ".json":
            report_path = report_path / "radar_report.json"
        _write_json(report_path, report)
    report["report_path"] = report_path.as_posix()
    return report


def validate_governed_package_source(path: str | Path) -> list[Diagnostic]:
    source = Path(path)
    if source.is_dir():
        manifest = source / "package_manifest.json"
        if not manifest.exists():
            return [_diag("MISSING_PACKAGE_MANIFEST", "package_manifest.json is required", manifest.as_posix())]
        package = load_governed_package_source(manifest)
        diagnostics = validate_governed_package(package, base_dir=source)
        diagnostics.extend(verify_package_lock(source))
        return diagnostics
    package = load_governed_package_source(source)
    base_dir = source.parent if source.suffix.lower() == ".json" else None
    diagnostics = validate_governed_package(package, base_dir=base_dir)
    if source.name == "package_manifest.json" and (source.parent / "package_lock.json").exists():
        diagnostics.extend(verify_package_lock(source.parent))
    return diagnostics
