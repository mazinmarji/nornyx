"""Failure taxonomy for the external adoption pilot.

Same invariant as the pip-only conformance example: exactly one class is
attributed to the caller, and every other class indicts the published
distributions. A pilot report that can only say "it did not work" is not a bug
report, and a first-time external user is precisely the person least able to
diagnose which half broke.

This is a *separate* taxonomy from `examples/pip_only_conformance`, not an
import of it, because the pilot has to be copyable and runnable outside the
repository -- importing a sibling example would defeat that. The classes that
overlap keep the same names and meanings on purpose.

``REGISTRY_INSTALL_FAILED``
    The pinned distributions could not be installed from PyPI, or installed and
    are not importable.
``INSTALLED_VERSION_MISMATCH``
    Something installed, but the resolved version is not the one requested.
``FRAMEWORK_EXTRA_UNAVAILABLE``
    The ``[crewai]`` extra did not deliver a usable framework at its declared
    pin. Named separately from a plain install failure because the base package
    can be perfectly healthy while the extra is not, and the remedy differs.
``SOURCE_TREE_LEAKAGE_DETECTED``
    Code or data resolved from outside the environment's ``site-packages``, or
    from inside a repository checkout. Whatever the run then shows, it does not
    show it about the published artifacts.
``SCENARIO_EXECUTION_FAILED``
    A variant did not complete: the framework raised, the scripted model was
    never driven, or the run could not produce a comparable result.
``GOVERNANCE_EXPECTATION_UNMET``
    Everything ran, and governance did not do what it claims. The governed
    variant executed an action it should have refused, an authorized call was
    blocked, or the expected evidence was absent.

    This is the class that makes the pilot a control rather than a
    demonstration. Without it a "successful" run means only that nothing
    crashed, which is not the claim being made.
``PILOT_INPUT_INVALID``
    The fault is local to the caller: bad arguments, or an environment that
    could not be prepared. Never a statement about the published packages.
"""

from __future__ import annotations

from enum import Enum


class PilotFailure(str, Enum):
    """Why an adoption-pilot run did not demonstrate governed behavior."""

    REGISTRY_INSTALL_FAILED = "REGISTRY_INSTALL_FAILED"
    INSTALLED_VERSION_MISMATCH = "INSTALLED_VERSION_MISMATCH"
    FRAMEWORK_EXTRA_UNAVAILABLE = "FRAMEWORK_EXTRA_UNAVAILABLE"
    SOURCE_TREE_LEAKAGE_DETECTED = "SOURCE_TREE_LEAKAGE_DETECTED"
    SCENARIO_EXECUTION_FAILED = "SCENARIO_EXECUTION_FAILED"
    GOVERNANCE_EXPECTATION_UNMET = "GOVERNANCE_EXPECTATION_UNMET"
    PILOT_INPUT_INVALID = "PILOT_INPUT_INVALID"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


#: Classes that attribute the failure to the published distributions rather
#: than to the caller.
DISTRIBUTION_FAILURE_CLASSES = frozenset(
    member for member in PilotFailure if member is not PilotFailure.PILOT_INPUT_INVALID
)


class PilotError(RuntimeError):
    """A classified pilot failure, carrying the class and its evidence."""

    def __init__(
        self,
        failure_class: PilotFailure,
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
        return self.failure_class in DISTRIBUTION_FAILURE_CLASSES

    @property
    def remedy(self) -> str:
        """What the reporter should do next. An adoption pilot owes them this."""
        return _REMEDIES[self.failure_class]

    def as_dict(self) -> dict[str, object]:
        return {
            "failure_class": self.failure_class.value,
            "detail": self.detail,
            "attributable_to_distribution": self.attributable_to_distribution,
            "remedy": self.remedy,
            "evidence": self.evidence,
        }


_REMEDIES: dict[PilotFailure, str] = {
    PilotFailure.REGISTRY_INSTALL_FAILED: (
        "Report this with the pip output attached. The published distributions "
        "could not be obtained; nothing about your setup needs changing first."
    ),
    PilotFailure.INSTALLED_VERSION_MISMATCH: (
        "Report this with the resolved versions attached. A constraint or a "
        "shadowing install resolved something other than the pinned versions."
    ),
    PilotFailure.FRAMEWORK_EXTRA_UNAVAILABLE: (
        "Report this with the CrewAI version attached. The base package may be "
        "healthy while the [crewai] extra is not; they fail independently."
    ),
    PilotFailure.SOURCE_TREE_LEAKAGE_DETECTED: (
        "Report this with the origins attached. Something resolved from a "
        "checkout or outside site-packages, so the run proves nothing about "
        "the published artifacts."
    ),
    PilotFailure.SCENARIO_EXECUTION_FAILED: (
        "Report this with the variant id and traceback attached. A scenario "
        "variant did not complete, so the comparison could not be made."
    ),
    PilotFailure.GOVERNANCE_EXPECTATION_UNMET: (
        "Report this first and with priority. Everything ran and governance "
        "did not hold: this is the pilot's primary control, and a failure here "
        "is a governance defect rather than an environment problem."
    ),
    PilotFailure.PILOT_INPUT_INVALID: (
        "Adjust the invocation or the local environment and re-run. This is a "
        "caller-side fault and says nothing about the published packages."
    ),
}
