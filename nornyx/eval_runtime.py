from __future__ import annotations

import hashlib
import json
import operator
import re
from pathlib import Path
from typing import Any


class EvalRuntimeError(Exception):
    pass


METRIC_PATTERN = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)"
    r"(?:\s*(?P<op>>=|<=|==|!=|>|<)\s*(?P<threshold>.+?))?\s*$"
)

OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _named_mapping(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_hashes(path: Path) -> set[str]:
    hashes: set[str] = set()
    with path.open("rb") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                hashes.add(hashlib.sha256(stripped).hexdigest())
    return hashes


def _parse_literal(value: str) -> Any:
    cleaned = value.strip().strip("\"'")
    lowered = cleaned.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in cleaned:
            return float(cleaned)
        return int(cleaned)
    except ValueError:
        return cleaned


def parse_metric(metric: Any) -> dict[str, Any]:
    raw = str(metric).strip()
    match = METRIC_PATTERN.match(raw)
    if not match:
        return {
            "raw": raw,
            "name": raw,
            "operator": None,
            "threshold": None,
            "parse_status": "invalid",
            "reason": "Metric must be a bare metric name or a simple threshold expression.",
        }
    op = match.group("op")
    threshold = _parse_literal(match.group("threshold")) if op else True
    return {
        "raw": raw,
        "name": match.group("name"),
        "operator": op or "==",
        "threshold": threshold,
        "parse_status": "parsed",
    }


def _coerce_observed(value: Any, threshold: Any) -> Any:
    if isinstance(threshold, bool):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        return bool(value)
    if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            return float(value) if "." in value else int(value)
    return value


def _metric_result(metric: dict[str, Any], observed_metrics: dict[str, Any]) -> dict[str, Any]:
    result = dict(metric)
    if metric["parse_status"] != "parsed":
        result.update({"status": "invalid", "reason": metric["reason"]})
        return result

    name = metric["name"]
    if name not in observed_metrics:
        result.update(
            {
                "status": "pending_evidence",
                "observed": None,
                "reason": "Metric has no observed value in the local results input.",
            }
        )
        return result

    observed = observed_metrics[name]
    try:
        coerced = _coerce_observed(observed, metric["threshold"])
        passed = OPERATORS[metric["operator"]](coerced, metric["threshold"])
    except (TypeError, ValueError):
        result.update(
            {
                "status": "invalid",
                "observed": observed,
                "reason": "Observed metric value cannot be compared to the threshold.",
            }
        )
        return result

    result.update(
        {
            "status": "passed" if passed else "failed",
            "observed": observed,
            "reason": "Metric satisfied the threshold."
            if passed
            else "Metric did not satisfy the threshold.",
        }
    )
    return result


def _results_for_eval(results: dict[str, Any] | None, eval_name: str) -> dict[str, Any]:
    if not isinstance(results, dict):
        return {}
    if eval_name in results and isinstance(results[eval_name], dict):
        payload = results[eval_name]
        metrics = payload.get("metrics")
        return metrics if isinstance(metrics, dict) else payload
    evals = results.get("evals")
    if isinstance(evals, dict):
        payload = evals.get(eval_name)
        if isinstance(payload, dict):
            metrics = payload.get("metrics")
            return metrics if isinstance(metrics, dict) else payload
    metrics = results.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _dataset_entries(eval_def: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    raw_entries = (
        _as_list(eval_def.get("datasets"))
        + _as_list(eval_def.get("dataset"))
        + _as_list(eval_def.get("holdouts"))
        + _as_list(eval_def.get("holdout"))
        + _as_list(eval_def.get("holdout_set"))
    )
    for index, raw in enumerate(raw_entries, start=1):
        if isinstance(raw, str):
            split = "holdout" if "holdout" in raw.lower() else "dataset"
            entries.append({"name": f"dataset_{index}", "path": raw, "split": split})
        elif isinstance(raw, dict):
            item = dict(raw)
            path = item.get("path") or item.get("file") or item.get("uri")
            if path:
                item["path"] = str(path)
            item.setdefault("name", f"dataset_{index}")
            item.setdefault("split", "holdout" if "holdout" in str(item.get("name")).lower() else "dataset")
            entries.append(item)
    integrity = eval_def.get("integrity")
    if isinstance(integrity, dict):
        for key in ["holdout", "holdout_set"]:
            for raw in _as_list(integrity.get(key)):
                if isinstance(raw, str):
                    entries.append({"name": key, "path": raw, "split": "holdout"})
                elif isinstance(raw, dict):
                    item = dict(raw)
                    item.setdefault("name", key)
                    item.setdefault("split", "holdout")
                    entries.append(item)
    return entries


def _resolve_dataset(path_text: str, repo: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path(repo) / path


def _dataset_report(eval_def: dict[str, Any], repo: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reports = []
    blockers = []
    for entry in _dataset_entries(eval_def):
        path_text = str(entry.get("path", "")).strip()
        report = {
            "name": str(entry.get("name")),
            "split": str(entry.get("split", "dataset")),
            "path": path_text,
            "status": "not_checked",
        }
        if "://" in path_text:
            report.update(
                {
                    "status": "blocked",
                    "reason": "External eval datasets are not read by the local runtime.",
                }
            )
            blockers.append(
                {
                    "code": "EXTERNAL_DATASET_NOT_ALLOWED",
                    "dataset": report["name"],
                    "reason": report["reason"],
                }
            )
        else:
            resolved = _resolve_dataset(path_text, repo)
            if not resolved.exists():
                report.update({"status": "missing", "reason": "Dataset file does not exist."})
                blockers.append(
                    {
                        "code": "DATASET_NOT_FOUND",
                        "dataset": report["name"],
                        "path": path_text,
                        "reason": report["reason"],
                    }
                )
            elif not resolved.is_file():
                report.update({"status": "blocked", "reason": "Dataset path is not a file."})
                blockers.append(
                    {
                        "code": "DATASET_NOT_FILE",
                        "dataset": report["name"],
                        "path": path_text,
                        "reason": report["reason"],
                    }
                )
            else:
                line_count = sum(1 for line in resolved.read_bytes().splitlines() if line.strip())
                report.update(
                    {
                        "status": "hashed",
                        "sha256": _hash_file(resolved),
                        "bytes": resolved.stat().st_size,
                        "non_empty_lines": line_count,
                    }
                )
        reports.append(report)
    return reports, blockers


def _integrity_checks(
    eval_def: dict[str, Any],
    datasets: list[dict[str, Any]],
    dataset_blockers: list[dict[str, Any]],
    repo: str | Path,
) -> list[dict[str, Any]]:
    checks = []
    integrity = eval_def.get("integrity")
    integrity = integrity if isinstance(integrity, dict) else {}

    holdouts = [item for item in datasets if "holdout" in item.get("split", "").lower()]
    checks.append(
        {
            "code": "HOLDOUT_DECLARED",
            "status": "passed" if holdouts else "warning",
            "reason": "Holdout dataset declared."
            if holdouts
            else "No holdout dataset is declared for this eval.",
        }
    )

    contamination_declared = bool(
        _text_list(integrity.get("contamination_checks") or eval_def.get("contamination_checks"))
    )
    checks.append(
        {
            "code": "CONTAMINATION_CHECK_DECLARED",
            "status": "passed" if contamination_declared else "warning",
            "reason": "Contamination check metadata declared."
            if contamination_declared
            else "No contamination check metadata is declared.",
        }
    )

    adversarial_declared = bool(
        integrity.get("adversarial_rotation")
        or integrity.get("adversarial_rotations")
        or eval_def.get("adversarial_rotation")
    )
    checks.append(
        {
            "code": "ADVERSARIAL_ROTATION_DECLARED",
            "status": "passed" if adversarial_declared else "warning",
            "reason": "Adversarial rotation metadata declared."
            if adversarial_declared
            else "No adversarial rotation metadata is declared.",
        }
    )

    baseline_declared = bool(
        integrity.get("baseline")
        or eval_def.get("baseline")
        or eval_def.get("regression_baseline")
        or eval_def.get("compare_to")
    )
    checks.append(
        {
            "code": "REGRESSION_BASELINE_DECLARED",
            "status": "passed" if baseline_declared else "warning",
            "reason": "Regression baseline metadata declared."
            if baseline_declared
            else "No regression baseline metadata is declared.",
        }
    )

    checks.extend({**blocker, "status": "blocked"} for blocker in dataset_blockers)

    train_sets = [
        item
        for item in datasets
        if item.get("status") == "hashed" and str(item.get("split", "")).lower() in {"train", "training"}
    ]
    holdout_sets = [item for item in holdouts if item.get("status") == "hashed"]
    for train in train_sets:
        train_hashes = _line_hashes(_resolve_dataset(train["path"], repo))
        for holdout in holdout_sets:
            overlap = train_hashes & _line_hashes(_resolve_dataset(holdout["path"], repo))
            checks.append(
                {
                    "code": "HOLDOUT_TRAIN_OVERLAP",
                    "status": "blocked" if overlap else "passed",
                    "train_dataset": train["name"],
                    "holdout_dataset": holdout["name"],
                    "overlap_count": len(overlap),
                    "reason": "Holdout overlaps with training data."
                    if overlap
                    else "No line-level overlap detected between training and holdout data.",
                }
            )

    return checks


def _eval_status(metrics: list[dict[str, Any]], integrity: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in integrity):
        return "blocked_integrity"
    if any(item["status"] == "failed" for item in metrics):
        return "failed"
    if any(item["status"] == "invalid" for item in metrics):
        return "invalid"
    if any(item["status"] == "pending_evidence" for item in metrics):
        return "pending_evidence"
    if any(item["status"] == "warning" for item in integrity):
        return "passed_with_integrity_warnings"
    return "passed"


def _summary(evals: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "evals": len(evals),
        "metrics": 0,
        "passed_metrics": 0,
        "failed_metrics": 0,
        "pending_metrics": 0,
        "invalid_metrics": 0,
        "integrity_warnings": 0,
        "integrity_blockers": 0,
        "datasets_hashed": 0,
    }
    for eval_report in evals:
        for metric in eval_report["metrics"]:
            summary["metrics"] += 1
            if metric["status"] == "passed":
                summary["passed_metrics"] += 1
            elif metric["status"] == "failed":
                summary["failed_metrics"] += 1
            elif metric["status"] == "pending_evidence":
                summary["pending_metrics"] += 1
            elif metric["status"] == "invalid":
                summary["invalid_metrics"] += 1
        for check in eval_report["integrity_checks"]:
            if check["status"] == "warning":
                summary["integrity_warnings"] += 1
            elif check["status"] == "blocked":
                summary["integrity_blockers"] += 1
        summary["datasets_hashed"] += sum(
            1 for dataset in eval_report["datasets"] if dataset["status"] == "hashed"
        )
    return summary


def _overall_status(evals: list[dict[str, Any]], summary: dict[str, int]) -> str:
    statuses = {item["status"] for item in evals}
    if "blocked_integrity" in statuses:
        return "blocked_integrity"
    if "failed" in statuses:
        return "failed"
    if "invalid" in statuses:
        return "invalid"
    if "pending_evidence" in statuses:
        return "pending_evidence"
    if summary["integrity_warnings"]:
        return "passed_with_integrity_warnings"
    return "passed"


def evaluate_document_evals(
    doc: dict[str, Any],
    *,
    eval_names: list[str] | None = None,
    results: dict[str, Any] | None = None,
    repo: str | Path = ".",
) -> dict[str, Any]:
    evals = _named_mapping(doc.get("evals"))
    selected = eval_names or list(evals)
    missing = [name for name in selected if name not in evals]
    if missing:
        raise EvalRuntimeError(f"Unknown eval reference(s): {', '.join(missing)}")

    reports = []
    for name in selected:
        eval_def = evals[name]
        observed_metrics = _results_for_eval(results, name)
        metric_results = [
            _metric_result(parse_metric(metric), observed_metrics)
            for metric in _text_list(eval_def.get("metrics"))
        ]
        datasets, dataset_blockers = _dataset_report(eval_def, repo)
        integrity = _integrity_checks(eval_def, datasets, dataset_blockers, repo)
        reports.append(
            {
                "name": name,
                "status": _eval_status(metric_results, integrity),
                "metrics": metric_results,
                "datasets": datasets,
                "integrity_checks": integrity,
            }
        )

    summary = _summary(reports)
    return {
        "schema": "nornyx.eval_report.v0.1",
        "mode": "safe_local_eval_manifest",
        "status": _overall_status(reports, summary),
        "summary": summary,
        "safety": {
            "models_called": False,
            "tools_executed": False,
            "external_connectors_used": False,
            "network_used": False,
            "datasets_read": summary["datasets_hashed"],
        },
        "evals": reports,
    }


def load_eval_results(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalRuntimeError(f"Cannot read eval results {result_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvalRuntimeError(f"Invalid eval results JSON in {result_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvalRuntimeError("Eval results JSON must be an object")
    return data


def write_eval_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
