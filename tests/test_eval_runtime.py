from __future__ import annotations

import json
from pathlib import Path

from nornyx.cli import main
from nornyx.eval_runtime import evaluate_document_evals, parse_metric
from nornyx.parser import load_nyx


def _eval(report: dict, name: str) -> dict:
    return next(item for item in report["evals"] if item["name"] == name)


def test_parse_metric_supports_threshold_and_bare_bool() -> None:
    assert parse_metric("accuracy >= 0.92") == {
        "raw": "accuracy >= 0.92",
        "name": "accuracy",
        "operator": ">=",
        "threshold": 0.92,
        "parse_status": "parsed",
    }
    assert parse_metric("no_secret_exposure") == {
        "raw": "no_secret_exposure",
        "name": "no_secret_exposure",
        "operator": "==",
        "threshold": True,
        "parse_status": "parsed",
    }


def test_eval_runtime_records_pending_metrics_and_integrity_warnings() -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    report = evaluate_document_evals(doc, eval_names=["RegressionEval"])
    eval_report = _eval(report, "RegressionEval")

    assert report["status"] == "pending_evidence"
    assert report["safety"]["models_called"] is False
    assert report["safety"]["external_connectors_used"] is False
    assert report["summary"]["pending_metrics"] == 3
    assert report["summary"]["integrity_warnings"] == 4
    assert eval_report["metrics"][0]["status"] == "pending_evidence"


def test_eval_runtime_passes_local_metrics_and_hashes_holdout(tmp_path: Path) -> None:
    (tmp_path / "train.jsonl").write_text('{"id": "train-1"}\n', encoding="utf-8")
    (tmp_path / "holdout.jsonl").write_text('{"id": "holdout-1"}\n', encoding="utf-8")
    doc = {
        "nornyx": "0.1",
        "project": {"name": "EvalFixture"},
        "evals": [
            {
                "name": "RegressionEval",
                "metrics": ["accuracy >= 0.9", "no_secret_exposure == true"],
                "datasets": [
                    {"name": "train", "path": "train.jsonl", "split": "train"},
                    {"name": "holdout", "path": "holdout.jsonl", "split": "holdout"},
                ],
                "integrity": {
                    "contamination_checks": ["line_hash_overlap"],
                    "adversarial_rotation": "weekly",
                    "baseline": "previous_release",
                },
            }
        ],
    }
    results = {"RegressionEval": {"accuracy": 0.94, "no_secret_exposure": True}}

    report = evaluate_document_evals(
        doc,
        eval_names=["RegressionEval"],
        results=results,
        repo=tmp_path,
    )

    assert report["status"] == "passed"
    assert report["summary"]["passed_metrics"] == 2
    assert report["summary"]["datasets_hashed"] == 2
    assert report["summary"]["integrity_blockers"] == 0


def test_eval_runtime_blocks_train_holdout_overlap(tmp_path: Path) -> None:
    duplicate = '{"id": "same"}\n'
    (tmp_path / "train.jsonl").write_text(duplicate, encoding="utf-8")
    (tmp_path / "holdout.jsonl").write_text(duplicate, encoding="utf-8")
    doc = {
        "nornyx": "0.1",
        "project": {"name": "EvalFixture"},
        "evals": [
            {
                "name": "RegressionEval",
                "metrics": ["accuracy >= 0.9"],
                "datasets": [
                    {"name": "train", "path": "train.jsonl", "split": "train"},
                    {"name": "holdout", "path": "holdout.jsonl", "split": "holdout"},
                ],
                "integrity": {
                    "contamination_checks": ["line_hash_overlap"],
                    "adversarial_rotation": "weekly",
                    "baseline": "previous_release",
                },
            }
        ],
    }

    report = evaluate_document_evals(
        doc,
        eval_names=["RegressionEval"],
        results={"RegressionEval": {"accuracy": 0.94}},
        repo=tmp_path,
    )

    assert report["status"] == "blocked_integrity"
    assert report["summary"]["integrity_blockers"] == 1
    overlap = next(
        item
        for item in _eval(report, "RegressionEval")["integrity_checks"]
        if item["code"] == "HOLDOUT_TRAIN_OVERLAP"
    )
    assert overlap["overlap_count"] == 1


def test_eval_run_cli_writes_report(tmp_path: Path, capsys) -> None:
    out_path = tmp_path / "eval_report.json"

    assert (
        main(
            [
                "eval-run",
                "examples/governed_delivery_control_plane.nyx",
                "--eval",
                "RegressionEval",
                "--out",
                str(out_path),
            ]
        )
        == 0
    )

    out = capsys.readouterr().out
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert "Eval report written" in out
    assert report["schema"] == "nornyx.eval_report.v0.1"
    assert report["summary"]["pending_metrics"] == 3
