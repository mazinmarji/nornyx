from __future__ import annotations

from .models import GovernanceDiagnostic


class GovernanceError(ValueError):
    def __init__(self, *diagnostics: GovernanceDiagnostic):
        self.diagnostics = tuple(diagnostics)
        message = "; ".join(f"{item.code}: {item.message}" for item in self.diagnostics)
        super().__init__(message or "governance operation failed")


def error(code: str, message: str, *, path: str | None = None, source_id: str | None = None) -> GovernanceError:
    return GovernanceError(
        GovernanceDiagnostic("error", code, message, path=path, source_id=source_id)
    )
