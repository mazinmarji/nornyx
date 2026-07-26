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

Both folds use each file's ``content_digest`` (line endings normalized) rather
than its raw-byte ``digest``, and POSIX-separated paths. Otherwise a Windows and
a Linux checkout of the *same commit* would produce different values, which is
precisely what these digests exist to rule out. The per-file ``digest`` remains
byte-exact, because detecting a locally edited artifact is a different question
from identifying a candidate.
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
    """The digest of a file's exact bytes, for detecting local tampering."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_content(path: Path) -> str:
    """The digest of a text file's *content*, independent of line-ending policy.

    Every file this manifest hashes is text. Whether it lands on disk with LF or
    CRLF is decided by the checkout (``core.autocrlf``) and by which platform
    wrote it — not by anything about the candidate. Folding raw bytes would make
    the cross-machine digests differ between a Windows and a Linux checkout of
    the *same commit*, which would defeat the one job those digests have.
    """
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _entry(path: Path, role: str, root: Path) -> dict[str, Any]:
    try:
        # POSIX separators always: a committed manifest is read on other
        # platforms, and "contract\\x.json" would not match there.
        name = path.relative_to(root).as_posix()
    except ValueError:
        name = path.name
    return {
        "path": name,
        "role": role,
        "bytes": path.stat().st_size,
        # Exact bytes as they sit on this machine — for local tamper detection.
        "digest": sha256_file(path),
        # Line-ending-independent — the value the cross-machine folds use.
        "content_digest": sha256_content(path),
    }


# Outputs whose content is reproducible on any machine: none of them embeds a
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
    """One digest over ``(path, content_digest)`` pairs, order-independent.

    Folds the line-ending-independent content digest, never the raw-byte one, so
    the result is identical on a Windows and a Linux checkout of the same commit.
    """
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["content_digest"].encode("utf-8"))
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
