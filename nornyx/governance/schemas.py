from __future__ import annotations

import hashlib
from importlib import resources
import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .errors import GovernanceError
from .models import GovernanceDiagnostic


SCHEMA_BY_DISCRIMINATOR = {
    "nornyx.profile_pack.v1": "profile_pack_v1.schema.json",
    "nornyx.governance_module.v1": "governance_module_v1.schema.json",
    "nornyx.normalized_approval.v1": "governance_approval_model_v1.schema.json",
    "nornyx.profiles_lock.v1": "profiles_lock_v1.schema.json",
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


def validate_payload(payload: Mapping[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_bundled_schema(schema_name), registry=schema_registry())
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
