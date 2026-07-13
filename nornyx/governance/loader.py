from __future__ import annotations

from importlib.resources.abc import Traversable
import os
from pathlib import Path
from typing import Any, Mapping
import yaml

from nornyx.parser import NornyxSafeLoader

from .errors import GovernanceError, error
from .models import (
    GovernanceBlockSchema,
    GovernanceModule,
    PackProvenance,
    PackSourceTier,
    ProfilePack,
    Rule,
    StarterFragment,
    immutable_mapping,
)
from .schemas import (
    SCHEMA_BY_DISCRIMINATOR,
    canonical_pack_hash,
    validate_governance_block_schema,
    validate_payload,
)


MAX_PACK_BYTES = 512 * 1024
MAX_YAML_DEPTH = 40
MAX_YAML_NODES = 20_000
MAX_YAML_ALIASES = 50
MAX_RULES_PER_PACK = 200
URL_PREFIXES = ("http://", "https://", "ftp://", "git://", "ssh://")


def _walk_limits(
    value: Any,
    *,
    depth: int = 0,
    code_prefix: str = "PACK",
    noun: str = "YAML",
) -> int:
    if depth > MAX_YAML_DEPTH:
        raise error(
            f"{code_prefix}_LIMIT_EXCEEDED",
            f"{noun} depth exceeds {MAX_YAML_DEPTH}.",
        )
    count = 1
    if isinstance(value, Mapping):
        for key, item in value.items():
            count += _walk_limits(
                key,
                depth=depth + 1,
                code_prefix=code_prefix,
                noun=noun,
            )
            count += _walk_limits(
                item,
                depth=depth + 1,
                code_prefix=code_prefix,
                noun=noun,
            )
    elif isinstance(value, list):
        for item in value:
            count += _walk_limits(
                item,
                depth=depth + 1,
                code_prefix=code_prefix,
                noun=noun,
            )
    if count > MAX_YAML_NODES:
        raise error(
            f"{code_prefix}_LIMIT_EXCEEDED",
            f"{noun} node count exceeds {MAX_YAML_NODES}.",
        )
    return count


