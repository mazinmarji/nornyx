from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

TRACE_EVENT_SCHEMA = "nornyx.trace_event.v0.1"
TRACE_BUNDLE_SCHEMA = "nornyx.trace_bundle.v0.1"


def _canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def _hash_hex(data: Any, length: int | None = None) -> str:
    digest = hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()
    return digest[:length] if length else digest


def make_trace_id(seed: Any) -> str:
    return _hash_hex({"trace_seed": seed}, length=32)


def make_trace_event(
    trace_id: str,
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
    status_code: str = "ok",
) -> dict[str, Any]:
    event_attributes = attributes or {}
    span_id = _hash_hex(
        {
            "trace_id": trace_id,
            "name": name,
            "parent_span_id": parent_span_id,
            "attributes": event_attributes,
        },
        length=16,
    )
    return {
        "schema": TRACE_EVENT_SCHEMA,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "name": name,
        "kind": "internal",
        "start_time_unix_nano": time.time_ns(),
        "end_time_unix_nano": time.time_ns(),
        "attributes": event_attributes,
        "status": {"code": status_code},
    }


def build_trace_bundle(events: list[dict[str, Any]]) -> dict[str, Any]:
    trace_id = events[0]["trace_id"] if events else make_trace_id("empty")
    digest = _hash_hex(events)
    return {
        "schema": TRACE_BUNDLE_SCHEMA,
        "trace_id": trace_id,
        "event_count": len(events),
        "events": events,
        "digest": {"algorithm": "sha256", "value": digest},
        "compatibility": {
            "opentelemetry": "local-json-shape-no-exporter",
            "note": "Fields mirror trace/span concepts without exporting telemetry.",
        },
    }


def write_trace_bundle(events: list[dict[str, Any]], path: str | Path) -> dict[str, Any]:
    bundle = build_trace_bundle(events)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle


def write_trace_digest(bundle: dict[str, Any], path: str | Path) -> dict[str, Any]:
    digest = {
        "schema": "nornyx.trace_digest.v0.1",
        "trace_id": bundle.get("trace_id"),
        "event_count": bundle.get("event_count", 0),
        "digest": bundle.get("digest"),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    return digest
