"""``nornyx.agentic`` — the supported agentic integration SPI (ADR-0039).

Two parts:

* **Curated re-exports** — one stable import path for the contract, checker,
  artifact/lock, and evidence names that already exist in their home modules.
* **A framework-neutral authorization engine** (``nornyx.agentic.authz``,
  re-exported here) — a loaded, immutable, lock-verified :class:`Authorizer` that
  evaluates discriminated authorization requests against Nornyx contract
  semantics and returns typed :class:`Decision` objects carrying decision-event
  intents only, plus an :class:`EvidenceRecorder` that binds evidence.

The SPI imports no agent framework. Framework interception, executor wrapping,
argument normalisation, and compatibility live in external adapter packages.
This is a cooperative Tier 2 boundary (ADR-0040): it never authenticates agents
or approvers, executes tools, or asserts runtime-event truth.

ADR-0044 adds a narrow public OpenID AuthZEN 1.0 mapping for capability
evaluations. It is a deterministic codec/local bridge only, not a hosted PDP,
transport implementation, enforcement point, or Enterprise control plane.
"""

from __future__ import annotations

# --- curated re-exports (names already public in their home modules) ---
from ..agentic_artifacts import (
    GENERATION_FORMAT_VERSION,
    LOCK_FORMAT_VERSION,
    LOCK_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_ID,
    RUNTIME_EVENTS_SCHEMA_VERSION,
    agentic_network_lock_digest,
    build_agentic_network_lock,
    contract_digest,
    load_agentic_network_lock,
    render_agentic_network_artifacts,
    verify_agentic_network_lock,
    write_agentic_network_lock,
)
from ..agentic_evidence import load_runtime_events, validate_runtime_events
from ..checker import check_document, has_errors
from ..governance import (
    GovernanceError,
    GovernanceRegistry,
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
)
from ..parser import load_nyx

# --- authorization engine (nornyx.agentic.authz) ---
from .authz import (
    SPI_VERSION,
    ApprovalAssertion,
    ApprovalRequest,
    AuthorizationRequest,
    Authorizer,
    AuthorizerLoadCode,
    AuthorizerLoadError,
    AuthorizerState,
    CapabilityRequest,
    DataShareRequest,
    Decision,
    DecisionBasis,
    DecisionCode,
    DecisionEffect,
    DecisionEventIntent,
    DelegationRequest,
    EvaluationContext,
    EvidenceRecorder,
    HandoffRequest,
    IdentityResolutionCode,
    IdentityResolutionError,
    RuntimeOccurrence,
    ZoneCrossingRequest,
    load_authorizer,
)

# --- OpenID AuthZEN interoperability (ADR-0044) ---
from .authzen import (
    AUTHZEN_ACCESS_EVALUATION_PATH,
    AUTHZEN_API_VERSION,
    NORNYX_AUTHZEN_CAPABILITY_PROFILE,
    AuthZENMappingError,
    capability_request_from_authzen,
    capability_request_to_authzen,
    decision_to_authzen,
    evaluate_authzen_capability,
)

__all__ = [
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
    "AuthorizerState",
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
    "RuntimeOccurrence",
    "EvidenceRecorder",
    # OpenID AuthZEN mapping
    "AUTHZEN_API_VERSION",
    "AUTHZEN_ACCESS_EVALUATION_PATH",
    "NORNYX_AUTHZEN_CAPABILITY_PROFILE",
    "AuthZENMappingError",
    "capability_request_to_authzen",
    "capability_request_from_authzen",
    "decision_to_authzen",
    "evaluate_authzen_capability",
]
