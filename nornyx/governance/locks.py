from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat
from typing import Iterable

from .errors import GovernanceError, error
from .loader import (
    MAX_PACK_BYTES,
    _absolute_without_resolving,
    _inspect_unresolved_components,
    _is_link_or_reparse,
    _require_lexical_containment,
    read_local_file_bytes,
    reject_remote_or_device_path,
)
from .models import GovernanceModule, LockEntry, ProfileLock, ProfilePack
from .schemas import validate_payload


Pack = ProfilePack | GovernanceModule


class GovernanceLockError(GovernanceError):
    """A lock-context failure whose diagnostics retain their stable codes."""


class _DuplicateJSONKey(ValueError):
    pass


class _NonFiniteJSONConstant(ValueError):
    pass


def _raise_as_lock_error(exc: GovernanceError) -> GovernanceLockError:
    if isinstance(exc, GovernanceLockError):
        return exc
    return GovernanceLockError(*exc.diagnostics)


def _reject_pack_identity_collisions(packs: tuple[Pack, ...]) -> None:
    ids: dict[str, list[Pack]] = {}
    tokens: dict[str, list[Pack]] = {}
    for pack in packs:
        ids.setdefault(pack.id, []).append(pack)
        for token in {pack.id, pack.name}:
            tokens.setdefault(token, []).append(pack)
    duplicate_ids = sorted(pack_id for pack_id, owners in ids.items() if len(owners) > 1)
    if duplicate_ids:
        identity = duplicate_ids[0]
        raise error(
            "PACK_LOCK_DUPLICATE_ID",
            f"Selected packs list {identity!r} more than once.",
            source_id=identity,
        )
    ambiguous = sorted(token for token, owners in tokens.items() if len(owners) > 1)
    if ambiguous:
        raise error(
            "PACK_DUPLICATE_IDENTITY",
            f"Selected pack identities collide on tokens {ambiguous!r}.",
        )


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
    selected = tuple(packs)
    _reject_pack_identity_collisions(selected)
    entries = tuple(
        LockEntry(
            id=pack.id,
            version=pack.version,
            source_tier=pack.provenance.source_tier,
            content_hash=pack.content_hash,
            path_hint=pack.provenance.source_path,
        )
        for pack in sorted(selected, key=lambda item: item.id)
    )
    _reject_duplicate_entries(entries)
    lock = ProfileLock(entries)
    validate_payload(lock.to_dict(), "profiles_lock_v1.schema.json")
    return lock


