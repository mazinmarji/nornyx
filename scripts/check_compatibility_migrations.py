from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import difflib
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nornyx.cli import main as cli_main  # noqa: E402


DEFAULT_MANIFEST = (
    ROOT / "tests" / "fixtures" / "governance_compatibility" / "manifest.json"
)
MIGRATION_ROOT = DEFAULT_MANIFEST.parent / "migrations"


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _pointer(path: str, key: str | int) -> str:
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"


def json_operations(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    if isinstance(before, dict) and isinstance(after, dict):
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            operations.append(
                {"op": "remove", "path": _pointer(path, key), "old": before[key]}
            )
        for key in sorted(after_keys - before_keys):
            operations.append(
                {"op": "add", "path": _pointer(path, key), "value": after[key]}
            )
        for key in sorted(before_keys & after_keys):
            operations.extend(
                json_operations(before[key], after[key], _pointer(path, key))
            )
        return operations
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for index, (before_item, after_item) in enumerate(zip(before, after)):
            operations.extend(
                json_operations(
                    before_item,
                    after_item,
                    _pointer(path, index),
                )
            )
        return operations
    if before != after:
        operations.append({"op": "replace", "path": path, "old": before, "value": after})
    return operations


def text_diff(before: str, after: str, migration_id: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"{migration_id}.before",
            tofile=f"{migration_id}.after",
        )
    )


def _contained_artifact(raw_path: str) -> Path:
    path = ROOT / raw_path
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(MIGRATION_ROOT.resolve(strict=True))
    except ValueError as exc:
        raise AssertionError(f"migration artifact escapes corpus: {raw_path}") from exc
    return resolved


def _sanitize(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(ROOT.as_posix(), "<ROOT>").replace(str(ROOT), "<ROOT>")
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    return value


def _current_target_bytes(manifest: dict[str, Any], target: str) -> bytes:
    if target.startswith("cli:"):
        case_id = target.removeprefix("cli:")
        case = next(item for item in manifest["cli"]["cases"] if item["id"] == case_id)
        output = StringIO()
        with redirect_stdout(output):
            exit_code = cli_main(case["argv"])
        assert exit_code == case["exit"], target
        return _canonical_json(_sanitize(json.loads(output.getvalue())))
    if target.startswith("nyx_examples:"):
        relative = target.removeprefix("nyx_examples:")
        return (ROOT / relative).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    raise AssertionError(f"unknown migration target: {target}")


def verify_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    migrations = manifest["intentional_migrations"]
    referenced: set[Path] = set()
    chains: dict[str, list[dict[str, Any]]] = {}

    for migration in migrations:
        assert migration["classification"] == "intentional_migration_requiring_approval"
        assert migration["reason"] and migration["approval"]
        assert migration["changelog"] and migration["changelog_marker"]
        changelog = ROOT / migration["changelog"]
        assert migration["changelog_marker"] in changelog.read_text(encoding="utf-8")

        before_path = _contained_artifact(migration["before_artifact"])
        after_path = _contained_artifact(migration["after_artifact"])
        proof_path = _contained_artifact(migration["expected_diff_artifact"])
        referenced.update((before_path, after_path, proof_path))
        before = before_path.read_bytes()
        after = after_path.read_bytes()
        proof_raw = proof_path.read_bytes()
        assert _sha256(before) == migration["old_hash"]
        assert _sha256(after) == migration["new_hash"]
        assert _sha256(proof_raw) == migration["proof_hash"]

        if migration["artifact_kind"] == "canonical_json":
            before_value = json.loads(before)
            after_value = json.loads(after)
            assert before == _canonical_json(before_value)
            assert after == _canonical_json(after_value)
            expected_change: dict[str, Any] = {
                "operations": json_operations(before_value, after_value)
            }
        elif migration["artifact_kind"] == "canonical_lf_text":
            assert b"\r" not in before and b"\r" not in after
            expected_change = {
                "unified_diff": text_diff(
                    before.decode("utf-8"),
                    after.decode("utf-8"),
                    migration["id"],
                )
            }
        else:
            raise AssertionError(f"unknown artifact kind: {migration['artifact_kind']}")

        proof = json.loads(proof_raw)
        assert proof_raw == _canonical_json(proof)
        bound_record = dict(migration)
        bound_record.pop("proof_hash")
        assert proof == {
            "schema": "nornyx.intentional_migration_proof.v1",
            "migration": bound_record,
            **expected_change,
        }
        assert expected_change.get("operations") or expected_change.get("unified_diff")
        chains.setdefault(migration["target"], []).append(migration)

    actual = {item.resolve() for item in MIGRATION_ROOT.iterdir() if item.is_file()}
    assert actual == referenced, "migration corpus contains unbound or missing artifacts"

    for target, chain in chains.items():
        ordered = sorted(chain, key=lambda item: item["sequence"])
        assert [item["sequence"] for item in ordered] == list(range(1, len(ordered) + 1))
        for previous, current in zip(ordered, ordered[1:]):
            assert previous["new_hash"] == current["old_hash"], target
            assert previous["after_artifact"] == current["before_artifact"], target
        current = _current_target_bytes(manifest, target)
        assert _sha256(current) == ordered[-1]["new_hash"], target

    for addition in manifest["profile_starters"]["additions"]:
        raw = (ROOT / addition["artifact"]).read_bytes()
        assert _sha256(raw) == addition["new_hash"]
        assert addition["reason"] and addition["approval"]
        assert addition["changelog_marker"] in (
            ROOT / addition["changelog"]
        ).read_text(encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify approved compatibility migrations.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    manifest = verify_manifest(args.manifest.resolve(strict=True))
    print(json.dumps({"status": "pass", "migrations": len(manifest["intentional_migrations"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
