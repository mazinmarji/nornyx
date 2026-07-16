from __future__ import annotations

from datetime import datetime
import hashlib
from importlib import resources
import json
import re
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

from .errors import GovernanceError, error
from .models import GovernanceDiagnostic


SCHEMA_BY_DISCRIMINATOR = {
    "nornyx.profile_pack.v1": "profile_pack_v1.schema.json",
    "nornyx.governance_module.v1": "governance_module_v1.schema.json",
    "nornyx.normalized_approval.v1": "governance_approval_model_v1.schema.json",
    "nornyx.normalized_approval.v2": "governance_approval_model_v2.schema.json",
    "nornyx.effective_approval.v1": "effective_approval_v1.schema.json",
    "nornyx.effective_governance.v2": "effective_governance_v2.schema.json",
    "nornyx.profiles_lock.v1": "profiles_lock_v1.schema.json",
}

MAX_GOVERNANCE_SCHEMA_BYTES = 256 * 1024
MAX_GOVERNANCE_SCHEMA_DEPTH = 40
MAX_GOVERNANCE_SCHEMA_NODES = 20_000
MAX_GOVERNANCE_SCHEMA_REFS = 128
FORMAT_CHECKER = FormatChecker()
_OFFSET_DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


@FORMAT_CHECKER.checks("date-time", raises=(TypeError, ValueError))
def _is_offset_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if _OFFSET_DATE_TIME_RE.fullmatch(value) is None:
        return False
    normalized = value.replace("t", "T", 1)
    if normalized[-1] in {"Z", "z"}:
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    return parsed.tzinfo is not None
_ALLOWED_SCHEMA_KEYS = {
    "$schema",
    "$id",
    "$comment",
    "$defs",
    "$ref",
    "title",
    "description",
    "type",
    "const",
    "enum",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minProperties",
    "maxProperties",
    "allOf",
    "anyOf",
    "oneOf",
    "default",
    "examples",
    "readOnly",
    "x-nornyx-governance-block",
}


def load_bundled_schema(name: str) -> dict[str, Any]:
    path = resources.files("nornyx") / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def schema_registry() -> Registry:
    registry = Registry()
    schema_root = resources.files("nornyx") / "schemas"
    for entry in schema_root.iterdir():
        if not entry.name.endswith(".schema.json"):
            continue
        contents = json.loads(entry.read_text(encoding="utf-8"))
        schema_id = contents.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(contents))
    return registry


def bundled_schema_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    schema_root = resources.files("nornyx") / "schemas"
    for entry in schema_root.iterdir():
        if not entry.name.endswith(".schema.json"):
            continue
        contents = json.loads(entry.read_text(encoding="utf-8"))
        schema_id = contents.get("$id")
        if isinstance(schema_id, str):
            catalog[schema_id] = contents
    return catalog


