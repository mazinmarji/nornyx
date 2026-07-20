"""Bounded local importer for external evaluation results (ADR-0038).

Nornyx does not execute external evaluation tools. This module converts one
supplied Promptfoo-style results file into the local results format consumed
by ``nornyx eval-run --results``, validating the input shape, recording the
producer and version, and binding the normalized evidence to the report
artifact's SHA-256 and the declared subject revision. Malformed or mismatched
reports are rejected. Nornyx does not replace Promptfoo, LangSmith, or
observability platforms; it validates supplied results against declared
thresholds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .governance.loader import reject_remote_or_device_path

MAX_REPORT_BYTES = 8 * 1024 * 1024
RESULTS_SCHEMA = "nornyx.imported_eval_results.v1"
SUPPORTED_TOOLS = ("promptfoo",)


class EvalImportError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalImportError(message)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6)


def convert_promptfoo_results(
    report_path: str | Path,
    *,
    eval_name: str,
    subject_revision: str | None = None,
) -> dict[str, Any]:
    """Convert one Promptfoo-style results JSON into eval-run results input.

    Accepts the stable ``promptfoo eval --output results.json`` shape: a JSON
    object whose ``results`` object contains a ``results`` array of test
    outcomes (``success``/``score``/``namedScores``) and a ``stats`` object
    with ``successes`` and ``failures`` counts.
    """

    reject_remote_or_device_path(
        report_path, code_prefix="EVAL_IMPORT", noun="External eval report"
    )
    path = Path(report_path)
    raw = path.read_bytes()
    _require(
        len(raw) <= MAX_REPORT_BYTES,
        f"External eval report exceeds the {MAX_REPORT_BYTES} byte bound.",
    )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvalImportError(f"Cannot parse the eval report: {exc}") from exc
    _require(isinstance(payload, dict), "Eval report must be a JSON object.")
    results_block = payload.get("results")
    _require(
        isinstance(results_block, dict),
        "Eval report must contain a 'results' object.",
    )
    outcomes = results_block.get("results")
    _require(
        isinstance(outcomes, list) and len(outcomes) > 0,
        "Eval report must contain a non-empty 'results.results' array.",
    )
    stats = results_block.get("stats")
    _require(
        isinstance(stats, dict),
        "Eval report must contain a 'results.stats' object.",
    )
    successes = stats.get("successes")
    failures = stats.get("failures")
    _require(
        isinstance(successes, int)
        and isinstance(failures, int)
        and successes >= 0
        and failures >= 0
        and successes + failures > 0,
        "Eval report stats must declare non-negative successes and failures.",
    )
    _require(
        successes + failures == len(outcomes),
        "Eval report stats do not match the number of recorded outcomes.",
    )

    named_scores: dict[str, list[float]] = {}
    scores: list[float] = []
    for index, outcome in enumerate(outcomes):
        _require(
            isinstance(outcome, dict),
            f"Eval outcome {index} must be an object.",
        )
        _require(
            isinstance(outcome.get("success"), bool),
            f"Eval outcome {index} must declare a boolean 'success'.",
        )
        score = outcome.get("score")
        if score is not None:
            _require(
                isinstance(score, (int, float)) and not isinstance(score, bool),
                f"Eval outcome {index} score must be numeric.",
            )
            scores.append(float(score))
        named = outcome.get("namedScores", {})
        _require(
            isinstance(named, dict),
            f"Eval outcome {index} namedScores must be an object.",
        )
        for name, value in named.items():
            _require(
                isinstance(value, (int, float)) and not isinstance(value, bool),
                f"Eval outcome {index} named score {name!r} must be numeric.",
            )
            named_scores.setdefault(str(name), []).append(float(value))

    metrics: dict[str, Any] = {
        name: _mean(values) for name, values in sorted(named_scores.items())
    }
    metrics["pass_rate"] = _mean(
        [1.0] * successes + [0.0] * failures
    )
    if scores:
        metrics["mean_score"] = _mean(scores)

    version = payload.get("results", {}).get("version")
    return {
        "schema": RESULTS_SCHEMA,
        "evals": {eval_name: {"metrics": metrics}},
        "provenance": {
            "producer": {
                "name": "promptfoo",
                "report_version": version if isinstance(version, int) else None,
            },
            "report_sha256": hashlib.sha256(raw).hexdigest(),
            "subject_revision": subject_revision,
            "converted_by": "nornyx.eval_import.v1",
            "outcome_count": len(outcomes),
        },
    }


def write_imported_results(results: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(results, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target
