"""Regression: Linux symlink-setup failures fail closed, never skip."""

from __future__ import annotations

from pathlib import Path

import pytest

from symlink_support import create_symlink_or_skip, handle_symlink_failure


def _forced_failure_link(tmp_path: Path) -> Path:
    # A missing parent directory makes symlink creation raise OSError on every
    # platform, without needing elevated privileges or a real Linux host.
    return tmp_path / "missing-parent" / "link"


def test_linux_symlink_setup_failure_fails_the_test(tmp_path: Path) -> None:
    with pytest.raises(pytest.fail.Exception):
        create_symlink_or_skip(
            _forced_failure_link(tmp_path),
            tmp_path / "target",
            platform="linux",
        )


def test_non_linux_symlink_setup_failure_skips(tmp_path: Path) -> None:
    with pytest.raises(pytest.skip.Exception):
        create_symlink_or_skip(
            _forced_failure_link(tmp_path),
            tmp_path / "target",
            platform="win32",
        )


def test_failure_handler_matches_platform_policy() -> None:
    with pytest.raises(pytest.fail.Exception):
        handle_symlink_failure(OSError("forced"), platform="linux")
    with pytest.raises(pytest.skip.Exception):
        handle_symlink_failure(OSError("forced"), platform="darwin")


def test_every_symlink_creation_site_routes_through_the_shared_policy() -> None:
    # No governance or package test may catch a symlink-creation failure with
    # a bare pytest.skip: every site must use the shared helper so the Linux
    # fail-closed branch cannot be bypassed by a new unguarded copy.
    offenders: list[str] = []
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        if path.name == "test_symlink_support.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "symlink_to(" in text and "pytest.skip(" in text:
            offenders.append(path.name)
    assert offenders == [], (
        "symlink tests must use tests.symlink_support instead of bare "
        f"pytest.skip: {offenders}"
    )
