"""Optional Nornyx agentic-network reference adapters (AN-005, ADR-0037).

This package is intentionally NOT part of the `nornyx` wheel. It contains
reference enforcement hooks that map external framework objects onto one
Nornyx agentic-network contract, enforce declared governance at the adapter
boundary, and emit standardized runtime-event evidence for Nornyx validation.

Adapters cannot cover every framework escape path: a caller that bypasses the
adapter bypasses its enforcement. The final authority is Nornyx validation of
the emitted evidence against the exact contract, lock, and revision.
"""

from .governance_kernel import GovernanceKernel, GovernanceViolation

__all__ = ["GovernanceKernel", "GovernanceViolation"]
