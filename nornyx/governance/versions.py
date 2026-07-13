from __future__ import annotations

import re


_COMPARISON = re.compile(r"^(>=|<=|>|<|=)?([0-9]+(?:\.[0-9]+){1,2})$")


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = [int(item) for item in value.split(".")]
    return tuple((parts + [0, 0])[:3])  # type: ignore[return-value]


def core_range_allows(expression: str, version: str = "1.0") -> bool:
    current = _version_tuple(version)
    tokens = expression.split()
    if not tokens:
        return False
    for token in tokens:
        match = _COMPARISON.fullmatch(token)
        if not match:
            return False
        operator, raw = match.groups()
        target = _version_tuple(raw)
        if operator in (None, "=") and current != target:
            return False
        if operator == ">=" and current < target:
            return False
        if operator == "<=" and current > target:
            return False
        if operator == ">" and current <= target:
            return False
        if operator == "<" and current >= target:
            return False
    return True