def parse_bounded_yaml_mapping(
    raw: bytes,
    *,
    source_path: str,
    code_prefix: str = "PACK",
    noun: str = "Pack",
) -> dict[str, Any]:
    if len(raw) > MAX_PACK_BYTES:
        raise error(
            f"{code_prefix}_LIMIT_EXCEEDED",
            f"{noun} exceeds the {MAX_PACK_BYTES}-byte limit.",
            path=source_path,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error(
            f"{code_prefix}_ENCODING_INVALID",
            f"{noun} must be UTF-8.",
            path=source_path,
        ) from exc
    if "\x00" in text:
        raise error(
            f"{code_prefix}_ENCODING_INVALID",
            f"{noun} contains a null byte.",
            path=source_path,
        )
    try:
        alias_count = sum(
            1
            for event in yaml.parse(text, Loader=NornyxSafeLoader)
            if isinstance(event, yaml.events.AliasEvent)
        )
        if alias_count > MAX_YAML_ALIASES:
            raise error(
                f"{code_prefix}_LIMIT_EXCEEDED",
                f"YAML alias count exceeds {MAX_YAML_ALIASES}.",
                path=source_path,
            )
        payload = yaml.load(text, Loader=NornyxSafeLoader)
    except GovernanceError:
        raise
    except yaml.YAMLError as exc:
        raise error(
            f"{code_prefix}_YAML_INVALID",
            f"Invalid YAML: {exc}",
            path=source_path,
        ) from exc
    if not isinstance(payload, dict):
        raise error(
            f"{code_prefix}_TOP_LEVEL_INVALID",
            f"{noun} must contain one top-level mapping.",
            path=source_path,
        )
    _walk_limits(payload, code_prefix=code_prefix, noun="YAML")
    return payload


def _verify_integrity(payload: Mapping[str, Any], source_path: str) -> str:
    integrity = payload.get("integrity")
    if not isinstance(integrity, Mapping):
        raise error("PACK_INTEGRITY_MISSING", "Pack integrity metadata is required.", path=source_path)
    expected = integrity.get("content_hash")
    actual = canonical_pack_hash(payload)
    if expected != actual:
        raise error(
            "PACK_INTEGRITY_MISMATCH",
            f"Pack content hash mismatch: expected {expected!r}, calculated {actual!r}.",
            path=source_path,
        )
    return actual


def _check_rule_cap(rules: list[Any], *, source_path: str, pack_id: str) -> None:
    if len(rules) > MAX_RULES_PER_PACK:
        raise error(
            "PACK_LIMIT_EXCEEDED",
            f"Pack declares {len(rules)} rules; the limit is {MAX_RULES_PER_PACK}.",
            path=source_path,
            source_id=pack_id,
        )


def _profile_from_payload(
    payload: dict[str, Any],
    *,
    source_path: str,
    source_tier: PackSourceTier,
    content_hash: str,
) -> ProfilePack:
    pack_id = str(payload["id"])
    _check_rule_cap(payload["validation_rules"], source_path=source_path, pack_id=pack_id)
    if source_tier != "builtin" and pack_id.startswith("nornyx.builtin."):
        raise error(
            "PACK_RESERVED_NAMESPACE",
            "Only bundled profiles may use the nornyx.builtin namespace.",
            path=source_path,
            source_id=pack_id,
        )
    provenance = payload["provenance"]
    fragments = tuple(
        StarterFragment(
            target=str(item["target"]),
            content=item["content"],
            source_id=pack_id,
            source_index=index,
        )
        for index, item in enumerate(payload["starter_fragments"])
    )
    return ProfilePack(
        id=pack_id,
        name=str(payload["name"]),
        display_name=str(payload["display_name"]),
        version=str(payload["version"]),
        compatible_core=str(payload["compatible_core"]),
        status=str(payload["status"]),
        purpose=str(payload["purpose"]),
        domain=str(payload["domain"]),
        required_modules=tuple(str(item) for item in payload["required_modules"]),
        required_blocks=tuple(str(item) for item in payload["required_blocks"]),
        recommended_blocks=tuple(str(item) for item in payload["recommended_blocks"]),
        default_policies=tuple(immutable_mapping(item) for item in payload["default_policies"]),
        required_evidence=tuple(immutable_mapping(item) for item in payload["required_evidence"]),
        default_evaluations=tuple(immutable_mapping(item) for item in payload["default_evaluations"]),
        approval_requirements=tuple(immutable_mapping(item) for item in payload["approval_requirements"]),
        validation_rules=tuple(
            Rule.from_dict(item, source_id=pack_id) for item in payload["validation_rules"]
        ),
        conflicts=tuple(str(item) for item in payload["conflicts"]),
        non_goals=tuple(str(item) for item in payload["non_goals"]),
        starter_fragments=fragments,
        provenance=PackProvenance(
            author=str(provenance["author"]),
            source_tier=source_tier,
            source_revision=str(provenance["source_revision"]),
            source_path=source_path,
        ),
        content_hash=content_hash,
        raw=immutable_mapping(payload),
    )


def _module_from_payload(
    payload: dict[str, Any],
    *,
    source_path: str,
    source_tier: PackSourceTier,
    content_hash: str,
) -> GovernanceModule:
    pack_id = str(payload["id"])
    _check_rule_cap(payload["rules"], source_path=source_path, pack_id=pack_id)
    if source_tier != "builtin" and pack_id.startswith("nornyx.builtin."):
        raise error(
            "PACK_RESERVED_NAMESPACE",
            "Only bundled modules may use the nornyx.builtin namespace.",
            path=source_path,
            source_id=pack_id,
        )
    provenance = payload["provenance"]
    block_schemas = tuple(
        GovernanceBlockSchema(
            block=str(item["block"]),
            schema_id=str(item["schema_id"]),
            source_id=pack_id,
        )
        for item in payload.get("block_schemas", [])
    )
    for binding in block_schemas:
        validate_governance_block_schema(binding.block, binding.schema_id, source_id=pack_id)
    return GovernanceModule(
        id=pack_id,
        name=str(payload["name"]),
        version=str(payload["version"]),
        compatible_core=str(payload["compatible_core"]),
        dependencies=tuple(str(item) for item in payload["dependencies"]),
        conflicts=tuple(str(item) for item in payload["conflicts"]),
        required_blocks=tuple(str(item) for item in payload["required_blocks"]),
        block_schemas=block_schemas,
        structural_checks=tuple(str(item) for item in payload.get("structural_checks", [])),
        policies=tuple(immutable_mapping(item) for item in payload["policies"]),
        evidence_requirements=tuple(
            immutable_mapping(item) for item in payload["evidence_requirements"]
        ),
        approval_requirements=tuple(
            immutable_mapping(item) for item in payload["approval_requirements"]
        ),
        evaluations=tuple(immutable_mapping(item) for item in payload["evaluations"]),
        rules=tuple(Rule.from_dict(item, source_id=pack_id) for item in payload["rules"]),
        non_goals=tuple(str(item) for item in payload["non_goals"]),
        provenance=PackProvenance(
            author=str(provenance["author"]),
            source_tier=source_tier,
            source_revision=str(provenance["source_revision"]),
            source_path=source_path,
        ),
        content_hash=content_hash,
        raw=immutable_mapping(payload),
    )


def load_pack_bytes(
    raw: bytes,
    *,
    source_path: str,
    source_tier: PackSourceTier,
) -> ProfilePack | GovernanceModule:
    payload = parse_bounded_yaml_mapping(raw, source_path=source_path)
    discriminator = payload.get("schema")
    schema_name = SCHEMA_BY_DISCRIMINATOR.get(str(discriminator))
    if schema_name not in {"profile_pack_v1.schema.json", "governance_module_v1.schema.json"}:
        raise error(
            "PACK_SCHEMA_UNSUPPORTED",
            f"Unsupported pack schema {discriminator!r}.",
            path=source_path,
        )
    validate_payload(payload, schema_name)
    content_hash = _verify_integrity(payload, source_path)
    if discriminator == "nornyx.profile_pack.v1":
        return _profile_from_payload(
            payload,
            source_path=source_path,
            source_tier=source_tier,
            content_hash=content_hash,
        )
    return _module_from_payload(
        payload,
        source_path=source_path,
        source_tier=source_tier,
        content_hash=content_hash,
    )


def _path_contains(parent: Path, child: Path) -> bool:
    # Case- and 8.3-shortname-insensitive containment: both sides must already
    # be real paths (os.path.realpath) so the comparison is purely textual.
    parent_text = os.path.normcase(str(parent)).rstrip("\\/")
    child_text = os.path.normcase(str(child))
    return child_text == parent_text or child_text.startswith(parent_text + os.sep)


def _absolute_without_resolving(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlink_components(
    candidate: Path,
    trust_root: Path,
    *,
    code_prefix: str,
    noun: str,
) -> None:
    raw_root = _absolute_without_resolving(trust_root)
    raw_candidate = _absolute_without_resolving(candidate)
    try:
        relative = raw_candidate.relative_to(raw_root)
    except ValueError as exc:
        raise error(
            f"{code_prefix}_PATH_OUTSIDE_ROOT",
            f"{noun} path must stay inside the symlink-inspection trust root.",
            path=str(candidate),
        ) from exc

    probe = raw_root
    components = [probe]
    for name in relative.parts:
        if name == os.pardir:
            if probe == raw_root:
                raise error(
                    f"{code_prefix}_PATH_OUTSIDE_ROOT",
                    f"{noun} path must stay inside the symlink-inspection trust root.",
                    path=str(candidate),
                )
            probe = probe.parent
        else:
            probe /= name
        components.append(probe)
    for part in components:
        try:
            is_symlink = part.is_symlink()
        except OSError:
            continue
        if is_symlink:
            raise error(
                f"{code_prefix}_SYMLINK_REJECTED",
                f"Symlinked {noun.lower()} paths are not allowed.",
                path=str(candidate),
            )


def read_local_file_bytes(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    code_prefix: str,
    noun: str,
) -> tuple[bytes, Path]:
    raw_path = str(path)
    if raw_path.lower().startswith(URL_PREFIXES):
        raise error(
            f"{code_prefix}_REMOTE_SOURCE_REJECTED",
            f"Network {noun.lower()} sources are not allowed.",
            path=raw_path,
        )
    raw_root = _absolute_without_resolving(Path(allowed_root))
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = raw_root / candidate
    inspection_root = raw_root if trust_root is None else Path(trust_root)
    _reject_symlink_components(
        candidate,
        inspection_root,
        code_prefix=code_prefix,
        noun=noun,
    )
    try:
        root = Path(os.path.realpath(raw_root.resolve(strict=True)))
    except OSError as exc:
        raise error(
            f"{code_prefix}_NOT_FOUND",
            f"Permitted {noun.lower()} root does not exist.",
            path=str(raw_root),
        ) from exc
    resolved = Path(os.path.realpath(candidate))
    if not _path_contains(root, resolved):
        raise error(
            f"{code_prefix}_PATH_OUTSIDE_ROOT",
            f"{noun} path must resolve inside the explicitly permitted root.",
            path=raw_path,
        )
    if not resolved.is_file():
        raise error(
            f"{code_prefix}_NOT_FOUND",
            f"{noun} path is not a file.",
            path=str(resolved),
        )
    try:
        return resolved.read_bytes(), resolved
    except OSError as exc:
        raise error(
            f"{code_prefix}_READ_ERROR",
            f"Cannot read {noun.lower()}: {exc}",
            path=str(resolved),
        ) from exc


def load_local_pack(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    source_tier: PackSourceTier = "explicit_path",
) -> ProfilePack | GovernanceModule:
    raw, resolved = read_local_file_bytes(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix="PACK",
        noun="Pack",
    )
    return load_pack_bytes(raw, source_path=resolved.as_posix(), source_tier=source_tier)


def load_bundled_pack(resource: Traversable) -> ProfilePack | GovernanceModule:
    return load_pack_bytes(
        resource.read_bytes(),
        source_path=f"nornyx/profiles_data/{resource.name}",
        source_tier="builtin",
    )
