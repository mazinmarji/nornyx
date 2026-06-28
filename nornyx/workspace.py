"""Cross-repo / workspace policy consistency.

A single `.nyx` is the source of truth *within* one repo, but Nornyx has no
notion of a policy that lives *above* repos — so two repos can carry divergent
copies of the "same" org policy and each still passes its own gate. This module
adds a workspace layer: a `nornyx.workspace.yaml` declares canonical policies
once, lists member contracts, and `check_workspace` verifies every member's
named policy matches the canonical rule set.

It is a checker, not a runtime: it reads local files only — no network, no
mutation of member contracts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .parser import load_nyx
from .policy_runtime import normalize_policy_rules

REPORT_SCHEMA = "nornyx.workspace_report.v0.1"


class WorkspaceError(Exception):
    """Raised when the workspace manifest is malformed."""


def _canonical_ruleset(rules: Any) -> set[str]:
    """Normalize a canonical policy declaration (a `rules:`-style list, or a
    mapping with `deny:`/`require:`) into a comparable set of ``verb token``."""
    if isinstance(rules, dict):
        policy = rules
    else:
        policy = {"rules": rules or []}
    norm = normalize_policy_rules(policy)
    return {f"deny {r}" for r in norm["deny"]} | {f"require {r}" for r in norm["require"]}


def _member_ruleset(contract: Path, policy_name: str) -> set[str] | None:
    doc = load_nyx(contract)
    for pol in doc.get("policies", []) or []:
        if pol.get("name") == policy_name:
            norm = normalize_policy_rules(pol)
            return {f"deny {r}" for r in norm["deny"]} | {
                f"require {r}" for r in norm["require"]
            }
    return None


def check_workspace(manifest_path: str | Path) -> dict[str, Any]:
    """Verify every member contract matches the workspace's canonical policies."""
    manifest_path = Path(manifest_path)
    manifest = load_nyx(manifest_path)  # YAML; reuses Nornyx's safe loader
    root = manifest_path.resolve().parent

    canonical_block = manifest.get("policies")
    if not isinstance(canonical_block, dict) or not canonical_block:
        raise WorkspaceError(
            "workspace manifest must define `policies:` as a mapping of "
            "policy_name -> rules"
        )
    canonical = {name: _canonical_ruleset(rules) for name, rules in canonical_block.items()}

    members = manifest.get("members") or []
    if not members:
        raise WorkspaceError("workspace manifest must list `members:`")

    results: list[dict[str, Any]] = []
    drift = False
    for member in members:
        rel = member.get("path") if isinstance(member, dict) else member
        contract = (root / rel).resolve()
        member_result: dict[str, Any] = {"path": rel, "policies": []}
        if not contract.is_file():
            member_result["policies"].append({"status": "contract_missing"})
            drift = True
            results.append(member_result)
            continue
        for name, want in canonical.items():
            have = _member_ruleset(contract, name)
            if have is None:
                member_result["policies"].append({"policy": name, "status": "missing"})
                drift = True
            else:
                missing = sorted(want - have)
                extra = sorted(have - want)
                if missing or extra:
                    drift = True
                    member_result["policies"].append(
                        {
                            "policy": name,
                            "status": "drift",
                            "missing": missing,
                            "extra": extra,
                        }
                    )
                else:
                    member_result["policies"].append({"policy": name, "status": "ok"})
        results.append(member_result)

    return {
        "schema": REPORT_SCHEMA,
        "status": "drift" if drift else "pass",
        "workspace": manifest.get("workspace", manifest_path.stem),
        "canonical_policies": {k: sorted(v) for k, v in canonical.items()},
        "members": results,
    }


def format_workspace(report: dict[str, Any]) -> str:
    lines = [
        f"Nornyx workspace policy check: {report.get('workspace')}",
        f"Status: {report['status']}",
        f"Canonical policies: {', '.join(report['canonical_policies']) or '(none)'}",
        "",
    ]
    for member in report["members"]:
        flags = [p for p in member["policies"] if p["status"] != "ok"]
        mark = "OK" if not flags else "DRIFT"
        lines.append(f"  [{mark}] {member['path']}")
        for p in flags:
            if p["status"] == "contract_missing":
                lines.append("            - contract file not found")
            elif p["status"] == "missing":
                lines.append(f"            - missing policy: {p['policy']}")
            else:
                for r in p.get("missing", []):
                    lines.append(f"            - {p['policy']} missing: {r}")
                for r in p.get("extra", []):
                    lines.append(f"            + {p['policy']} extra:   {r}")
    return "\n".join(lines)