def load_lock(
    path: str | Path,
    *,
    allowed_root: str | Path | None = None,
    trust_root: str | Path | None = None,
) -> ProfileLock:
    reject_remote_or_device_path(path, code_prefix="PACK", noun="Profile lock")
    supplied = Path(path)
    lock_path = _absolute_without_resolving(supplied)
    permitted_root = lock_path.parent if allowed_root is None else allowed_root
    try:
        raw, resolved = read_local_file_bytes(
            lock_path,
            allowed_root=permitted_root,
            trust_root=trust_root,
            code_prefix="PACK",
            noun="Profile lock",
            max_bytes=MAX_PACK_BYTES,
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise error(
                "PACK_ENCODING_INVALID",
                "Profile lock must be UTF-8.",
                path=str(resolved),
            ) from exc
        if "\x00" in text:
            raise error(
                "PACK_ENCODING_INVALID",
                "Profile lock contains a null byte.",
                path=str(resolved),
            )

        def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise _DuplicateJSONKey(key)
                result[key] = value
            return result

        def reject_constant(value: str) -> object:
            raise _NonFiniteJSONConstant(value)

        try:
            payload = json.loads(
                text,
                object_pairs_hook=object_pairs,
                parse_constant=reject_constant,
            )
        except _DuplicateJSONKey as exc:
            raise error(
                "PACK_LOCK_DUPLICATE_KEY",
                f"Profile lock repeats JSON key {exc.args[0]!r}.",
                path=str(resolved),
            ) from exc
        except (_NonFiniteJSONConstant, json.JSONDecodeError) as exc:
            raise error(
                "PACK_LOCK_INVALID",
                f"Cannot parse profile lock JSON: {exc}",
                path=str(resolved),
            ) from exc
        if not isinstance(payload, dict):
            raise error(
                "PACK_LOCK_INVALID",
                "Profile lock must contain one top-level JSON object.",
                path=str(resolved),
            )
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
        _reject_duplicate_entries(entries, path=str(resolved))
        return ProfileLock(entries)
    except GovernanceError as exc:
        raise _raise_as_lock_error(exc) from exc


def _prepare_lock_output(
    path: str | Path,
    *,
    allowed_root: str | Path | None,
    trust_root: str | Path | None,
) -> Path:
    for boundary in (path, allowed_root, trust_root):
        if boundary is not None:
            reject_remote_or_device_path(
                boundary,
                code_prefix="PACK",
                noun="Profile lock",
            )
    target = _absolute_without_resolving(Path(path))
    root = (
        target.parent
        if allowed_root is None
        else _absolute_without_resolving(Path(allowed_root))
    )
    _inspect_unresolved_components(root, code_prefix="PACK", noun="Profile lock")
    _inspect_unresolved_components(target, code_prefix="PACK", noun="Profile lock")
    _require_lexical_containment(
        root,
        target,
        code_prefix="PACK",
        noun="Profile lock",
    )
    if trust_root is not None:
        trust = _absolute_without_resolving(Path(trust_root))
        _inspect_unresolved_components(
            trust,
            code_prefix="PACK",
            noun="Profile lock",
        )
        _require_lexical_containment(
            trust,
            root,
            code_prefix="PACK",
            noun="Profile lock",
        )
        _require_lexical_containment(
            trust,
            target,
            code_prefix="PACK",
            noun="Profile lock",
        )

    ancestor = target.parent
    while True:
        try:
            metadata = os.lstat(ancestor)
        except FileNotFoundError:
            parent = ancestor.parent
            if parent == ancestor:
                raise error(
                    "PACK_PATH_INSPECTION_FAILED",
                    "Cannot find an existing local ancestor for the profile lock.",
                    path=str(target),
                ) from None
            ancestor = parent
            continue
        except OSError as exc:
            raise error(
                "PACK_PATH_INSPECTION_FAILED",
                f"Cannot inspect the profile lock parent: {exc}",
                path=str(target),
            ) from exc
        if _is_link_or_reparse(metadata):
            raise error(
                "PACK_SYMLINK_REJECTED",
                "Symlinked or reparse-point profile lock parents are not allowed.",
                path=str(target),
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise error(
                "PACK_PATH_TYPE_INVALID",
                "Profile lock parent must be a directory.",
                path=str(ancestor),
            )
        break

    try:
        metadata = os.lstat(target)
    except FileNotFoundError:
        return target
    except OSError as exc:
        raise error(
            "PACK_PATH_INSPECTION_FAILED",
            f"Cannot inspect the profile lock output: {exc}",
            path=str(target),
        ) from exc
    if _is_link_or_reparse(metadata):
        raise error(
            "PACK_SYMLINK_REJECTED",
            "Refusing to overwrite a symlinked or reparse-point profile lock.",
            path=str(target),
        )
    if not stat.S_ISREG(metadata.st_mode):
        raise error(
            "PACK_PATH_TYPE_INVALID",
            "Profile lock output must be a regular file.",
            path=str(target),
        )
    return target


def write_lock(
    path: str | Path,
    lock: ProfileLock,
    *,
    allowed_root: str | Path | None = None,
    trust_root: str | Path | None = None,
) -> Path:
    supplied_target = Path(path)
    target = _prepare_lock_output(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
    )
    payload = lock.to_dict()
    _reject_duplicate_entries(lock.resolved, path=str(path))
    validate_payload(payload, "profiles_lock_v1.schema.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _prepare_lock_output(
        target,
        allowed_root=allowed_root,
        trust_root=trust_root,
    )
    try:
        existing_mode = stat.S_IMODE(os.lstat(target).st_mode)
    except FileNotFoundError:
        existing_mode = None
    except OSError as exc:
        raise error(
            "PACK_PATH_INSPECTION_FAILED",
            f"Cannot inspect the profile lock output mode: {exc}",
            path=str(target),
        ) from exc
    if existing_mode is not None and existing_mode & 0o222 == 0:
        raise error(
            "PACK_WRITE_ERROR",
            "Cannot overwrite a read-only profile lock.",
            path=str(target),
        )
    content = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor = -1
    temporary: Path | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        for _ in range(100):
            candidate = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(candidate, flags, 0o666)
            except FileExistsError:
                continue
            temporary = candidate
            break
        if temporary is None:
            raise OSError("cannot allocate a unique same-directory lock temporary")
        if existing_mode is not None:
            os.chmod(temporary, existing_mode)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            if temporary is not None:
                os.unlink(temporary)
        except OSError:
            pass
        raise error(
            "PACK_WRITE_ERROR",
            f"Cannot write profile lock: {exc}",
            path=str(target),
        ) from exc
    return supplied_target


def verify_lock(lock: ProfileLock, packs: Iterable[Pack]) -> None:
    _reject_duplicate_entries(lock.resolved)
    selected = tuple(packs)
    _reject_pack_identity_collisions(selected)
    expected = {entry.id: entry for entry in lock.resolved}
    actual = {pack.id: pack for pack in selected}
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
