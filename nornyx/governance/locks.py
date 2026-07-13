from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .errors import GovernanceError, error
from .models import GovernanceModule, LockEntry, ProfileLock, ProfilePack
from .schemas import validate_payload


Pack = ProfilePack | GovernanceModule


def _reject_duplicate_entries(entries: tuple[LockEntry, ...], *, path: str | None = None) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            raise error(
                "PACK_LOCK_DUPLICATE_ID",
                f"Profile lock lists {entry.id!r} more than once.",
                path=path,
                source_id=entry.id,
            )
        seen.add(entry.id)


def lock_for_packs(packs: Iterable[Pack]) -> ProfileLock:
    entries = tuple(
        LockEntry(
            id=pack.id,
            version=pack.version,
            source_tier=pack.provenance.source_tier,
            content_hash=pack.content_hash,
            path_hint=pack.provenance.source_path,
        )
        for pack in sorted(packs, key=lambda item: item.id)
    )
    lock = ProfileLock(entries)
    validate_payload(lock.to_dict(), "profiles_lock_v1.schema.json")
    return lock


def load_lock(path: str | Path) -> ProfileLock:
    lock_path = Path(path)
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise error("PACK_LOCK_INVALID", f"Cannot read profile lock: {exc}", path=str(path)) from exc
    validate_payload(payload, "profiles_lock_v1.schema.json")
    entries = tuple(
        LockEntry(
            id=str(item["id"]),
            version=str(item["version"]),
            source_tier=item["source_tier"],
            content_hash=str(item["content_hash"]),
            path_hint=str(item["path_hint"]),
        )
        for item in payload["resolved"]
    )
    _reject_duplicate_entries(entries, path=str(path))
    return ProfileLock(entries)


def write_lock(path: str | Path, lock: ProfileLock) -> Path:
    payload = lock.to_dict()
    validate_payload(payload, "profiles_lock_v1.schema.json")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def verify_lock(lock: ProfileLock, packs: Iterable[Pack]) -> None:
    _reject_duplicate_entries(lock.resolved)
    expected = {entry.id: entry for entry in lock.resolved}
    actual = {pack.id: pack for pack in packs}
    if set(expected) != set(actual):
        missing = sorted(set(actual) - set(expected))
        stale = sorted(set(expected) - set(actual))
        raise error(
            "PACK_LOCK_SET_MISMATCH",
            f"Lock selection differs; missing={missing}, stale={stale}.",
        )
    diagnostics = []
    for pack_id in sorted(actual):
        entry = expected[pack_id]
        pack = actual[pack_id]
        for field, locked, resolved in (
            ("version", entry.version, pack.version),
            ("source_tier", entry.source_tier, pack.provenance.source_tier),
            ("content_hash", entry.content_hash, pack.content_hash),
        ):
            if locked != resolved:
                diagnostics.append(
                    error(
                        "PACK_LOCK_MISMATCH",
                        f"{pack_id} {field} mismatch: lock={locked!r}, resolved={resolved!r}.",
                        source_id=pack_id,
                    ).diagnostics[0]
                )
    if diagnostics:
        raise GovernanceError(*diagnostics)
