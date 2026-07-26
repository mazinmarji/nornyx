"""The validation manifest: a hash of every governance input, source, and output.

A reviewer who reruns the benchmark can compare this file to check that the
contract, the lock, the scenario definitions, the code that produced the
numbers, and the emitted artifacts match the run being reviewed. It collects and
transmits nothing: it hashes local files only.

Two kinds of digest, kept apart on purpose
------------------------------------------
``candidate_digest`` folds every governance input and benchmark source file into
one value. It depends only on the candidate tree, so it is identical on every
machine and is the digest that binds a recorded result to the exact code and
contract that produced it.

Output digests are not all reproducible. ``benchmark.json``, ``benchmark.md``,
``dashboard.html`` and ``environment.json`` embed installed versions, the host
platform, and local wall-clock timings, so their bytes legitimately differ
between machines. Each output entry is therefore marked ``deterministic``, and
``deterministic_outputs_digest`` folds only the reproducible ones — the evidence
stream, its validation report, and the two per-scenario result files, none of
which contain a wall-clock value or an environment string. Comparing that digest
across two runs is a real integrity check; comparing every output digest is not.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from crewai_governance_benchmark.config import BENCHMARK_DIR, CONTRACT, GENERATED_ARTIFACTS, LOCK

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


# Outputs whose bytes are reproducible on any machine: none of them embeds a
# wall-clock timing, an absolute path, a platform string, or an installed
# version. Everything else is a machine-local rendering of the same run.
DETERMINISTIC_OUTPUTS = frozenset(
    {
        "nornyx_runtime_events.json",
        "nornyx_evidence_report.json",
        "plain_results.json",
        "governed_results.json",
    }
)


def fold_digests(entries: list[dict[str, Any]]) -> str:
    """One digest over ``(path, digest)`` pairs, independent of iteration order."""
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["digest"].encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def governance_inputs() -> list[dict[str, Any]]:
    """Hash entries for the contract, lock, control artifacts, and evidence records."""
    inputs: list[dict[str, Any]] = [
        _entry(CONTRACT, "benchmark_contract", CONTRACT.parent),
        _entry(LOCK, "network_lock", LOCK.parent),
    ]
    for artifact in sorted(GENERATED_ARTIFACTS.glob("*.json")):
        inputs.append(_entry(artifact, "generated_control_artifact", CONTRACT.parent))
    for fixture in sorted((CONTRACT.parent / "governance_evidence").glob("*.json")):
        inputs.append(_entry(fixture, "governance_evidence_record", CONTRACT.parent))
    return inputs


def benchmark_sources() -> list[dict[str, Any]]:
    """Hash entries for the benchmark's own source files."""
    return [
        _entry(BENCHMARK_DIR / name, "benchmark_source", BENCHMARK_DIR)
        for name in SOURCE_FILES
        if (BENCHMARK_DIR / name).is_file()
    ]


def candidate_digest() -> str:
    """The machine-independent digest of the exact candidate that produced a run.

    Computable without any output directory, so a recorded result can carry the
    identity of the tree that produced it, and a reviewer can tell in one
    comparison whether they are looking at the same candidate.
    """
    return fold_digests(governance_inputs() + benchmark_sources())


def build_manifest(out_dir: Path, *, contract_digest: str, lock_digest: str) -> dict[str, Any]:
    """Hash every governance input, benchmark source file, and emitted artifact."""
    inputs = governance_inputs()
    sources = benchmark_sources()

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if not path.is_file() or path.name == "validation_manifest.json":
            continue
        entry = _entry(path, "benchmark_output", out_dir)
        entry["deterministic"] = path.name in DETERMINISTIC_OUTPUTS
        outputs.append(entry)

    return {
        "schema": "nornyx.benchmark_validation_manifest.v2",
        "collects_reviewer_data": False,
        "governance_digests": {
            "contract_digest": contract_digest,
            "network_lock_digest": lock_digest,
        },
        # Machine-independent: binds this result to the exact candidate tree
        # (governance inputs + the benchmark source that produced the numbers).
        "candidate_digest": fold_digests(inputs + sources),
        "deterministic_outputs_digest": fold_digests(
            [entry for entry in outputs if entry["deterministic"]]
        ),
        "inputs": inputs,
        "benchmark_sources": sources,
        "outputs": outputs,
        "counts": {
            "inputs": len(inputs),
            "benchmark_sources": len(sources),
            "outputs": len(outputs),
            "deterministic_outputs": sum(1 for entry in outputs if entry["deterministic"]),
        },
        "note": (
            "candidate_digest and deterministic_outputs_digest are reproducible on any "
            "machine and are the values to compare across runs. The remaining output "
            "digests cover this snapshot's exact bytes only: benchmark.json, "
            "benchmark.md, dashboard.html and environment.json embed installed "
            "versions, the host platform, and local wall-clock timings."
        ),
    }
