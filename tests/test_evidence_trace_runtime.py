from __future__ import annotations

import json
from pathlib import Path

from nornyx.evidence import create_evidence_pack
from nornyx.harness_runtime import run_harness
from nornyx.parser import load_nyx
from nornyx.trace_runtime import make_trace_event, make_trace_id, write_trace_bundle


def test_trace_runtime_writes_otel_compatible_local_bundle(tmp_path: Path) -> None:
    trace_id = make_trace_id({"harness": "Demo"})
    event = make_trace_event(trace_id, "harness.run_planned", attributes={"safe": True})
    bundle = write_trace_bundle([event], tmp_path / "trace_bundle.json")

    assert bundle["schema"] == "nornyx.trace_bundle.v0.1"
    assert bundle["event_count"] == 1
    assert bundle["events"][0]["trace_id"] == trace_id
    assert bundle["events"][0]["span_id"]
    assert bundle["events"][0]["attributes"]["safe"] is True
    assert bundle["compatibility"]["opentelemetry"] == "local-json-shape-no-exporter"
    assert (tmp_path / "trace_bundle.json").exists()


def test_evidence_pack_records_hashes_and_trace_digest(tmp_path: Path) -> None:
    runtime_artifact = tmp_path / "runtime.json"
    runtime_artifact.write_text('{"ok": true}', encoding="utf-8")
    trace_digest = {
        "schema": "nornyx.trace_digest.v0.1",
        "trace_id": "abc",
        "event_count": 1,
        "digest": {"algorithm": "sha256", "value": "123"},
    }

    create_evidence_pack(
        tmp_path / "evidence",
        status="planned",
        trace_digest=trace_digest,
        runtime_artifacts=[runtime_artifact],
    )
    manifest = json.loads(
        (tmp_path / "evidence" / "evidence_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["schema"] == "nornyx.evidence_pack.v0.1"
    assert manifest["trace_digest"] == trace_digest
    assert any(item["path"] == "trace_digest.json" for item in manifest["artifact_hashes"])
    assert str(runtime_artifact) in manifest["runtime_artifacts"]


def test_harness_runtime_links_trace_and_evidence_outputs(tmp_path: Path) -> None:
    doc = load_nyx(Path("examples/governed_delivery_control_plane.nyx"))
    manifest = run_harness(doc, Path("."), tmp_path, harness_name="DevHarness")
    trace_bundle = json.loads((tmp_path / "trace_bundle.json").read_text(encoding="utf-8"))
    evidence_manifest = json.loads(
        (tmp_path / "evidence" / "evidence_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["trace_digest"]["digest"] == trace_bundle["digest"]
    assert evidence_manifest["trace_digest"] == manifest["trace_digest"]
    assert trace_bundle["event_count"] >= len(manifest["flow"])
    assert all(event["schema"] == "nornyx.trace_event.v0.1" for event in trace_bundle["events"])
