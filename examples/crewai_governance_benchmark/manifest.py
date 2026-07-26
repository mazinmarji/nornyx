"""The validation manifest: a deterministic hash of every input and output.

A reviewer who reruns the benchmark can compare this file to check that the
contract, the lock, the scenario definitions, the code that produced the numbers,
and every emitted artifact are byte-identical to the run being reviewed. It
collects and transmits nothing: it hashes local files only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from config import BENCHMARK_DIR, CONTRACT, GENERATED_ARTIFACTS, LOCK

# The benchmark's own source. Hashing these means a reviewer can tell whether the
# numbers were produced by the code they are reading.
SOURCE_FILES = (
    "benchmark.py",
    "business.py",
    "config.py",
    "deterministic_llm.py",
    "ledger.py",
    "manifest.py",
    "metrics.py",
    "report.py",
    "runtime.py",
    "scenarios.py",
    "variant_governed.py",
    "variant_plain.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _entry(path: Path, role: str, root: Path) -> dict[str, Any]:
    try:
        name = str(path.relative_to(root))
    except ValueError:
        name = path.name
    return {
        "path": name,
        "role": role,
        "bytes": path.stat().st_size,
        "digest": sha256_file(path),
    }


def build_manifest(out_dir: Path, *, contract_digest: str, lock_digest: str) -> dict[str, Any]:
    """Hash every governance input, benchmark source file, and emitted artifact."""
    inputs: list[dict[str, Any]] = [
        _entry(CONTRACT, "benchmark_contract", CONTRACT.parent),
        _entry(LOCK, "network_lock", LOCK.parent),
    ]
    for artifact in sorted(GENERATED_ARTIFACTS.glob("*.json")):
        inputs.append(_entry(artifact, "generated_control_artifact", CONTRACT.parent))
    for fixture in sorted((CONTRACT.parent / "governance_evidence").glob("*.json")):
        inputs.append(_entry(fixture, "governance_evidence_record", CONTRACT.parent))

    sources = [
        _entry(BENCHMARK_DIR / name, "benchmark_source", BENCHMARK_DIR)
        for name in SOURCE_FILES
        if (BENCHMARK_DIR / name).is_file()
    ]

    outputs = [
        _entry(path, "benchmark_output", out_dir)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "validation_manifest.json"
    ]

    return {
        "schema": "nornyx.benchmark_validation_manifest.v1",
        "collects_reviewer_data": False,
        "governance_digests": {
            "contract_digest": contract_digest,
            "network_lock_digest": lock_digest,
        },
        "inputs": inputs,
        "benchmark_sources": sources,
        "outputs": outputs,
        "counts": {
            "inputs": len(inputs),
            "benchmark_sources": len(sources),
            "outputs": len(outputs),
        },
    }
