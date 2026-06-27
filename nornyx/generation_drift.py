from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import tempfile
from typing import Any

from .checker import check_document, has_errors
from .generator import generate_artifacts
from .parser import load_nyx


BASELINE_SCHEMA = "nornyx.generated_drift_baseline.v0.1"


@dataclass(frozen=True)
class DriftCase:
    label: str
    source: str
    baseline: str


DEFAULT_DRIFT_CASES: tuple[DriftCase, ...] = (
    DriftCase(
        label="governed_delivery_control_plane",
        source="examples/governed_delivery_control_plane.nyx",
        baseline="tests/fixtures/generated_drift/governed_delivery_control_plane.json",
    ),
    DriftCase(
        label="nornyx_roadmap_goals",
        source="examples/nornyx_roadmap_goals.nyx",
        baseline="tests/fixtures/generated_drift/nornyx_roadmap_goals.json",
    ),
)


def _stable_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _load_manifest(repo_root: Path, source: str, out_dir: Path) -> dict[str, Any]:
    doc = load_nyx(repo_root / source)
    diagnostics = check_document(doc)
    if has_errors(diagnostics):
        messages = [diag.to_dict() for diag in diagnostics]
        raise ValueError(f"{source} has checker errors: {messages}")

    generate_artifacts(doc, out_dir)
    manifest_path = out_dir / "nornyx_generation_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_baseline(repo_root: Path, case: DriftCase) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"nornyx-drift-{case.label}-") as temp_dir:
        manifest = _load_manifest(repo_root, case.source, Path(temp_dir))

    return {
        "schema": BASELINE_SCHEMA,
        "label": case.label,
        "source": case.source,
        "generator_manifest": manifest,
    }


def _compare_baseline(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if expected.get("schema") != BASELINE_SCHEMA:
        issues.append(f"baseline schema mismatch: {expected.get('schema')!r}")
    if expected.get("source") != actual.get("source"):
        issues.append(
            f"baseline source mismatch: {expected.get('source')!r} != {actual.get('source')!r}"
        )
    if expected.get("generator_manifest") != actual.get("generator_manifest"):
        issues.append("generated manifest differs from committed baseline")
    return issues


def check_generated_drift(
    repo_root: str | Path,
    *,
    cases: tuple[DriftCase, ...] = DEFAULT_DRIFT_CASES,
    update_baseline: bool = False,
) -> dict[str, Any]:
    root = Path(repo_root)
    results: list[dict[str, Any]] = []

    for case in cases:
        baseline_path = root / case.baseline
        try:
            actual = build_baseline(root, case)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            results.append(
                {
                    "label": case.label,
                    "source": case.source,
                    "baseline": case.baseline,
                    "status": "error",
                    "issues": [str(exc)],
                }
            )
            continue

        if update_baseline:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(_stable_json(actual), encoding="utf-8")
            results.append(
                {
                    "label": case.label,
                    "source": case.source,
                    "baseline": case.baseline,
                    "status": "updated",
                    "issues": [],
                }
            )
            continue

        if not baseline_path.exists():
            results.append(
                {
                    "label": case.label,
                    "source": case.source,
                    "baseline": case.baseline,
                    "status": "missing",
                    "issues": ["baseline file is missing"],
                }
            )
            continue

        try:
            expected = json.loads(baseline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            results.append(
                {
                    "label": case.label,
                    "source": case.source,
                    "baseline": case.baseline,
                    "status": "error",
                    "issues": [str(exc)],
                }
            )
            continue
        issues = _compare_baseline(expected, actual)
        results.append(
            {
                "label": case.label,
                "source": case.source,
                "baseline": case.baseline,
                "status": "drift" if issues else "pass",
                "issues": issues,
            }
        )

    failing = [item for item in results if item["status"] not in {"pass", "updated"}]
    status = "updated" if update_baseline else ("fail" if failing else "pass")
    return {
        "schema": "nornyx.generated_drift_report.v0.1",
        "status": status,
        "case_count": len(results),
        "results": results,
    }


def format_drift_report(report: dict[str, Any]) -> str:
    lines = [
        "Nornyx generated artifact drift gate",
        f"Status: {report['status']}",
        f"Cases: {report['case_count']}",
        "",
    ]
    for result in report["results"]:
        lines.append(
            f"- {result['label']}: {result['status']} "
            f"({result['source']} -> {result['baseline']})"
        )
        for issue in result["issues"]:
            lines.append(f"  - {issue}")
    return "\n".join(lines)
