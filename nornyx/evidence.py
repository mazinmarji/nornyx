from __future__ import annotations

from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_entry(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def create_evidence_pack(
    out_dir: str | Path,
    status: str = "scaffold",
    *,
    trace_digest: dict[str, Any] | None = None,
    runtime_artifacts: list[str | Path] | None = None,
) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    paths: list[Path] = []
    for name, content in {
        "test_report.json": json.dumps({"status": "not_run", "tests": []}, indent=2),
        "eval_report.json": json.dumps({"status": "not_run", "evals": []}, indent=2),
        "security_report.md": "# Security Report\n\nNot run in scaffold.\n",
        "risk_update.md": "# Risk Update\n\nNo risks assessed in scaffold.\n",
        "approval_log.json": json.dumps({"approvals": []}, indent=2),
        "trace_digest.json": json.dumps(
            trace_digest or {"status": "not_available"},
            indent=2,
        ),
    }.items():
        p = out / name
        p.write_text(content, encoding="utf-8")
        paths.append(p)
    payload = {
        "schema": "nornyx.evidence_pack.v0.1",
        "created_at": timestamp,
        "status": status,
        "note": "Local evidence pack. Runtime artifacts are recorded but not executed.",
        "artifacts": [path.name for path in paths],
        "artifact_hashes": [_artifact_entry(path, out) for path in paths],
        "runtime_artifacts": [str(path) for path in runtime_artifacts or []],
        "trace_digest": trace_digest,
    }
    manifest = out / "evidence_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths.insert(0, manifest)
    return paths
