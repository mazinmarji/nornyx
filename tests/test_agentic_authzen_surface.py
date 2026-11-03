"""ADR-0039 / ADR-0044: pin the supported ``nornyx.agentic.authzen`` surface.

``nornyx.agentic.authzen`` is part of the supported in-process agentic SPI from
SPI 1.3. It is imported explicitly as a submodule; the frozen top-level facade
``nornyx.agentic.__all__`` does not re-export it (see
``tests/test_agentic_facade_surface.py``).
"""

from __future__ import annotations

import inspect
import pkgutil
import subprocess
import sys

import nornyx.agentic as agentic
import nornyx.agentic.authzen as authzen

# The supported submodule surface. Adding a name is a reviewed, additive SPI
# change (SPI minor); removing or renaming one, or changing a signature
# incompatibly, is a breaking SPI change (SPI major).
AUTHZEN_SURFACE = {
    "AUTHZEN_API_VERSION",
    "AUTHZEN_ACCESS_EVALUATION_PATH",
    "NORNYX_AUTHZEN_CAPABILITY_PROFILE",
    "AuthZENMappingError",
    "capability_request_to_authzen",
    "capability_request_from_authzen",
    "decision_to_authzen",
    "evaluate_authzen_capability",
}

AUTHZEN_SIGNATURES = {
    "capability_request_to_authzen": (
        "(request: 'CapabilityRequest', *, context: 'EvaluationContext') -> 'dict[str, Any]'"
    ),
    "capability_request_from_authzen": (
        "(payload: 'Mapping[str, Any]') -> 'tuple[CapabilityRequest, EvaluationContext]'"
    ),
    "decision_to_authzen": "(decision: 'Decision') -> 'dict[str, Any]'",
    "evaluate_authzen_capability": (
        "(authorizer: 'Authorizer', payload: 'Mapping[str, Any]') -> 'dict[str, Any]'"
    ),
}


def test_spi_version_includes_authzen_submodule():
    # The exact SPI value is pinned in test_agentic_facade_surface.py; here the
    # requirement is only that the SPI is a 1.x release from 1.3 onward.
    major, minor = (int(part) for part in agentic.SPI_VERSION.split("."))
    assert major == 1
    assert minor >= 3


def test_all_matches_supported_surface():
    assert set(authzen.__all__) == AUTHZEN_SURFACE
    assert len(authzen.__all__) == len(set(authzen.__all__))


def test_all_lists_every_public_name_the_module_defines():
    # A public function, class, or UPPER_CASE constant defined in the module
    # but missing from __all__ would be an unclassified API.
    defined = set()
    for name, value in vars(authzen).items():
        if name.startswith("_"):
            continue
        if inspect.isfunction(value) or inspect.isclass(value):
            if value.__module__ == "nornyx.agentic.authzen":
                defined.add(name)
        elif name.isupper():
            defined.add(name)
    assert defined == set(authzen.__all__)


def test_agentic_package_has_only_classified_submodules():
    # Every submodule of nornyx.agentic is either re-exported through the
    # frozen facade (authz) or an explicitly imported supported submodule
    # (authzen, from SPI 1.3). A new submodule needs an SPI classification
    # (docs/VERSIONING.md) before it is added here.
    found = {module.name for module in pkgutil.iter_modules(agentic.__path__)}
    assert found == {"authz", "authzen"}


def test_every_exported_name_resolves_and_is_owned_by_the_module():
    for name in authzen.__all__:
        value = getattr(authzen, name)
        assert value is not None, name
        if inspect.isclass(value) or inspect.isfunction(value):
            assert value.__module__ == "nornyx.agentic.authzen", name


def test_star_import_exposes_exactly_the_supported_surface():
    namespace: dict[str, object] = {}
    exec("from nornyx.agentic.authzen import *", namespace)
    exported = {name for name in namespace if name != "__builtins__"}
    assert exported == AUTHZEN_SURFACE


def test_public_callable_signatures_are_pinned():
    for name, signature in AUTHZEN_SIGNATURES.items():
        assert str(inspect.signature(getattr(authzen, name))) == signature, name


def test_mapping_error_is_a_value_error():
    assert issubclass(authzen.AuthZENMappingError, ValueError)


def test_constants_are_pinned():
    assert authzen.AUTHZEN_API_VERSION == "1.0"
    assert authzen.AUTHZEN_ACCESS_EVALUATION_PATH == "/access/v1/evaluation"
    assert authzen.NORNYX_AUTHZEN_CAPABILITY_PROFILE == "nornyx.authzen.capability.v1"


def test_authzen_is_not_part_of_the_frozen_facade():
    assert "authzen" not in agentic.__all__
    for name in AUTHZEN_SURFACE:
        assert name not in agentic.__all__, name


def test_authzen_imports_no_agent_framework():
    # Run in a fresh subprocess so an unrelated earlier test that imported a
    # framework into this session cannot mask a real leak.
    code = (
        "import sys, nornyx.agentic.authzen; "
        "banned=[m for m in ('crewai','langgraph','openhands') if m in sys.modules]; "
        "print(banned); sys.exit(1 if banned else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"nornyx.agentic.authzen pulled a framework: {result.stdout.strip()}"
