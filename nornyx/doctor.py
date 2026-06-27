from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


def find_repo_root(start: str | Path = ".") -> Path:
    cur = Path(start).resolve()
    for path in [cur, *cur.parents]:
        if (path / ".git").exists() or (path / "manifest.json").exists() or (path / "pyproject.toml").exists():
            return path
    return cur


def run_doctor(repo: str | Path = ".") -> dict[str, Any]:
    root = find_repo_root(repo)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, severity: str = "info") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "severity": severity})

    add("python", sys.version_info >= (3, 10), f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "error")
    add("git", shutil.which("git") is not None, shutil.which("git") or "not found", "warning")
    add("repo_root", root.exists(), str(root), "error")
    add("pyproject", (root / "pyproject.toml").exists(), "pyproject.toml present" if (root / "pyproject.toml").exists() else "missing", "warning")
    add("manifest", (root / "manifest.json").exists(), "manifest.json present" if (root / "manifest.json").exists() else "missing", "warning")
    add("examples", any(root.glob("examples/*.nyx")), "examples/*.nyx found" if any(root.glob("examples/*.nyx")) else "missing examples", "warning")
    add("pmo_status", (root / "docs" / "pmo" / "status" / "current_status.json").exists(), "PMO status present" if (root / "docs" / "pmo" / "status" / "current_status.json").exists() else "PMO status not generated", "info")
    add("pmo_portal", (root / "apps" / "nornyx-dev-pmo-portal" / "server.py").exists(), "Nornyx PMO portal present" if (root / "apps" / "nornyx-dev-pmo-portal" / "server.py").exists() else "Nornyx PMO portal not installed", "info")
    add("tests", (root / "tests").exists(), "tests directory present" if (root / "tests").exists() else "tests directory missing", "warning")

    return {
        "repo_root": str(root),
        "ok": all(c["ok"] or c["severity"] not in {"error"} for c in checks),
        "checks": checks,
    }


def format_doctor(report: dict[str, Any]) -> str:
    lines = [f"Nornyx doctor — repo: {report['repo_root']}", ""]
    for check in report["checks"]:
        mark = "PASS" if check["ok"] else "WARN" if check["severity"] != "error" else "FAIL"
        lines.append(f"[{mark}] {check['name']}: {check['detail']}")
    lines.append("")
    lines.append("Overall: " + ("ready" if report["ok"] else "needs attention"))
    return "\n".join(lines)


def doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2)
