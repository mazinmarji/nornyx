from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING, Any, Mapping
import yaml

if TYPE_CHECKING:
    # `importlib.resources.abc` exists only on Python 3.11+. `Traversable` is
    # used purely as a type annotation here and (with `from __future__ import
    # annotations`) is never evaluated at runtime, so guarding the import keeps
    # the package importable on the advertised Python 3.10 floor.
    from importlib.resources.abc import Traversable

from nornyx.path_security import is_remote_or_device_path
from nornyx.parser import NornyxSafeLoader

from .approvals import normalize_approval
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


def _reserved_builtin_identity(pack_id: str) -> bool:
    return pack_id == "nornyx.builtin" or pack_id.startswith("nornyx.builtin.")


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
    if source_tier != "builtin" and _reserved_builtin_identity(pack_id):
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
            author=provenance["author"],
            source_tier=source_tier,
            source_revision=provenance["source_revision"],
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
    if source_tier != "builtin" and _reserved_builtin_identity(pack_id):
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
            author=provenance["author"],
            source_tier=source_tier,
            source_revision=provenance["source_revision"],
            source_path=source_path,
        ),
        content_hash=content_hash,
        raw=immutable_mapping(payload),
    )


def _load_pack_bytes(
    raw: bytes,
    *,
    source_path: str,
    source_tier: PackSourceTier,
    allow_builtin: bool,
) -> ProfilePack | GovernanceModule:
    if source_tier == "builtin" and not allow_builtin:
        raise error(
            "PACK_SOURCE_TIER_INVALID",
            "The builtin source tier is reserved for packaged Nornyx resources.",
            path=source_path,
        )
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
    for index, approval in enumerate(payload.get("approval_requirements", [])):
        normalized = normalize_approval(
            approval,
            shape="generated_profile_approval",
            path=f"{payload['id']}.approval_requirements[{index}]",
            fallback_id=(
                approval["id"]
                if isinstance(approval, Mapping)
                and isinstance(approval.get("id"), str)
                else f"approval-{index}"
            ),
        )
        blocking_codes = {
            "APPROVAL_ACCOUNTABLE_AUTHORITY_INVALID",
            "APPROVAL_NON_HUMAN_AUTHORITY",
        }
        if blocking_codes & {item.code for item in normalized.diagnostics}:
            raise GovernanceError(*normalized.diagnostics)
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


def load_pack_bytes(
    raw: bytes,
    *,
    source_path: str,
    source_tier: PackSourceTier,
) -> ProfilePack | GovernanceModule:
    """Load caller-supplied bytes without granting bundled-resource authority."""

    return _load_pack_bytes(
        raw,
        source_path=source_path,
        source_tier=source_tier,
        allow_builtin=False,
    )


def _path_contains(parent: Path, child: Path) -> bool:
    # Case- and 8.3-shortname-insensitive containment: both sides must already
    # be real paths (os.path.realpath) so the comparison is purely textual.
    parent_text = os.path.normcase(str(parent)).rstrip("\\/")
    child_text = os.path.normcase(str(child))
    return child_text == parent_text or child_text.startswith(parent_text + os.sep)


