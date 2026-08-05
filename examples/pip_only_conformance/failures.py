"""Failure taxonomy for the pip-only registry-backed conformance example.

The point of naming these classes is attribution. A pip-only example that can
only say "it did not work" cannot distinguish a broken *distribution* from a
broken *invocation*, which is exactly the distinction a consumer needs: the
first is our defect, the second is theirs.

Each class answers one question and no other:

``REGISTRY_INSTALL_FAILED``
    The named version could not be installed from the index, or installed but
    is not importable. The published artifact is unusable.
``INSTALLED_VERSION_MISMATCH``
    Something installed, but the resolved distribution version is not the one
    requested. A version constraint, a cached wheel, or a shadowing install.
``SOURCE_TREE_LEAKAGE_DETECTED``
    Code or data resolved from somewhere other than the environment's
    ``site-packages`` -- most importantly from a repository checkout. Whatever
    the run then proves, it does not prove it about the published artifact.
``PACKAGED_RESOURCE_MISSING``
    A bundled resource could not be resolved through ``importlib.resources``.
    This is the failure mode an undeclared ``package-data`` entry produces, and
    it surfaces only from an installed distribution.
``PACKAGED_RESOURCE_INVALID``
    A bundled resource resolved, but its content failed semantic validation.
    Distinct from MISSING on purpose: "present" and "correct" are different
    claims, and collapsing them lets a truncated or stale resource pass as
    healthy.
``CONFORMANCE_EXECUTION_FAILED``
    The kit ran from the installed distribution and did not reach a conformant
    result, or its emitted report failed validation against the bundled schema.
``EXAMPLE_INPUT_INVALID``
    The example itself was invoked wrongly. Never a statement about the
    published package.
"""

from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    """Why a pip-only example run did not reach a conformant result."""

    REGISTRY_INSTALL_FAILED = "REGISTRY_INSTALL_FAILED"
    INSTALLED_VERSION_MISMATCH = "INSTALLED_VERSION_MISMATCH"
    SOURCE_TREE_LEAKAGE_DETECTED = "SOURCE_TREE_LEAKAGE_DETECTED"
    PACKAGED_RESOURCE_MISSING = "PACKAGED_RESOURCE_MISSING"
    PACKAGED_RESOURCE_INVALID = "PACKAGED_RESOURCE_INVALID"
    CONFORMANCE_EXECUTION_FAILED = "CONFORMANCE_EXECUTION_FAILED"
    EXAMPLE_INPUT_INVALID = "EXAMPLE_INPUT_INVALID"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


#: Classes that attribute the failure to the published distribution rather than
#: to the caller. `EXAMPLE_INPUT_INVALID` is deliberately excluded: misusing the
#: example says nothing about the artifact on the index.
DISTRIBUTION_FAILURE_CLASSES = frozenset(
    member for member in FailureClass if member is not FailureClass.EXAMPLE_INPUT_INVALID
)


class PipOnlyExampleError(RuntimeError):
    """A classified failure, carrying the class and the evidence behind it."""

    def __init__(
        self,
        failure_class: FailureClass,
        detail: str,
        *,
        evidence: dict[str, object] | None = None,
    ) -> None:
        super().__init__(f"{failure_class.value}: {detail}")
        self.failure_class = failure_class
        self.detail = detail
        self.evidence: dict[str, object] = dict(evidence or {})

    @property
    def attributable_to_distribution(self) -> bool:
        """True when this failure indicts the published artifact, not the caller."""
        return self.failure_class in DISTRIBUTION_FAILURE_CLASSES

    def as_dict(self) -> dict[str, object]:
        return {
            "failure_class": self.failure_class.value,
            "detail": self.detail,
            "attributable_to_distribution": self.attributable_to_distribution,
            "evidence": self.evidence,
        }
