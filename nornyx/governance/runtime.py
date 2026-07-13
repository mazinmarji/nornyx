from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .composition import compose_governance
from .errors import GovernanceError, error
from .locks import load_lock
from .models import CompositionResult, GovernanceDiagnostic
from .registry import GovernanceRegistry
from .rules import evaluate_rules
from .schemas import validate_governance_block
from .structural import evaluate_structural_checks


def registry_for_directory(root: str | Path) -> GovernanceRegistry:
    registry = GovernanceRegistry.builtins()
    nornyx_root = Path(root).resolve() / ".nornyx"
    for directory_name in ("profiles", "modules"):
        directory = nornyx_root / directory_name
        if directory.is_dir():
            registry.register_directory(directory, source_tier="project")
    return registry


def registry_for_contract(path: str | Path) -> GovernanceRegistry:
    return registry_for_directory(Path(path).resolve().parent)


def compose_document_governance(
    document: Mapping[str, Any],
    *,
    registry: GovernanceRegistry,
    lock_path: str | Path | None = None,
) -> CompositionResult | None:
    project = document.get("project")
    if not isinstance(project, Mapping):
        return None
    profile_value = project.get("profile")
    profile_identity = str(profile_value) if profile_value is not None else None
    module_value = project.get("modules", [])
    if not isinstance(module_value, list) or not all(
        isinstance(item, str) and item for item in module_value
    ):
        raise error(
            "PACK_MODULE_SELECTION_INVALID",
            "project.modules must be a list of non-empty module identifiers.",
            path="project.modules",
        )
    if profile_identity is None and not module_value:
        return None
    if profile_identity is not None and not module_value:
        # project.profile has always been a free-form field; a value that does
        # not match any governance pack must not fail existing contracts.
        # Explicit project.modules is an opt-in and stays fail-closed.
        try:
            registry.resolve_profile(profile_identity)
        except GovernanceError:
            return None
    lock = load_lock(lock_path) if lock_path is not None else None
    return compose_governance(
        registry,
        profile_identity=profile_identity,
        module_ids=module_value,
        lock=lock,
    )


def evaluate_document_governance(
    document: Mapping[str, Any],
    *,
    registry: GovernanceRegistry,
    lock_path: str | Path | None = None,
    as_of: str | None = None,
    document_root: str | Path | None = None,
) -> tuple[GovernanceDiagnostic, ...]:
    composition = compose_document_governance(
        document,
        registry=registry,
        lock_path=lock_path,
    )
    if composition is None:
        project = document.get("project")
        profile_value = project.get("profile") if isinstance(project, Mapping) else None
        if profile_value is not None:
            try:
                registry.resolve_profile(str(profile_value))
            except GovernanceError:
                return (
                    GovernanceDiagnostic(
                        "warning",
                        "PACK_NOT_RESOLVED",
                        f"project.profile {profile_value!r} does not match a governance "
                        "pack; pack rules were not evaluated.",
                        path="project.profile",
                    ),
                )
        return ()
    diagnostics: list[GovernanceDiagnostic] = []
    enforced_blocks = sorted(
        {
            block
            for module in composition.modules
            for block in module.required_blocks
        }
    )
    for block in enforced_blocks:
        if block not in document:
            diagnostics.append(
                GovernanceDiagnostic(
                    "error",
                    "GOVERNANCE_REQUIRED_BLOCK_MISSING",
                    f"Selected governance modules require top-level block {block!r}.",
                    path=block,
                )
            )
    for binding in composition.block_schemas:
        if binding.block in document:
            diagnostics.extend(
                validate_governance_block(
                    binding.block,
                    document[binding.block],
                    binding.schema_id,
                    source_id=binding.source_id,
                )
            )
    diagnostics.extend(evaluate_rules(document, composition.rules))
    diagnostics.extend(
        evaluate_structural_checks(
            document,
            composition,
            as_of=as_of,
            document_root=document_root,
        )
    )
    return tuple(diagnostics)
