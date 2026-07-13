"""Declarative, local-only governance extension runtime."""

from .approvals import normalize_approval, trusted_normalized_approval
from .composition import compose_governance
from .errors import GovernanceError
from .loader import load_local_pack, load_pack_bytes
from .locks import load_lock, lock_for_packs, verify_lock, write_lock
from .models import (
    CompositionResult,
    GovernanceBlockSchema,
    GovernanceDiagnostic,
    GovernanceModule,
    LockEntry,
    NormalizedApproval,
    ProfileLock,
    ProfilePack,
    ProjectionResult,
    Rule,
    StarterFragment,
)
from .projection import project_profile_to_v03
from .registry import GovernanceRegistry
from .rules import evaluate_rule, evaluate_rules
from .runtime import (
    compose_document_governance,
    evaluate_document_governance,
    registry_for_contract,
    registry_for_directory,
)
from .structural import change_scope_hash

__all__ = [
    "CompositionResult",
    "GovernanceBlockSchema",
    "GovernanceDiagnostic",
    "GovernanceError",
    "GovernanceModule",
    "GovernanceRegistry",
    "LockEntry",
    "NormalizedApproval",
    "ProfileLock",
    "ProfilePack",
    "ProjectionResult",
    "Rule",
    "StarterFragment",
    "change_scope_hash",
    "compose_document_governance",
    "compose_governance",
    "evaluate_document_governance",
    "evaluate_rule",
    "evaluate_rules",
    "load_local_pack",
    "load_lock",
    "load_pack_bytes",
    "lock_for_packs",
    "normalize_approval",
    "trusted_normalized_approval",
    "project_profile_to_v03",
    "registry_for_contract",
    "registry_for_directory",
    "verify_lock",
    "write_lock",
]