def _absolute_without_resolving(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def reject_remote_or_device_path(
    path: str | Path,
    *,
    code_prefix: str,
    noun: str,
) -> None:
    if is_remote_or_device_path(path):
        raise error(
            f"{code_prefix}_REMOTE_SOURCE_REJECTED",
            f"Remote or device-backed {noun.lower()} paths are not allowed.",
            path=str(path),
        )


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _inspect_unresolved_components(
    path: Path,
    *,
    code_prefix: str,
    noun: str,
) -> None:
    """Inspect every lexical component with lstat, preserving ``..`` walks."""

    candidate = _absolute_without_resolving(path)
    anchor = Path(candidate.anchor) if candidate.anchor else Path.cwd()
    try:
        relative = candidate.relative_to(anchor)
    except ValueError as exc:
        raise error(
            f"{code_prefix}_PATH_INSPECTION_FAILED",
            f"Cannot derive a local inspection anchor for the {noun.lower()} path.",
            path=str(path),
        ) from exc

    probe = anchor
    components = [probe]
    for component in relative.parts:
        if component in {"", os.curdir}:
            continue
        probe = probe.parent if component == os.pardir else probe / component
        components.append(probe)

    for component in components:
        try:
            metadata = os.lstat(component)
        except FileNotFoundError:
            # A dangling link is visible to lstat. A genuinely missing path is
            # handled by the final type check, while later ``..`` components
            # still need inspection.
            continue
        except OSError as exc:
            raise error(
                f"{code_prefix}_PATH_INSPECTION_FAILED",
                f"Cannot inspect the {noun.lower()} path: {exc}",
                path=str(path),
            ) from exc
        if _is_link_or_reparse(metadata):
            raise error(
                f"{code_prefix}_SYMLINK_REJECTED",
                f"Symlinked or reparse-point {noun.lower()} paths are not allowed.",
                path=str(path),
            )


def _require_lexical_containment(
    root: Path,
    candidate: Path,
    *,
    code_prefix: str,
    noun: str,
) -> None:
    raw_root = _absolute_without_resolving(root)
    raw_candidate = _absolute_without_resolving(candidate)
    try:
        relative = raw_candidate.relative_to(raw_root)
    except ValueError as exc:
        raise error(
            f"{code_prefix}_PATH_OUTSIDE_ROOT",
            f"{noun} path must stay inside the explicitly permitted root.",
            path=str(candidate),
        ) from exc

    depth = 0
    for component in relative.parts:
        if component in {"", os.curdir}:
            continue
        if component == os.pardir:
            if depth == 0:
                raise error(
                    f"{code_prefix}_PATH_OUTSIDE_ROOT",
                    f"{noun} path must not traverse outside the explicitly permitted root.",
                    path=str(candidate),
                )
            depth -= 1
        else:
            depth += 1


def _reject_symlink_components(
    candidate: Path,
    trust_root: Path,
    *,
    code_prefix: str,
    noun: str,
) -> None:
    reject_remote_or_device_path(candidate, code_prefix=code_prefix, noun=noun)
    reject_remote_or_device_path(trust_root, code_prefix=code_prefix, noun=noun)
    raw_root = _absolute_without_resolving(trust_root)
    raw_candidate = _absolute_without_resolving(candidate)
    _inspect_unresolved_components(raw_root, code_prefix=code_prefix, noun=noun)
    _inspect_unresolved_components(raw_candidate, code_prefix=code_prefix, noun=noun)
    _require_lexical_containment(
        raw_root,
        raw_candidate,
        code_prefix=code_prefix,
        noun=noun,
    )


def _prepare_local_candidate(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None,
    code_prefix: str,
    noun: str,
) -> tuple[Path, Path, Path]:
    for boundary in (path, allowed_root, trust_root):
        if boundary is not None:
            reject_remote_or_device_path(
                boundary,
                code_prefix=code_prefix,
                noun=noun,
            )

    raw_root = _absolute_without_resolving(Path(allowed_root))
    supplied = Path(path)
    candidate = supplied if supplied.is_absolute() else raw_root / supplied
    candidate = _absolute_without_resolving(candidate)

    _inspect_unresolved_components(raw_root, code_prefix=code_prefix, noun=noun)
    _inspect_unresolved_components(candidate, code_prefix=code_prefix, noun=noun)
    _require_lexical_containment(
        raw_root,
        candidate,
        code_prefix=code_prefix,
        noun=noun,
    )
    if trust_root is not None:
        raw_trust_root = _absolute_without_resolving(Path(trust_root))
        _inspect_unresolved_components(
            raw_trust_root,
            code_prefix=code_prefix,
            noun=noun,
        )
        _require_lexical_containment(
            raw_trust_root,
            raw_root,
            code_prefix=code_prefix,
            noun=noun,
        )
        _require_lexical_containment(
            raw_trust_root,
            candidate,
            code_prefix=code_prefix,
            noun=noun,
        )

    try:
        root_metadata = os.lstat(raw_root)
    except FileNotFoundError as exc:
        raise error(
            f"{code_prefix}_NOT_FOUND",
            f"Permitted {noun.lower()} root does not exist.",
            path=str(raw_root),
        ) from exc
    except OSError as exc:
        raise error(
            f"{code_prefix}_PATH_INSPECTION_FAILED",
            f"Cannot inspect the permitted {noun.lower()} root: {exc}",
            path=str(raw_root),
        ) from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise error(
            f"{code_prefix}_PATH_TYPE_INVALID",
            f"Permitted {noun.lower()} root must be a directory.",
            path=str(raw_root),
        )

    resolved_root = Path(os.path.realpath(raw_root))
    resolved_candidate = Path(os.path.realpath(candidate))
    if not _path_contains(resolved_root, resolved_candidate):
        raise error(
            f"{code_prefix}_PATH_OUTSIDE_ROOT",
            f"{noun} path must resolve inside the explicitly permitted root.",
            path=str(path),
        )
    return candidate, resolved_candidate, resolved_root


def inspect_local_file(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    code_prefix: str,
    noun: str,
    allow_missing: bool = False,
) -> Path | None:
    candidate, resolved, _ = _prepare_local_candidate(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix=code_prefix,
        noun=noun,
    )
    try:
        metadata = os.lstat(candidate)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise error(
            f"{code_prefix}_NOT_FOUND",
            f"{noun} path is not a file.",
            path=str(candidate),
        ) from None
    except OSError as exc:
        raise error(
            f"{code_prefix}_PATH_INSPECTION_FAILED",
            f"Cannot inspect the {noun.lower()} path: {exc}",
            path=str(candidate),
        ) from exc
    if _is_link_or_reparse(metadata):
        raise error(
            f"{code_prefix}_SYMLINK_REJECTED",
            f"Symlinked or reparse-point {noun.lower()} paths are not allowed.",
            path=str(candidate),
        )
    if not stat.S_ISREG(metadata.st_mode):
        raise error(
            f"{code_prefix}_PATH_TYPE_INVALID",
            f"{noun} path must be a regular file.",
            path=str(candidate),
        )
    return resolved


def inspect_local_directory(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    code_prefix: str,
    noun: str,
    allow_missing: bool = False,
) -> Path | None:
    candidate, resolved, _ = _prepare_local_candidate(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix=code_prefix,
        noun=noun,
    )
    try:
        metadata = os.lstat(candidate)
    except FileNotFoundError:
        if allow_missing:
            return None
        raise error(
            f"{code_prefix}_NOT_FOUND",
            f"{noun} directory does not exist.",
            path=str(candidate),
        ) from None
    except OSError as exc:
        raise error(
            f"{code_prefix}_PATH_INSPECTION_FAILED",
            f"Cannot inspect the {noun.lower()} directory: {exc}",
            path=str(candidate),
        ) from exc
    if _is_link_or_reparse(metadata):
        raise error(
            f"{code_prefix}_SYMLINK_REJECTED",
            f"Symlinked or reparse-point {noun.lower()} paths are not allowed.",
            path=str(candidate),
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise error(
            f"{code_prefix}_PATH_TYPE_INVALID",
            f"{noun} path must be a directory.",
            path=str(candidate),
        )
    return resolved


def read_local_file_bytes(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    code_prefix: str,
    noun: str,
    max_bytes: int | None = None,
) -> tuple[bytes, Path]:
    resolved = inspect_local_file(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix=code_prefix,
        noun=noun,
    )
    assert resolved is not None
    try:
        with resolved.open("rb") as stream:
            raw = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
    except OSError as exc:
        raise error(
            f"{code_prefix}_READ_ERROR",
            f"Cannot read {noun.lower()}: {exc}",
            path=str(resolved),
        ) from exc
    if max_bytes is not None and len(raw) > max_bytes:
        raise error(
            f"{code_prefix}_LIMIT_EXCEEDED",
            f"{noun} exceeds the {max_bytes}-byte limit.",
            path=str(resolved),
        )
    return raw, resolved


def load_local_pack(
    path: str | Path,
    *,
    allowed_root: str | Path,
    trust_root: str | Path | None = None,
    source_tier: PackSourceTier = "explicit_path",
) -> ProfilePack | GovernanceModule:
    if source_tier == "builtin":
        raise error(
            "PACK_SOURCE_TIER_INVALID",
            "Local pack sources cannot claim the builtin source tier.",
            path=str(path),
        )
    raw, resolved = read_local_file_bytes(
        path,
        allowed_root=allowed_root,
        trust_root=trust_root,
        code_prefix="PACK",
        noun="Pack",
        max_bytes=MAX_PACK_BYTES,
    )
    return load_pack_bytes(raw, source_path=resolved.as_posix(), source_tier=source_tier)


_BUNDLED_RESOURCE_CAPABILITY = object()


def _load_bundled_pack(
    resource: Traversable,
    *,
    capability: object,
) -> ProfilePack | GovernanceModule:
    if capability is not _BUNDLED_RESOURCE_CAPABILITY:
        raise error(
            "PACK_SOURCE_TIER_INVALID",
            "Bundled pack loading is restricted to the packaged catalog.",
            path=str(getattr(resource, "name", "<resource>")),
        )
    return _load_pack_bytes(
        resource.read_bytes(),
        source_path=f"nornyx/profiles_data/{resource.name}",
        source_tier="builtin",
        allow_builtin=True,
    )
