"""Serialization and strict validation of the runtime-conformance report.

The bundled schema is closed at every level: unknown keys and invented status
values are rejected, not tolerated. That matters because every downstream claim
rests on the report meaning exactly what it says, and a permissive schema would
make each of those claims unenforceable.
"""

from __future__ import annotations

import json
import os
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from .model import CONFORMANCE_SCHEMA_ID, ConformanceReport

SCHEMA_PACKAGE = "nornyx_agentic_adapters.conformance.schemas"
SCHEMA_NAME = "runtime_conformance_report.schema.json"


def load_report_schema() -> dict[str, Any]:
    """Load the bundled report schema from this package's own resources."""
    text = (
        resources.files(SCHEMA_PACKAGE).joinpath(SCHEMA_NAME).read_text(encoding="utf-8")
    )
    return json.loads(text)


def serialize(report: ConformanceReport | dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, fixed indent, trailing newline.

    Sorted keys rather than insertion order so the bytes do not depend on how
    the payload happened to be assembled.
    """
    payload = report.as_dict() if isinstance(report, ConformanceReport) else report
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def validate_report(payload: Any) -> tuple[str, ...]:
    """Validate a report payload. Returns diagnostics; empty means valid.

    Returns diagnostics rather than raising so a caller can report every
    problem at once, and so a malformed report is itself a reportable
    conformance result rather than a crash.
    """
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - jsonschema ships with nornyx
        return ("jsonschema is not installed; the report cannot be validated",)

    if not isinstance(payload, dict):
        return (f"report must be a JSON object, got {type(payload).__name__}",)

    schema = load_report_schema()
    validator = jsonschema.Draft202012Validator(schema)
    diagnostics: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path)):
        pointer = "/".join(str(part) for part in error.absolute_path) or "<root>"
        diagnostics.append(f"{pointer}: {error.message}")
    return tuple(diagnostics)


def write_report(report: ConformanceReport | dict[str, Any], path: str | Path) -> Path:
    """Write the report atomically.

    A consumer must never read a truncated report and treat it as
    authoritative, so the payload is written to a temporary file in the
    destination directory and moved into place only once it is complete.
    """
    destination = Path(path)
    if destination.is_dir():
        raise IsADirectoryError(f"report destination {destination.name!r} is a directory")
    parent = destination.parent if str(destination.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)
    text = serialize(report)

    handle, temporary = tempfile.mkstemp(
        prefix=".conformance-", suffix=".json", dir=str(parent)
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, destination)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return destination


__all__ = [
    "CONFORMANCE_SCHEMA_ID",
    "SCHEMA_NAME",
    "SCHEMA_PACKAGE",
    "load_report_schema",
    "serialize",
    "validate_report",
    "write_report",
]
