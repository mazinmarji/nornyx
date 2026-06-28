"""Full-output within-repo drift gate.

`AGENTS.md` does not render policy rules, so a drift gate that diffs only
`AGENTS.md` (as earlier docs suggested) stays green when `policy.yaml` changes.
This checker regenerates the contract to a throwaway directory and compares the
**entire** generated artifact set — by sha256, straight from the generation
manifest — against the committed output directory. Any added, removed, or changed
artifact is reported as drift.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from .checker import check_document, has_errors
from .generator import generate_artifacts
from .parser import load_nyx

REPORT_SCHEMA = "nornyx.repo_drift_report.v0.1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_repo_drift(contract: str | Path, committed_out: str | Path) -> dict[str, Any]:
    """Compare a committed generated-artifact directory against a fresh generate.

    Returns a report dict with ``status`` in {"pass", "drift", "error"} and a
    per-artifact breakdown. ``committed_out`` is the directory the repo committed
    (e.g. ``.nyx-out/``) plus the root ``AGENTS.md`` is checked separately by the
    caller if it copies it elsewhere.
    """
    contract = Path(contract)
    committed = Path(committed_out)

    doc = load_nyx(contract)
    diagnostics = check_document(doc)
    if has_errors(diagnostics):
        return {
            "schema": REPORT_SCHEMA,
            "status": "error",
            "contract": str(contract),
            "issues": [d.to_dict() for d in diagnostics if d.to_dict().get("level") == "error"],
            "artifacts": [],
        }

    with tempfile.TemporaryDirectory(prefix="nornyx-repo-drift-") as tmp:
        tmp_dir = Path(tmp)
        generate_artifacts(doc, tmp_dir)
        manifest = json.loads(
            (tmp_dir / "nornyx_generation_manifest.json").read_text(encoding="utf-8")
        )
        expected = {h["path"]: h["sha256"] for h in manifest.get("artifact_hashes", [])}

    artifacts: list[dict[str, str]] = []
    drift = False
    for rel, want in sorted(expected.items()):
        target = committed / rel
        if not target.is_file():
            artifacts.append({"path": rel, "status": "missing"})
            drift = True
        elif _sha256(target) != want:
            artifacts.append({"path": rel, "status": "changed"})
            drift = True
        else:
            artifacts.append({"path": rel, "status": "ok"})

    # Stray files the contract no longer generates (ignore the manifest itself).
    if committed.is_dir():
        for path in sorted(committed.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(committed).as_posix()
            if rel == "nornyx_generation_manifest.json":
                continue
            if rel not in expected:
                artifacts.append({"path": rel, "status": "stray"})
                drift = True

    return {
        "schema": REPORT_SCHEMA,
        "status": "drift" if drift else "pass",
        "contract": str(contract),
        "committed_out": str(committed),
        "artifacts": artifacts,
    }


def format_repo_drift(report: dict[str, Any]) -> str:
    lines = [
        "Nornyx repo drift gate (full output)",
        f"Status: {report['status']}",
        f"Contract: {report.get('contract')}",
    ]
    if report["status"] == "error":
        lines.append("Contract failed `nornyx check`:")
        for issue in report.get("issues", []):
            lines.append(f"  - {issue.get('code')}: {issue.get('message')}")
        return "\n".join(lines)
    for art in report["artifacts"]:
        if art["status"] != "ok":
            lines.append(f"  [{art['status'].upper()}] {art['path']}")
    if report["status"] == "drift":
        lines.append(
            "Fix: regenerate and re-copy artifacts "
            "(e.g. `nornyx generate <contract> --out <dir>`)."
        )
    else:
        lines.append("All generated artifacts match the committed output.")
    return "\n".join(lines)
