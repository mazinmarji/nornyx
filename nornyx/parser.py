from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import yaml

from .path_security import is_remote_or_device_path


class NornyxParseError(Exception):
    pass


class NornyxSafeLoader(yaml.SafeLoader):
    """SafeLoader that does not coerce YAML 1.1 booleans on/off/yes/no.

    Plain YAML treats on/off/yes/no/y/n as booleans, so a harness step like
    `- on: test_failure` parses as `{True: "test_failure"}` and the `on` key is
    lost. Nornyx uses `on:` as a real key (repair conditions, etc.), so we
    restrict implicit bool resolution to true/false only.
    """


# Drop the bool resolver everywhere, then re-add it for true/false only.
NornyxSafeLoader.yaml_implicit_resolvers = {
    ch: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_BOOL_RE = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
for _ch in "tTfF":
    NornyxSafeLoader.yaml_implicit_resolvers.setdefault(_ch, []).append(
        ("tag:yaml.org,2002:bool", _BOOL_RE)
    )


def load_nyx(path: str | Path) -> dict[str, Any]:
    """Load a v0.1 .nyx file.

    v0.1 intentionally uses a YAML-compatible syntax so the first implementation
    can focus on semantics: context, agents, policy, harness, evals, evidence.
    A future parser can replace this without changing the high-level model.
    """
    if is_remote_or_device_path(path):
        raise NornyxParseError(
            f"remote or device-backed contract paths are not allowed: {path}"
        )
    p = Path(path)
    if not p.exists():
        raise NornyxParseError(f"contract file not found: {p}")

    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise NornyxParseError(f"Cannot read {p}: {exc}") from exc

    try:
        data = yaml.load(raw, Loader=NornyxSafeLoader)
    except yaml.YAMLError as exc:
        raise NornyxParseError(f"Invalid Nornyx/YAML syntax in {p}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise NornyxParseError("Top-level Nornyx document must be a mapping/object")
    return _resolve_policy_refs(data, p.parent)


def _extract_policy_rules(source_doc: dict[str, Any], policy_name: str) -> list[Any] | None:
    """Find a policy's rules in a referenced source, accepting both shapes:

    - a `.nyx` contract:        ``policies: [{name: X, rules: [...]}]``
    - a workspace manifest:     ``policies: {X: [...]}``
    """
    policies = source_doc.get("policies")
    if isinstance(policies, dict):  # workspace-manifest shape
        rules = policies.get(policy_name)
        return list(rules) if isinstance(rules, list) else None
    if isinstance(policies, list):  # .nyx shape
        for item in policies:
            if isinstance(item, dict) and item.get("name") == policy_name:
                rules = item.get("rules")
                return list(rules) if isinstance(rules, list) else None
    return None


def _resolve_policy_refs(data: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Resolve `ref`-based policies into inline rules from a referenced source.

    Instead of copying an org policy's rules into every contract, a policy may
    reference the one canonical definition:

        policies:
          - name: SafeDeliveryPolicy
            ref: ../governance/nornyx.workspace.yaml#SafeDeliveryPolicy

    `ref` is ``<path>#<PolicyName>`` where the path is a local file (a `.nyx`
    contract or a workspace manifest) relative to this contract. The canonical
    rules live in exactly one place, so there is nothing to drift. Resolution is
    offline and compiles the `ref` into inline `rules` (dropping the `ref` key), so
    every downstream consumer — checker, generator, drift gate — sees a normal
    policy. Backward compatible: contracts without any `ref` are untouched.
    """
    policies = data.get("policies")
    if not isinstance(policies, list):
        return data
    if not any(isinstance(p, dict) and "ref" in p for p in policies):
        return data

    source_cache: dict[str, dict[str, Any]] = {}
    for policy in policies:
        if not isinstance(policy, dict) or "ref" not in policy:
            continue
        name = policy.get("name", "<unnamed>")
        if "rules" in policy:
            raise NornyxParseError(f"policy {name!r}: set either 'ref' or 'rules', not both")
        ref = policy["ref"]
        rel_path, _, ref_policy = ref.rpartition("#") if isinstance(ref, str) else ("", "", "")
        if not rel_path or not ref_policy:
            raise NornyxParseError(
                f"policy {name!r}: 'ref' must be '<path>#<PolicyName>', got {ref!r}"
            )
        if is_remote_or_device_path(rel_path):
            raise NornyxParseError(
                f"policy {name!r}: remote or device-backed ref sources are not allowed"
            )
        source_doc = source_cache.get(rel_path)
        if source_doc is None:
            source_path = base_dir / rel_path
            if not source_path.is_file():
                raise NornyxParseError(
                    f"policy {name!r}: ref source not found: {source_path}"
                )
            try:
                source_doc = yaml.load(
                    source_path.read_text(encoding="utf-8"), Loader=NornyxSafeLoader
                ) or {}
            except yaml.YAMLError as exc:
                raise NornyxParseError(
                    f"policy {name!r}: ref source {rel_path!r} is invalid YAML: {exc}"
                ) from exc
            if not isinstance(source_doc, dict):
                raise NornyxParseError(
                    f"policy {name!r}: ref source {rel_path!r} is not a mapping"
                )
            source_cache[rel_path] = source_doc
        rules = _extract_policy_rules(source_doc, ref_policy)
        if rules is None:
            raise NornyxParseError(
                f"policy {name!r}: policy {ref_policy!r} not found in {rel_path}"
            )
        resolved = {key: value for key, value in policy.items() if key != "ref"}
        resolved["rules"] = rules
        policy.clear()
        policy.update(resolved)
    return data
