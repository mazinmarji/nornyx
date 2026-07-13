from __future__ import annotations

import os
import re


_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_WINDOWS_DEVICE_COMPONENT = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    re.IGNORECASE,
)


def is_remote_or_device_path(path: str | os.PathLike[str]) -> bool:
    """Classify paths that must be rejected before any filesystem access.

    The check is deliberately lexical and host-independent.  A Linux runner
    must reject a Windows UNC or device path just as a Windows runner does, and
    an ordinary drive-qualified Windows path must not be mistaken for a URI.
    """

    text = os.fspath(path)
    if not isinstance(text, str):
        return True
    if _URI_SCHEME.match(text) and not (
        len(text) >= 3
        and text[0].isalpha()
        and text[1] == ":"
        and text[2] in {"\\", "/"}
    ):
        return True

    windows = text.replace("/", "\\")
    lowered = windows.casefold()
    if windows.startswith("\\\\"):
        return True
    if lowered.startswith(("\\??\\", "\\device\\", "\\global??\\")):
        return True

    # Windows device names retain their special meaning with extensions and
    # when they occur below an otherwise ordinary directory.
    for component in re.split(r"[\\/]", text):
        candidate = component.rstrip(" .")
        if not candidate:
            continue
        # A stream suffix does not make a reserved DOS device safe.
        candidate = candidate.split(":", 1)[0]
        if _WINDOWS_DEVICE_COMPONENT.fullmatch(candidate):
            return True
    return False
