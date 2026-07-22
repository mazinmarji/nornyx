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
    ZoneCrossingRequest,
    load_authorizer,
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
]
