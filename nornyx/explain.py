from __future__ import annotations

import json
from typing import Any


def _by_name(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {item.get("name"): item for item in items if isinstance(item, dict) and item.get("name")}


def explain_document(doc: dict[str, Any], symbol: str | None = None, *, as_json: bool = False) -> str:
    project = doc.get("project", {}) if isinstance(doc.get("project"), dict) else {}
    payload: dict[str, Any] = {
        "project": project.get("name", "UnnamedProject"),
        "profile": project.get("profile", "unspecified"),
        "nornyx_version": doc.get("nornyx"),
        "counts": {
            "goals": len(doc.get("goals", []) or []),
            "contexts": len(doc.get("contexts", []) or []),
            "agents": len(doc.get("agents", []) or []),
            "policies": len(doc.get("policies", []) or []),
            "harnesses": len(doc.get("harnesses", []) or []),
            "evals": len(doc.get("evals", []) or []),
        },
    }

    if symbol:
        collections = {
            "goal": doc.get("goals", []) or [],
            "context": doc.get("contexts", []) or [],
            "agent": doc.get("agents", []) or [],
            "policy": doc.get("policies", []) or [],
            "harness": doc.get("harnesses", []) or [],
            "eval": doc.get("evals", []) or [],
            "skill": doc.get("skills", []) or [],
        }
        found = None
        found_type = None
        for kind, items in collections.items():
            for item in items:
                if not isinstance(item, dict):
                    continue
                if symbol in {item.get("name"), item.get("id"), item.get("title")}:
                    found = item
                    found_type = kind
                    break
            if found:
                break
        payload["symbol"] = {"query": symbol, "type": found_type, "value": found}

    if as_json:
        return json.dumps(payload, indent=2)

    lines = [f"Project: {payload['project']}", f"Profile: {payload['profile']}", f"Nornyx: {payload['nornyx_version']}", ""]
    lines.append("Blocks:")
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: {value}")
    if symbol:
        lines.append("")
        sym = payload.get("symbol", {})
        if sym.get("value"):
            lines.append(f"Symbol: {symbol} ({sym.get('type')})")
            for k, v in sym["value"].items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"Symbol not found: {symbol}")
    return "\n".join(lines)
