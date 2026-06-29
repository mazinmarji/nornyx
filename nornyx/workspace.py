"""Cross-repo / workspace policy consistency.

A single `.nyx` is the source of truth *within* one repo, but Nornyx has no
notion of a policy that lives *above* repos — so two repos can carry divergent
copies of the "same" org policy and each still passes its own gate. This module
adds a workspace layer: a `nornyx.workspace.yaml` declares canonical policies
once, lists member contracts, and `check_workspace` verifies every member's
named policy matches the canonical rule set.

With ``write=True`` (sync mode) it also *propagates* the canonical policy into
each member: the org policy is edited in one place (the manifest) and pushed
down, so members stay self-contained and auditable without hand-copying. The
rewrite is surgical — it replaces only the matched policy's rule block and
leaves the rest of the contract (comments, other blocks) untouched.

It reads and writes local files only — no network.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .parser import load_nyx
from .policy_runtime import normalize_policy_rules

REPORT_SCHEMA = "nornyx.workspace_report.v0.1"

_RULE_KEYS = ("rules", "deny", "require")


class WorkspaceError(Exception):
    """Raised when the workspace manifest is malformed."""


def _canonical_ordered(rules: Any) -> list[str]:
    """Canonical rules as an ordered list of ``verb token`` strings.

    A `rules:`-style list keeps its declared order; a `deny:`/`require:` mapping
    emits all denies then all requires. Used for the written output so it is
    deterministic and matches the manifest's authored order."""
    if isinstance(rules, dict):
        norm = normalize_policy_rules(rules)
        return [f"deny {r}" for r in norm["deny"]] + [f"require {r}" for r in norm["require"]]
    ordered: list[str] = []
    for item in rules or []:
        norm = normalize_policy_rules({"rules": [item]})
        ordered += [f"deny {r}" for r in norm["deny"]] + [f"require {r}" for r in norm["require"]]
    return ordered


def _canonical_ruleset(rules: Any) -> set[str]:
    return set(_canonical_ordered(rules))


def _member_ruleset(contract: Path, policy_name: str) -> set[str] | None:
    doc = load_nyx(contract)
    for pol in doc.get("policies", []) or []:
        if pol.get("name") == policy_name:
            norm = normalize_policy_rules(pol)
            return {f"deny {r}" for r in norm["deny"]} | {
                f"require {r}" for r in norm["require"]
            }
    return None


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def sync_policy_in_contract(contract: Path, policy_name: str, ordered_rules: list[str]) -> bool:
    """Rewrite the named policy's rule block to ``ordered_rules`` in place.

    Surgical: keeps the policy's `- name:` line and any non-rule lines, removes
    existing `rules:`/`deny:`/`require:` sub-blocks, and writes one canonical
    `rules:` block. Returns True if the policy was found and rewritten."""
    lines = contract.read_text(encoding="utf-8").splitlines()
    n = len(lines)

    # Locate the top-level `policies:` block.
    pi = next(
        (i for i, ln in enumerate(lines) if ln.rstrip() == "policies:" and _indent(ln) == 0),
        None,
    )
    if pi is None:
        return False
    base = _indent(lines[pi])
    # The block ends at the next sibling *key* — a non-deeper line that is not a
    # list item. List items may sit at the key's own indent (YAML block sequence
    # at key indent, which is what `nornyx init` emits), so `- ` lines at `base`
    # are still inside the block.
    end = n
    for j in range(pi + 1, n):
        ln = lines[j]
        if ln.strip() == "" or ln.lstrip().startswith("#"):
            continue
        if _indent(ln) <= base and not ln.lstrip().startswith("- "):
            end = j
            break

    first_item = next(
        (k for k in range(pi + 1, end) if lines[k].lstrip().startswith("- ")), None
    )
    if first_item is None:
        return False
    item_indent = _indent(lines[first_item])
    # Only `- ` lines at the policy-item indent are items; deeper `- ` lines are
    # rule list entries and must not be treated as item boundaries.
    item_starts = [
        k
        for k in range(pi + 1, end)
        if lines[k].lstrip().startswith("- ") and _indent(lines[k]) == item_indent
    ]

    target: tuple[int, int] | None = None
    for idx, start in enumerate(item_starts):
        span_end = item_starts[idx + 1] if idx + 1 < len(item_starts) else end
        if any(re.search(rf"name:\s*{re.escape(policy_name)}\b", lines[k]) for k in range(start, span_end)):
            target = (start, span_end)
            break
    if target is None:
        return False

    start, span_end = target
    content_indent = item_indent + 2
    list_indent = content_indent + 2

    body = lines[start + 1 : span_end]
    kept: list[str] = []
    insert_index: int | None = None
    k = 0
    while k < len(body):
        ln = body[k]
        key = ln.strip().split(":", 1)[0]
        if _indent(ln) == content_indent and key in _RULE_KEYS:
            if insert_index is None:
                insert_index = len(kept)
            k += 1  # skip the rule key line, then its sequence items
            block: list[str] = []
            while k < len(body):
                cur = body[k]
                ind = _indent(cur)
                # A block sequence's items may sit at the key's own indent
                # (`deny:` then `- x` both at content_indent) or deeper. Both,
                # plus blank lines, belong to this rule block.
                if cur.strip() == "" or ind > content_indent or (
                    ind == content_indent and cur.lstrip().startswith("- ")
                ):
                    block.append(cur)
                    k += 1
                    continue
                break
            # Drop the rule content but keep any trailing separator blank lines.
            trailing: list[str] = []
            for cur in reversed(block):
                if cur.strip() == "":
                    trailing.insert(0, cur)
                else:
                    break
            kept.extend(trailing)
            continue
        kept.append(ln)
        k += 1
    if insert_index is None:
        insert_index = 0

    canonical = [f"{' ' * content_indent}rules:"] + [
        f"{' ' * list_indent}- {r}" for r in ordered_rules
    ]
    new_lines = (
        lines[: start + 1]
        + kept[:insert_index]
        + canonical
        + kept[insert_index:]
        + lines[span_end:]
    )
    text = "\n".join(new_lines)
    if not text.endswith("\n"):
        text += "\n"
    contract.write_text(text, encoding="utf-8", newline="\n")
    return True


