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
from .governance.errors import GovernanceError
from .governance.loader import (
    inspect_local_directory,
    read_local_file_bytes,
    reject_remote_or_device_path,
)
from .governance.schemas import validate_governance_block
from .package_scanner import SCANNER_NAME, SCANNER_VERSION, scan_package, write_scan_reports
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
SCAN_REPORT_FILES = [
    "package_analysis.json",
    "package_analysis.md",
    "risk_surface_report.json",
    "risk_surface_report.md",
    "source_inventory.md",
    "hook_risk_review.md",
    "hook_risk_report.json",
    "mcp_risk_review.md",
    "mcp_risk_report.json",
    "secret_scan_report.json",
    "secret_scan_report.md",
    "endpoint_scan_report.json",
    "endpoint_scan_report.md",
    "command_risk_report.json",
    "command_risk_report.md",
    "claim_vs_evidence_report.json",
    "claim_vs_evidence_report.md",
    "external_evidence_summary.json",
    "external_evidence_summary.md",
    "adapter_execution_report.json",
]
RISK_EVIDENCE_REQUIREMENTS = [
    ("inventory_report", "inventory", "source_inventory.md"),
    ("package_analysis", "package_analysis", "package_analysis.json"),
    ("risk_surface_report", "risk_surface", "risk_surface_report.json"),
    ("claim_vs_evidence_report", "claim_vs_evidence", "claim_vs_evidence_report.json"),
    ("review_record", "human_review", ""),
]


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