def _schema_nodes(value: Any, *, depth: int = 0) -> Iterator[tuple[int, Any]]:
    yield depth, value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _schema_nodes(item, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _schema_nodes(item, depth=depth + 1)


def _check_schema_subset(schema: Mapping[str, Any], *, schema_id: str) -> None:
    encoded = json.dumps(schema, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_GOVERNANCE_SCHEMA_BYTES:
        raise error(
            "PACK_BLOCK_SCHEMA_LIMIT_EXCEEDED",
            f"Governance block schema {schema_id!r} exceeds the byte limit.",
        )
    nodes = list(_schema_nodes(schema))
    if len(nodes) > MAX_GOVERNANCE_SCHEMA_NODES or any(
        depth > MAX_GOVERNANCE_SCHEMA_DEPTH for depth, _ in nodes
    ):
        raise error(
            "PACK_BLOCK_SCHEMA_LIMIT_EXCEEDED",
            f"Governance block schema {schema_id!r} exceeds structural limits.",
        )

    ref_count = 0

    def visit(node: Mapping[str, Any], path: str) -> None:
        nonlocal ref_count
        unknown = sorted(set(node) - _ALLOWED_SCHEMA_KEYS)
        if unknown:
            raise error(
                "PACK_BLOCK_SCHEMA_KEYWORD_REJECTED",
                f"Governance block schema {schema_id!r} uses unsupported keyword(s): "
                f"{', '.join(unknown)}.",
                path=path,
            )
        reference = node.get("$ref")
        if reference is not None:
            ref_count += 1
            if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
                raise error(
                    "PACK_BLOCK_SCHEMA_REF_REJECTED",
                    "Governance block schemas may use only local bundled $defs references.",
                    path=path,
                )
        for container in ("properties", "$defs"):
            entries = node.get(container, {})
            if isinstance(entries, Mapping):
                for key, child in entries.items():
                    if isinstance(child, Mapping):
                        visit(child, f"{path}.{container}.{key}")
        child = node.get("items")
        if isinstance(child, Mapping):
            visit(child, f"{path}.items")
        child = node.get("additionalProperties")
        if isinstance(child, Mapping):
            visit(child, f"{path}.additionalProperties")
        for container in ("allOf", "anyOf", "oneOf"):
            entries = node.get(container, [])
            if isinstance(entries, list):
                for index, child in enumerate(entries):
                    if isinstance(child, Mapping):
                        visit(child, f"{path}.{container}[{index}]")

    visit(schema, schema_id)
    if ref_count > MAX_GOVERNANCE_SCHEMA_REFS:
        raise error(
            "PACK_BLOCK_SCHEMA_LIMIT_EXCEEDED",
            f"Governance block schema {schema_id!r} exceeds the reference limit.",
        )

    definitions = schema.get("$defs", {})
    definition_names = (
        {str(name) for name in definitions}
        if isinstance(definitions, Mapping)
        else set()
    )
    reference_graph: dict[str, set[str]] = {
        name: set() for name in definition_names
    }
    for owner, value in (
        definitions.items() if isinstance(definitions, Mapping) else ()
    ):
        for _, node in _schema_nodes(value):
            if not isinstance(node, Mapping) or not isinstance(node.get("$ref"), str):
                continue
            target = str(node["$ref"]).removeprefix("#/$defs/")
            if target not in definition_names:
                raise error(
                    "PACK_BLOCK_SCHEMA_REF_REJECTED",
                    f"Governance block schema {schema_id!r} references missing "
                    f"local definition {target!r}.",
                )
            reference_graph[str(owner)].add(target)

    # Root-level references are not graph vertices, but still must resolve to
    # one reviewed local definition.
    for _, node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("$ref"), str):
            continue
        target = str(node["$ref"]).removeprefix("#/$defs/")
        if target not in definition_names:
            raise error(
                "PACK_BLOCK_SCHEMA_REF_REJECTED",
                f"Governance block schema {schema_id!r} references missing "
                f"local definition {target!r}.",
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_references(name: str) -> None:
        if name in visiting:
            raise error(
                "PACK_BLOCK_SCHEMA_REF_CYCLE",
                f"Governance block schema {schema_id!r} contains a local $ref cycle.",
            )
        if name in visited:
            return
        visiting.add(name)
        for target in sorted(reference_graph[name]):
            visit_references(target)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(reference_graph):
        visit_references(name)


def validate_governance_block_schema(
    block: str,
    schema_id: str,
    *,
    source_id: str | None = None,
) -> None:
    schema = bundled_schema_catalog().get(schema_id)
    if schema is None or schema.get("x-nornyx-governance-block") != block:
        raise error(
            "PACK_BLOCK_SCHEMA_UNAVAILABLE",
            f"Block {block!r} must reference a matching bundled governance schema.",
            source_id=source_id,
        )
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise error(
            "PACK_BLOCK_SCHEMA_INVALID",
            f"Bundled governance schema {schema_id!r} is invalid: {exc}",
            source_id=source_id,
        ) from exc
    _check_schema_subset(schema, schema_id=schema_id)


def validate_governance_block(
    block: str,
    value: Any,
    schema_id: str,
    *,
    source_id: str,
) -> tuple[GovernanceDiagnostic, ...]:
    validate_governance_block_schema(block, schema_id, source_id=source_id)
    schema = bundled_schema_catalog()[schema_id]
    validator = Draft202012Validator(
        schema,
        registry=schema_registry(),
        format_checker=FORMAT_CHECKER,
    )
    diagnostics = []
    for item in sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path)):
        suffix = ".".join(str(part) for part in item.absolute_path)
        diagnostics.append(
            GovernanceDiagnostic(
                "error",
                "GOVERNANCE_BLOCK_SCHEMA_INVALID",
                item.message,
                path=f"{block}.{suffix}" if suffix else block,
                source_id=source_id,
            )
        )
    return tuple(diagnostics)


def validate_payload(payload: Mapping[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(
        load_bundled_schema(schema_name),
        registry=schema_registry(),
        format_checker=FORMAT_CHECKER,
    )
    errors = sorted(validator.iter_errors(dict(payload)), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    diagnostics = []
    for item in errors:
        path = ".".join(str(part) for part in item.absolute_path) or None
        diagnostics.append(
            GovernanceDiagnostic(
                "error",
                "PACK_SCHEMA_INVALID",
                item.message,
                path=path,
            )
        )
    raise GovernanceError(*diagnostics)


def canonical_pack_bytes(payload: Mapping[str, Any]) -> bytes:
    body = dict(payload)
    body.pop("integrity", None)
    return json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_pack_hash(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_pack_bytes(payload)).hexdigest()
