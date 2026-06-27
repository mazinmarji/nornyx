from __future__ import annotations

import importlib.util
from pathlib import Path


def load_server_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "apps" / "nornyx-dev-pmo-portal" / "server.py"
    spec = importlib.util.spec_from_file_location("nornyx_dev_pmo_server", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_favicon_bytes_are_svg() -> None:
    module = load_server_module()
    body = module.favicon_bytes()
    assert body.startswith(b"<svg")
    assert b"N" in body
    assert b"</svg>" in body
