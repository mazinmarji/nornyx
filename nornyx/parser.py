from __future__ import annotations

import re
from pathlib import Path
from typing import Any
import yaml


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
    return data
