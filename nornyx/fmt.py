from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .parser import load_nyx


def format_document(doc: dict[str, Any]) -> str:
    """Canonical v0.1 formatting.

    v0.1 is YAML-compatible by design. This formatter keeps output stable and
    diff-friendly. A later grammar-native formatter can replace this function.
    """
    rendered = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    return rendered if rendered.endswith("\n") else rendered + "\n"


def format_file(path: str | Path, *, write: bool = False) -> str:
    p = Path(path)
    doc = load_nyx(p)
    rendered = format_document(doc)
    if write:
        p.write_text(rendered, encoding="utf-8")
    return rendered