def _risk_rank(tier: str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(tier, 0)


def _max_risk_tier(*tiers: str) -> str:
    return max((tier for tier in tiers if tier in RISK_TIERS), key=_risk_rank, default="low")


def _requirement_types(package: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for item in _evidence_requirements(package):
        for field in ("id", "type"):
            if _non_empty_string(item.get(field)):
                values.add(str(item[field]))
    return values


def _gate_roles(package: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    for gate in _as_list(package.get("approval_gates")):
        if isinstance(gate, dict):
            roles.update(_flatten_approver_values(gate))
    return roles


def _scan_meta(package: dict[str, Any]) -> dict[str, Any]:
    scan = package.get("scan_metadata")
    return scan if isinstance(scan, dict) else {}


def _scan_count(package: dict[str, Any], key: str) -> int:
    meta = _scan_meta(package)
    counts = meta.get("risk_surface_counts")
    if isinstance(counts, dict):
        try:
            return int(counts.get(key, 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _scanner_claim_mismatch_count(package: dict[str, Any]) -> int:
    meta = _scan_meta(package)
    try:
        return int(meta.get("claim_mismatch_count", 0))
    except (TypeError, ValueError):
        return 0


def _adapter_status(package: dict[str, Any], name: str) -> str | None:
    meta = _scan_meta(package)
    statuses = meta.get("adapter_status")
    if isinstance(statuses, dict):
        value = statuses.get(name)
        if _non_empty_string(value):
            return str(value)
    return None


def _external_critical_count(package: dict[str, Any]) -> int:
    meta = _scan_meta(package)
    try:
        return int(meta.get("external_critical_findings", 0))
    except (TypeError, ValueError):
        return 0


def _has_scan_evidence(package: dict[str, Any], *needles: str) -> bool:
    available = _requirement_types(package)
    return any(needle in available for needle in needles)


def _scan_manifest_fields(
    manifest: dict[str, Any],
    scan: dict[str, Any],
    *,
    source: Path,
    acquisition_mode: str,
    copied_payload: bool = False,
) -> None:
    risk_surface = scan["risk_surface"]
    summary = scan["summary"]
    findings = scan["findings"]
    adapter_summary = scan["external_evidence_summary"]
    manifest["source_path"] = _portable_ref(source)
    manifest["acquisition_mode"] = acquisition_mode
    manifest["copied_payload"] = copied_payload
    manifest["scanner"] = {
        "name": SCANNER_NAME,
        "version": SCANNER_VERSION,
        "scan_timestamp": manifest.get("provenance", {}).get("generated_at") or _utc_now(),
        "deterministic": True,
        "network_used": False,
        "package_payload_executed": False,
    }
    manifest["file_count"] = summary["total_files_scanned"]
    manifest["total_byte_count"] = summary["total_bytes_scanned"]
    manifest["hash_summary"] = {
        "source_inventory_hash": scan["source_hash"],
        "hash_algorithm": "sha256",
    }
    manifest["risk_tier"] = _max_risk_tier(str(manifest.get("risk_tier", "low")), risk_surface["risk_tier"])
    manifest["risk_findings_count_by_severity"] = risk_surface["finding_count_by_severity"]
    manifest["adapter_evidence_count_by_source"] = adapter_summary.get("evidence_count_by_source", {})
    manifest["blocked_by_default"] = True
    manifest["approval_required"] = True
    manifest["scan_metadata"] = {
        "scanner_version": SCANNER_VERSION,
        "source_hash": scan["source_hash"],
        "risk_tier": risk_surface["risk_tier"],
        "risk_score": risk_surface["risk_score"],
        "risk_surface_counts": {
            "hooks": len(findings["hooks"]),
            "mcp": len(findings["mcp"]),
            "secrets": len(findings["secrets"]),
            "endpoints": len(findings["endpoints"]),
            "commands": len(findings["commands"]),
            "scripts": len(findings["scripts"]),
            "binary_files": summary["binary_like_files"],
            "minified_files": summary["suspicious_long_line_or_minified_files"],
        },
        "claim_mismatch_count": len(scan["claim_vs_evidence"]["mismatches"]),
        "claim_mismatch_max_severity": _max_risk_tier(
            *(str(item.get("severity", "low")) for item in scan["claim_vs_evidence"]["mismatches"])
        ),
        "adapter_status": {
            item.get("name", ""): item.get("status", "")
            for item in scan["adapter_execution_report"].get("executions", [])
            if isinstance(item, dict)
        },
        "adapter_diagnostics": adapter_summary.get("diagnostics", []),
        "external_critical_findings": sum(
            1
            for item in scan.get("evidence_records", [])
            if item.get("source") == "external_adapter" and item.get("severity") == "critical"
        ),
        "has_readme": any(Path(item["path"]).name.lower().startswith("readme") for item in scan["files"]),
        "has_license": any(Path(item["path"]).name.lower().startswith("license") for item in scan["files"]),
        "remote_endpoints_unclear": any(
            item.get("endpoint_classification") == "unknown" for item in findings["endpoints"]
        ),
        "required_report_files": list(SCAN_REPORT_FILES),
    }


def _ensure_requirement(package: dict[str, Any], requirement: dict[str, Any]) -> None:
    package.setdefault("evidence", {})
    evidence = package["evidence"]
    if not isinstance(evidence, dict):
        package["evidence"] = {"requirements": []}
        evidence = package["evidence"]
    requirements = evidence.setdefault("requirements", [])
    if not isinstance(requirements, list):
        evidence["requirements"] = []
        requirements = evidence["requirements"]
    existing = {item.get("id") for item in requirements if isinstance(item, dict)}
    if requirement["id"] not in existing:
        requirements.append(requirement)


def _ensure_gate(package: dict[str, Any], evidence_ids: list[str]) -> None:
    gates = package.setdefault("approval_gates", [])
    if not isinstance(gates, list):
        package["approval_gates"] = []
        gates = package["approval_gates"]
    if gates:
        gate = next((item for item in gates if isinstance(item, dict)), None)
        if gate is not None:
            refs = gate.setdefault("required_evidence", [])
            if isinstance(refs, list):
                for evidence_id in evidence_ids:
                    if evidence_id not in refs:
                        refs.append(evidence_id)
            denied = gate.setdefault("denied_approver_types", [])
            if isinstance(denied, list):
                for denied_type in ["execution_surface", "ai_tool"]:
                    if denied_type not in denied:
                        denied.append(denied_type)
            return
    gates.append(
        {
            "id": "gate-package-review",
            "required_evidence": evidence_ids,
            "eligible_approver_roles": ["reviewer", "security"],
            "denied_approver_types": ["execution_surface", "ai_tool"],
        }
    )


def _apply_scan_contract_requirements(manifest: dict[str, Any], scan: dict[str, Any]) -> None:
    required = list(RISK_EVIDENCE_REQUIREMENTS)
    findings = scan["findings"]
    if findings["hooks"]:
        required.append(("hook_risk_review", "hook_risk_review", "hook_risk_review.md"))
    if findings["mcp"]:
        required.append(("mcp_risk_review", "mcp_risk_review", "mcp_risk_review.md"))
    if findings["secrets"]:
        required.append(("secret_scan_report", "secret_scan", "secret_scan_report.json"))
    if findings["endpoints"]:
        required.append(("endpoint_scan_report", "endpoint_scan", "endpoint_scan_report.json"))
    if findings["commands"]:
        required.append(("command_risk_report", "command_risk", "command_risk_report.json"))
    for req_id, req_type, artifact in required:
        requirement = {"id": req_id, "type": req_type, "required": True}
        if artifact:
            requirement["artifact"] = artifact
        _ensure_requirement(manifest, requirement)
    _ensure_gate(manifest, [item[0] for item in required if item[0] in _evidence_ids(manifest)])


def _scan_report_hashes(out: Path) -> list[dict[str, str]]:
    return [
        {"path": name, "sha256": _sha256_file(out / name)}
        for name in SCAN_REPORT_FILES
        if (out / name).exists()
    ]


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

    for item in validate_governance_block(
        "changes",
        package.get("changes"),
        "https://nornyx.dev/schemas/change_v1.schema.json",
        source_id="nornyx.governed_package",
    ):
        suffix = item.path.removeprefix("changes") if item.path else ""
        diagnostics.append(
            _diag(
                "INVALID_GOVERNED_PACKAGE_CHANGE",
                item.message,
                f"governed_package.changes{suffix}",
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
        if safety.get("external_writes_allowed") is True and not package.get("approval_gates"):
            diagnostics.append(
                _diag(
                    "EXTERNAL_WRITES_REQUIRE_APPROVAL_GATE",
                    "external writes require an explicit approval gate",
                    "governed_package.safety_boundary.external_writes_allowed",
                )
            )

    if _scan_meta(package):
        if _scan_count(package, "hooks") and not _has_scan_evidence(package, "hook_risk_review"):
            diagnostics.append(
                _diag(
                    "HOOKS_REQUIRE_HOOK_RISK_REVIEW",
                    "detected hooks require hook risk review evidence",
                    "governed_package.evidence.requirements",
                )
            )
        if _scan_count(package, "mcp") and not _has_scan_evidence(package, "mcp_risk_review"):
            diagnostics.append(
                _diag(
                    "MCP_REQUIRES_MCP_RISK_REVIEW",
                    "detected MCP configs require MCP risk review evidence",
                    "governed_package.evidence.requirements",
                )
            )
        if _scan_count(package, "secrets") and not _has_scan_evidence(package, "secret_scan"):
            diagnostics.append(
                _diag(
                    "SECRETS_REQUIRE_SECRET_SCAN_EVIDENCE",
                    "secret-like content requires secret scan evidence",
                    "governed_package.evidence.requirements",
                )
            )
        if (
            _scanner_claim_mismatch_count(package)
            and _scan_meta(package).get("claim_mismatch_max_severity") in {"high", "critical"}
            and not _has_scan_evidence(package, "claim_vs_evidence")
        ):
            diagnostics.append(
                _diag(
                    "CLAIM_MISMATCH_REQUIRES_EVIDENCE",
                    "critical claim-vs-evidence mismatches require claim review evidence",
                    "governed_package.evidence.requirements",
                )
            )
        for adapter in _as_list(package.get("evidence_adapters")):
            if not isinstance(adapter, dict):
                continue
            name = str(adapter.get("name", "")).strip()
            required = bool(adapter.get("required", False))
            # A required adapter fails by default; opt out explicitly with failure_policy: warn.
            failure_policy = str(adapter.get("failure_policy", "fail" if required else "warn"))
            status = _adapter_status(package, name)
            if required and failure_policy != "warn" and status in {None, "unavailable", "failed"}:
                diagnostics.append(
                    _diag(
                        "REQUIRED_ADAPTER_UNAVAILABLE",
                        f"required external adapter {name!r} is unavailable",
                        "governed_package.evidence_adapters",
                    )
                )
            elif not required and status in {"unavailable", "failed"}:
                diagnostics.append(
                    _diag(
                        "OPTIONAL_ADAPTER_UNAVAILABLE",
                        f"optional external adapter {name!r} is unavailable",
                        "governed_package.evidence_adapters",
                        level="warning",
                    )
                )
        if _external_critical_count(package) and "security" not in _gate_roles(package):
            diagnostics.append(
                _diag(
                    "CRITICAL_EXTERNAL_EVIDENCE_REQUIRES_SECURITY_GATE",
                    "critical external evidence requires a security approval gate",
                    "governed_package.approval_gates",
                )
            )
        meta = _scan_meta(package)
        if meta.get("has_license") is False:
            diagnostics.append(
                _diag(
                    "PACKAGE_WITHOUT_LICENSE",
                    "package scan did not find a license file",
                    "governed_package.scan_metadata.has_license",
                    level="warning",
                )
            )
        if meta.get("has_readme") is False:
            diagnostics.append(
                _diag(
                    "PACKAGE_WITHOUT_README",
                    "package scan did not find a README file",
                    "governed_package.scan_metadata.has_readme",
                    level="warning",
                )
            )
        if _scan_count(package, "binary_files"):
            diagnostics.append(
                _diag(
                    "PACKAGE_CONTAINS_BINARY_FILES",
                    "package scan found binary-like files",
                    "governed_package.scan_metadata.risk_surface_counts.binary_files",
                    level="warning",
                )
            )
        if _scan_count(package, "minified_files"):
            diagnostics.append(
                _diag(
                    "PACKAGE_CONTAINS_MINIFIED_FILES",
                    "package scan found long-line or minified files",
                    "governed_package.scan_metadata.risk_surface_counts.minified_files",
                    level="warning",
                )
            )
        if meta.get("remote_endpoints_unclear") is True:
            diagnostics.append(
                _diag(
                    "PACKAGE_HAS_UNCLEAR_REMOTE_ENDPOINTS",
                    "package scan found remote endpoints with unclear purpose",
                    "governed_package.scan_metadata.remote_endpoints_unclear",
                    level="warning",
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
    scan = scan_package(
        source,
        package_id=str(manifest.get("package_id", "package")),
        package_claims=manifest.get("claims") if isinstance(manifest.get("claims"), dict) else None,
        evidence_adapters=manifest.get("evidence_adapters"),
    )
    _scan_manifest_fields(manifest, scan, source=source, acquisition_mode="contract_source")
    _apply_scan_contract_requirements(manifest, scan)
    diagnostics = validate_governed_package(manifest)
    if any(item.level == "error" for item in diagnostics):
        messages = "; ".join(item.message for item in diagnostics)
        raise ValueError(f"governed package validation failed: {messages}")

    generated: list[Path] = []
    generated.extend(write_scan_reports(scan, out))
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
        "generated_governance_file_hashes": _artifact_hashes(out, generated),
        "scanner_report_hash": _sha256_file(out / "package_analysis.json"),
        "source_inventory_hash": _sha256_file(out / "source_inventory.md"),
        "external_evidence_report_hashes": _scan_report_hashes(out),
        "contract_hash": manifest["provenance"]["source_sha256"],
        "manifest_sha256": _sha256_file(manifest_path),
    }
    lock_path = out / "package_lock.json"
    _write_json(lock_path, lock)
    generated.append(lock_path)
    return generated


def verify_package_lock(package_dir: str | Path) -> list[Diagnostic]:
    try:
        reject_remote_or_device_path(
            package_dir,
            code_prefix="PACKAGE",
            noun="Governed package",
        )
        supplied = Path(package_dir)
        display_directory = supplied
        raw_directory = supplied if supplied.is_absolute() else Path.cwd() / supplied
        directory = inspect_local_directory(
            raw_directory,
            allowed_root=raw_directory.parent,
            code_prefix="PACKAGE",
            noun="Governed package",
            allow_missing=True,
        )
    except GovernanceError as exc:
        return [
            _diag(
                "UNSAFE_PACKAGE_PATH",
                str(exc),
                str(package_dir),
            )
        ]
    if directory is None:
        missing = display_directory / "package_lock.json"
        return [_diag("MISSING_PACKAGE_LOCK", "package_lock.json is required", missing.as_posix())]
    lock_path = directory / "package_lock.json"
    display_lock_path = display_directory / "package_lock.json"
    diagnostics: list[Diagnostic] = []
    try:
        raw_lock, _ = read_local_file_bytes(
            lock_path,
            allowed_root=directory,
            code_prefix="PACKAGE",
            noun="Package lock",
            max_bytes=1024 * 1024,
        )
    except GovernanceError as exc:
        if {item.code for item in exc.diagnostics} == {"PACKAGE_NOT_FOUND"}:
            return [
                _diag(
                    "MISSING_PACKAGE_LOCK",
                    "package_lock.json is required",
                    display_lock_path.as_posix(),
                )
            ]
        return [_diag("UNSAFE_PACKAGE_LOCK", str(exc), display_lock_path.as_posix())]
    try:
        lock = json.loads(raw_lock.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [_diag("INVALID_PACKAGE_LOCK_JSON", f"package_lock.json is invalid JSON: {exc}", display_lock_path.as_posix())]
    if not isinstance(lock, dict):
        return [
            _diag(
                "INVALID_PACKAGE_LOCK_JSON",
                "package_lock.json must contain one JSON object",
                display_lock_path.as_posix(),
            )
        ]
    manifest_path = directory / "package_manifest.json"
    display_manifest_path = display_directory / "package_manifest.json"
    manifest_missing = False
    try:
        raw_manifest, _ = read_local_file_bytes(
            manifest_path,
            allowed_root=directory,
            code_prefix="PACKAGE",
            noun="Package manifest",
            max_bytes=4 * 1024 * 1024,
        )
    except GovernanceError as exc:
        raw_manifest = None
        codes = {item.code for item in exc.diagnostics}
        if codes == {"PACKAGE_NOT_FOUND"}:
            manifest_missing = True
        else:
            diagnostics.append(
                _diag("UNSAFE_PACKAGE_MANIFEST", str(exc), display_manifest_path.as_posix())
            )
    if manifest_missing:
        diagnostics.append(
            _diag("MISSING_PACKAGE_MANIFEST", "package_manifest.json is required", display_manifest_path.as_posix())
        )
    elif raw_manifest is not None and lock.get("manifest_sha256") != _sha256_bytes(raw_manifest):
        diagnostics.append(
            _diag(
                "PACKAGE_LOCK_MANIFEST_HASH_MISMATCH",
                "package_manifest.json hash does not match package_lock.json",
                display_manifest_path.as_posix(),
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
        try:
            raw_artifact, _ = read_local_file_bytes(
                str(rel),
                allowed_root=directory,
                code_prefix="PACKAGE",
                noun="Locked package artifact",
                max_bytes=16 * 1024 * 1024,
            )
        except GovernanceError as exc:
            codes = {entry.code for entry in exc.diagnostics}
            display_path = display_directory / str(rel)
            if codes == {"PACKAGE_NOT_FOUND"}:
                diagnostics.append(
                    _diag(
                        "PACKAGE_LOCK_ARTIFACT_MISSING",
                        f"locked artifact missing: {rel}",
                        display_path.as_posix(),
                    )
                )
            else:
                diagnostics.append(
                    _diag(
                        "UNSAFE_PACKAGE_LOCK_ARTIFACT",
                        f"locked artifact path is unsafe: {rel}; {exc}",
                        display_path.as_posix(),
                    )
                )
            continue
        if _sha256_bytes(raw_artifact) != expected:
            diagnostics.append(
                _diag(
                    "PACKAGE_LOCK_ARTIFACT_HASH_MISMATCH",
                    f"artifact hash mismatch for {rel}",
                    (display_directory / str(rel)).as_posix(),
                )
            )
    return diagnostics


def verify_registered_artifact_hashes(
    package: dict[str, Any],
    package_dir: str | Path,
) -> list[Diagnostic]:
    if package.get("registration_mode") != "existing":
        return []
    source_path = package.get("source_path")
    if not _non_empty_string(source_path):
        return [_diag("MISSING_REGISTERED_SOURCE_PATH", "registered packages require source_path", "source_path")]

    try:
        reject_remote_or_device_path(
            package_dir,
            code_prefix="PACKAGE",
            noun="Governed package",
        )
        reject_remote_or_device_path(
            str(source_path),
            code_prefix="PACKAGE",
            noun="Registered package source",
        )
    except GovernanceError as exc:
        return [_diag("UNSAFE_REGISTERED_SOURCE_PATH", str(exc), "source_path")]
    raw_source = Path(str(source_path))
    candidates = [raw_source]
    if not raw_source.is_absolute():
        candidates.append(Path(package_dir) / raw_source)
    source = None
    source_display = None
    for candidate in candidates:
        absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
        try:
            inspected = inspect_local_directory(
                absolute,
                allowed_root=absolute.parent,
                code_prefix="PACKAGE",
                noun="Registered package source",
                allow_missing=True,
            )
        except GovernanceError as exc:
            return [_diag("UNSAFE_REGISTERED_SOURCE_PATH", str(exc), "source_path")]
        if inspected is not None:
            source = inspected
            source_display = candidate
            break
    if source is None or source_display is None:
        return []

    diagnostics: list[Diagnostic] = []
    for item in _as_list(package.get("artifacts")):
        if not isinstance(item, dict):
            continue
        rel = item.get("path")
        expected = item.get("sha256")
        if not _non_empty_string(rel) or not _non_empty_string(expected):
            continue
        try:
            raw_artifact, _ = read_local_file_bytes(
                str(rel),
                allowed_root=source,
                code_prefix="PACKAGE",
                noun="Registered package artifact",
                max_bytes=16 * 1024 * 1024,
            )
        except GovernanceError as exc:
            codes = {entry.code for entry in exc.diagnostics}
            display_path = source_display / str(rel)
            if codes == {"PACKAGE_NOT_FOUND"}:
                diagnostics.append(
                    _diag(
                        "REGISTERED_ARTIFACT_MISSING",
                        f"registered artifact missing from source: {rel}",
                        display_path.as_posix(),
                    )
                )
            else:
                diagnostics.append(
                    _diag(
                        "UNSAFE_REGISTERED_ARTIFACT_PATH",
                        f"registered artifact path is unsafe: {rel}; {exc}",
                        display_path.as_posix(),
                    )
                )
            continue
        if _sha256_bytes(raw_artifact) != expected:
            diagnostics.append(
                _diag(
                    "REGISTERED_ARTIFACT_HASH_MISMATCH",
                    f"registered artifact hash mismatch for {rel}",
                    (source_display / str(rel)).as_posix(),
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
    scan = scan_package(
        source,
        package_id=str(manifest.get("package_id", "package")),
        package_claims=manifest.get("claims") if isinstance(manifest.get("claims"), dict) else None,
        evidence_adapters=manifest.get("evidence_adapters"),
    )
    _scan_manifest_fields(manifest, scan, source=source, acquisition_mode="existing_directory")
    _apply_scan_contract_requirements(manifest, scan)
    diagnostics = validate_governed_package(manifest)
    if any(item.level == "error" for item in diagnostics):
        messages = "; ".join(item.message for item in diagnostics)
        raise ValueError(f"registered package validation failed: {messages}")

    written: list[Path] = []
    written.extend(write_scan_reports(scan, out))
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
        "generated_governance_file_hashes": _artifact_hashes(out, written),
        "registered_artifact_hashes": manifest["artifact_hashes"],
        "payload_file_hashes": manifest["artifact_hashes"],
        "scanner_report_hash": _sha256_file(out / "package_analysis.json"),
        "source_inventory_hash": _sha256_file(out / "source_inventory.md"),
        "external_evidence_report_hashes": _scan_report_hashes(out),
        "contract_hash": manifest["provenance"]["source_sha256"],
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

    scan = scan_package(source, package_id=f"radar-{source.name or 'source'}")
    secret_paths = {item["file_path"] for item in scan["findings"]["secrets"]}
    detected: list[dict[str, Any]] = [
        {
            "path": item["path"],
            "type": _artifact_type(Path(item["path"])),
            "sha256": item["sha256"],
            "secret_like": item["path"] in secret_paths,
            "binary_like": item["binary_like"],
            "large_file": item["large_file"],
        }
        for item in scan["files"]
    ]
    safety_findings: list[dict[str, Any]] = [
        {
            "path": item.get("file_path"),
            "finding": "possible_secret"
            if item.get("finding_type") == "secret_like_pattern"
            else item.get("finding_type", "risk_surface"),
            "detail": "Risk material was detected and values were redacted where needed.",
            "severity": item.get("severity"),
        }
        for group in scan["findings"].values()
        for item in group
    ]

    safe_artifacts = [
        {"id": item["path"].replace("/", "-"), "path": item["path"], "type": item["type"]}
        for item in detected
        if not item["secret_like"]
    ]
    inferred_risk = scan["risk_surface"]["risk_tier"]
    evidence = [
        {"id": "inventory_report", "type": "inventory", "required": True},
        {"id": "package_analysis", "type": "package_analysis", "required": True},
        {"id": "risk_surface_report", "type": "risk_surface", "required": True},
        {"id": "claim_vs_evidence_report", "type": "claim_vs_evidence", "required": True},
        {"id": "review_record", "type": "review", "required": True},
    ]
    if scan["findings"]["hooks"]:
        evidence.append({"id": "hook_risk_review", "type": "hook_risk_review", "required": True})
    if scan["findings"]["mcp"]:
        evidence.append({"id": "mcp_risk_review", "type": "mcp_risk_review", "required": True})
    if scan["findings"]["secrets"]:
        evidence.append({"id": "secret_scan_report", "type": "secret_scan", "required": True})
    if scan["findings"]["endpoints"]:
        evidence.append({"id": "endpoint_scan_report", "type": "endpoint_scan", "required": True})
    if scan["findings"]["commands"]:
        evidence.append({"id": "command_risk_report", "type": "command_risk", "required": True})
    gates = [
        {
            "id": "gate-review",
            "required_evidence": [item["id"] for item in evidence],
            "eligible_approver_roles": ["reviewer"],
            "denied_approver_types": ["execution_surface", "ai_tool"],
        }
    ]
    source_sha = scan["source_hash"]
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
        "scan_summary": {
            "scanner": scan["scanner"],
            "summary": scan["summary"],
            "risk_surface": scan["risk_surface"],
            "claim_vs_evidence": scan["claim_vs_evidence"],
            "external_evidence_summary": scan["external_evidence_summary"],
        },
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
        if contract_path.resolve() == report_path.resolve():
            raise ValueError(
                "suggested contract output path collides with radar report path; use a .nyx output path"
            )
        contract = _radar_contract(report)
        _write_text(contract_path, yaml.safe_dump(contract, sort_keys=False, width=100))
        report["suggested_contract_ref"] = contract_path.as_posix()
        _write_json(report_path, report)
    else:
        report_path = out_path
        if report_path.suffix.lower() != ".json":
            report_path = report_path / "radar_report.json"
            write_scan_reports(scan, report_path.parent)
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
        diagnostics.extend(verify_registered_artifact_hashes(package, source))
        return diagnostics
    package = load_governed_package_source(source)
    base_dir = source.parent if source.suffix.lower() == ".json" else None
    diagnostics = validate_governed_package(package, base_dir=base_dir)
    if source.name == "package_manifest.json" and (source.parent / "package_lock.json").exists():
        diagnostics.extend(verify_package_lock(source.parent))
        diagnostics.extend(verify_registered_artifact_hashes(package, source.parent))
    return diagnostics
