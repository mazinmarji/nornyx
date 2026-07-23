"""A minimal, framework-agnostic declarative binding an adapter declares.

Framework-specific submodules build these from their own static configuration
(never from raw framework arguments — commands, paths, URLs, tool payloads)
and pass the resolved identity/capability refs into the SPI's typed request
constructors. Validation here is deliberately narrow: it only checks that
required declarative fields are present, non-blank strings; it cannot know
whether they name anything the loaded contract actually declares — only the
``Authorizer`` determines that at evaluation time.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import AdapterConfigurationError


@dataclass(frozen=True)
class SurfaceBinding:
    """A closed, adapter-declared mapping from one framework surface to a
    Nornyx identity and capability."""

    surface: str
    identity_ref: str
    capability_ref: str


def validate_binding(binding: SurfaceBinding) -> None:
    """Fail closed if any required field of ``binding`` is missing or blank."""
    for field_name in ("surface", "identity_ref", "capability_ref"):
        value = getattr(binding, field_name)
        if not isinstance(value, str) or not value.strip():
            raise AdapterConfigurationError(
                f"SurfaceBinding.{field_name} must be a non-empty string; got {value!r}."
            )
