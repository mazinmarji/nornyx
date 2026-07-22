"""ADR-0039: freeze the ``nornyx.agentic`` SPI surface and its import boundary."""

from __future__ import annotations

import subprocess
import sys

import nornyx.agentic as agentic

# The frozen public surface. Adding a name is a reviewed change; removing or
# renaming one is a breaking SPI change (bump SPI_VERSION major).
FROZEN_SURFACE = {
    "SPI_VERSION",
    # curated re-exports
    "load_nyx",
    "check_document",
    "has_errors",
    "GovernanceError",
    "GovernanceRegistry",
    "compose_document_governance",
    "evaluate_document_governance",
    "registry_for_contract",
    "contract_digest",
    "agentic_network_lock_digest",
    "build_agentic_network_lock",
    "write_agentic_network_lock",
    "load_agentic_network_lock",
    "verify_agentic_network_lock",
    "render_agentic_network_artifacts",
    "LOCK_SCHEMA_ID",
    "LOCK_FORMAT_VERSION",
    "GENERATION_FORMAT_VERSION",
    "RUNTIME_EVENTS_SCHEMA_ID",
    "RUNTIME_EVENTS_SCHEMA_VERSION",
    "validate_runtime_events",
    "load_runtime_events",
    # authorization engine
    "load_authorizer",
    "Authorizer",
    "EvaluationContext",
    "AuthorizationRequest",
    "CapabilityRequest",
    "DelegationRequest",
    "HandoffRequest",
    "ApprovalRequest",
    "ZoneCrossingRequest",
    "DataShareRequest",
    "ApprovalAssertion",
    "DecisionBasis",
    "DecisionEventIntent",
    "Decision",
    "DecisionEffect",
    "AuthorizerLoadCode",
    "IdentityResolutionCode",
    "DecisionCode",
    "AuthorizerLoadError",
    "IdentityResolutionError",
    "EvidenceRecorder",
}


def test_all_matches_frozen_surface():
    assert set(agentic.__all__) == FROZEN_SURFACE
    assert len(agentic.__all__) == len(set(agentic.__all__))


def test_every_exported_name_resolves():
    for name in agentic.__all__:
        assert hasattr(agentic, name), name
        assert getattr(agentic, name) is not None


def test_spi_version_pinned():
    assert agentic.SPI_VERSION == "1.0"
    assert agentic.authz.SPI_VERSION == agentic.SPI_VERSION


def test_core_imports_no_agent_framework():
    # Importing the SPI must not pull any agent framework into the process. Run
    # in a fresh subprocess so an unrelated earlier test that imported a
    # framework into this session cannot mask a real leak.
    code = (
        "import sys, nornyx.agentic, nornyx.agentic.authz; "
        "banned=[m for m in ('crewai','langgraph','openhands') if m in sys.modules]; "
        "print(banned); sys.exit(1 if banned else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"nornyx.agentic pulled a framework: {result.stdout.strip()}"


def test_event_phases_partition_and_disjoint():
    from nornyx.agentic.authz import PHASE_INTENT, PHASE_OBSERVATION

    assert PHASE_INTENT.isdisjoint(PHASE_OBSERVATION)
    # Together they cover exactly the runtime-event schema's declared event types.
    from nornyx.governance.schemas import load_bundled_schema

    schema = load_bundled_schema("agentic_runtime_events_v1.schema.json")
    enum = set(schema["$defs"]["event"]["properties"]["event_type"]["enum"])
    assert PHASE_INTENT | PHASE_OBSERVATION == enum