def check_workspace(manifest_path: str | Path, *, write: bool = False) -> dict[str, Any]:
    """Verify every member contract matches the workspace's canonical policies.

    With ``write=True`` (sync mode), members whose named policy *exists but
    diverges* are rewritten to the canonical rule set and reported as ``synced``.
    A policy a member doesn't declare at all, or a missing contract file, is left
    for a human (still reported as drift) — sync edits existing policies, it does
    not invent new blocks or files."""
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
    canonical_ordered = {name: _canonical_ordered(rules) for name, rules in canonical_block.items()}

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
            elif want == have:
                member_result["policies"].append({"policy": name, "status": "ok"})
            elif write and sync_policy_in_contract(contract, name, canonical_ordered[name]):
                member_result["policies"].append({"policy": name, "status": "synced"})
            else:
                drift = True
                member_result["policies"].append(
                    {
                        "policy": name,
                        "status": "drift",
                        "missing": sorted(want - have),
                        "extra": sorted(have - want),
                    }
                )
        results.append(member_result)

    synced = any(p["status"] == "synced" for m in results for p in m["policies"])
    status = "drift" if drift else ("synced" if synced else "pass")
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
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
        statuses = {p["status"] for p in flags}
        if not flags:
            mark = "OK"
        elif statuses <= {"synced"}:
            mark = "SYNCED"
        else:
            mark = "DRIFT"
        lines.append(f"  [{mark}] {member['path']}")
        for p in flags:
            if p["status"] == "contract_missing":
                lines.append("            - contract file not found")
            elif p["status"] == "missing":
                lines.append(f"            - missing policy: {p['policy']} (add it by hand)")
            elif p["status"] == "synced":
                lines.append(f"            ~ {p['policy']} rewritten to the canonical rules")
            else:
                for r in p.get("missing", []):
                    lines.append(f"            - {p['policy']} missing: {r}")
                for r in p.get("extra", []):
                    lines.append(f"            + {p['policy']} extra:   {r}")
    syncable = any(
        p["status"] == "drift" for m in report["members"] for p in m["policies"]
    )
    if syncable:
        lines.append("")
        lines.append("Run with --write to propagate the canonical policy into diverging members.")
    return "\n".join(lines)


def format_workspace_failures(report: dict[str, Any]) -> str:
    lines: list[str] = []
    for member in report["members"]:
        failures = [
            p for p in member["policies"] if p["status"] not in ("ok", "synced")
        ]
        if not failures:
            continue
        lines.append(f"  [DRIFT] {member['path']}")
        for p in failures:
            if p["status"] == "contract_missing":
                lines.append("            - contract file not found")
            elif p["status"] == "missing":
                lines.append(f"            - missing policy: {p['policy']} (add it by hand)")
            else:
                for r in p.get("missing", []):
                    lines.append(f"            - {p['policy']} missing: {r}")
                for r in p.get("extra", []):
                    lines.append(f"            + {p['policy']} extra:   {r}")
    return "\n".join(lines)
