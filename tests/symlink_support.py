"""Shared symlink-setup policy for security tests.

Real symlinks are mandatory on Linux (doc 13, security/adversarial): when a
required test symlink cannot be created there, the test must fail, not skip,
so security coverage cannot silently vanish. Platforms without reliable
symlink capability (notably Windows without SeCreateSymbolicLinkPrivilege)
may skip with a documented reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def create_symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
    platform: str = sys.platform,
) -> None:
    """Create ``link -> target`` or apply the platform skip policy.

    ``platform`` is injectable so the fail-closed Linux branch is testable on
    every host.
    """
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        handle_symlink_failure(exc, platform=platform)


def handle_symlink_failure(exc: BaseException, *, platform: str = sys.platform) -> None:
    """Fail on Linux, skip elsewhere, for a symlink-creation failure."""
    if platform.startswith("linux"):
        pytest.fail(f"real Linux symlink creation failed: {exc}")
    pytest.skip(f"symlink creation is unavailable: {exc}")
