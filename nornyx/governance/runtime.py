from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..checker import GraphVocabulary, check_document, graph_vocabulary_for_profile_pack
from .composition import compose_governance
from .errors import GovernanceError, error
from .loader import (
    _reject_symlink_components,
    inspect_local_directory,
    reject_remote_or_device_path,
)
from .locks import load_lock
from .models import CompositionResult, GovernanceDiagnostic
from .registry import GovernanceRegistry
from .rules import evaluate_rules
from .schemas import validate_governance_block
from .structural import evaluate_structural_checks


def _absolute_without_resolving(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def registry_for_directory(
    root: str | Path,
    *,
    trust_root: str | Path | None = None,
) -> GovernanceRegistry:
    reject_remote_or_device_path(root, code_prefix="PACK", noun="Project")
    if trust_root is not None:
        reject_remote_or_device_path(
            trust_root,
            code_prefix="PACK",
            noun="Project",
        )
    project_root = _absolute_without_resolving(Path(root))
    inspection_root = (
        None
        if trust_root is None
        else _absolute_without_resolving(Path(trust_root))
    )
    inspected_project = inspect_local_directory(
        project_root,
        allowed_root=project_root,
        trust_root=inspection_root,
        code_prefix="PACK",
        noun="Project",
    )
    assert inspected_project is not None
    nornyx_root = project_root / ".nornyx"
    inspected_nornyx = inspect_local_directory(
        nornyx_root,
        allowed_root=project_root,
        trust_root=inspection_root,
        code_prefix="PACK",
        noun="Project governance",
        allow_missing=True,
    )
    discovered: list[Path] = []
    if inspected_nornyx is not None:
        for directory_name in ("profiles", "modules"):
            directory = nornyx_root / directory_name
            inspected = inspect_local_directory(
                directory,
                allowed_root=project_root,
                trust_root=inspection_root,
                code_prefix="PACK",
                noun=f"Project {directory_name}",
                allow_missing=True,
            )
            if inspected is not None:
                discovered.append(inspected)

    # Bundled discovery is intentionally deferred until every caller-controlled
    # project component has passed inspection.
    registry = GovernanceRegistry.builtins()
    for directory in discovered:
        registry.register_directory(
            directory,
            source_tier="project",
            trust_root=inspection_root,
        )
    return registry


def registry_for_contract(path: str | Path) -> GovernanceRegistry:
    reject_remote_or_device_path(path, code_prefix="PACK", noun="Contract")
    supplied = Path(path)
    contract = _absolute_without_resolving(supplied)
    trust_root = Path(contract.anchor) if supplied.is_absolute() else Path.cwd()
    _reject_symlink_components(
        contract,
        trust_root,
        code_prefix="PACK",
        noun="Contract",
    )
    return registry_for_directory(contract.parent, trust_root=trust_root)


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


def graph_vocabulary_for_composition(
    composition: CompositionResult | None,
) -> GraphVocabulary | None:
    """The graph vocabulary a composed document's ``graph:`` block is checked against.

    ``None`` when nothing composed a profile, which lets the checker fall back
    to its built-in-profile resolution and report that it did so.
    """
    if composition is None or composition.profile is None:
        return None
    return graph_vocabulary_for_profile_pack(composition.profile)


_UNCOMPOSED = object()


def check_document_with_governance(
    document: Mapping[str, Any],
    *,
    registry: GovernanceRegistry | None = None,
    lock_path: str | Path | None = None,
    composition: CompositionResult | None | object = _UNCOMPOSED,
) -> tuple[list[Any], CompositionResult | None]:
    """Run the static checker against the document's composed governance.

    This is the one place that defines "checked under the active profile": the
    composed profile's ``graph.node_kinds`` and ``relationship_constraints`` are
    applied exactly as ``nornyx check`` applies them, and checker diagnostics
    for top-level blocks a selected module contributes are dropped, as ``nornyx
    check`` drops them. Pass ``composition`` when the caller has already composed
    the document (``None`` meaning "composed, no profile"); otherwise ``registry``
    is required and the document is composed here. Composition failures raise
    ``GovernanceError``; the checker itself never raises. The checker stays
    static and side-effect-free: the composition comes from the caller's
    registry and is handed in.
    """
    if composition is _UNCOMPOSED:
        if registry is None:
            raise TypeError("registry is required when no composition is supplied")
        composition = compose_document_governance(
            document,
            registry=registry,
            lock_path=lock_path,
        )
    assert composition is None or isinstance(composition, CompositionResult)
    diagnostics = list(
        check_document(
            document,  # type: ignore[arg-type]
            graph_vocabulary=graph_vocabulary_for_composition(composition),
        )
    )
    if composition is not None:
        contributed = {item.block for item in (composition.block_schemas or ())}
        diagnostics = [
            item
            for item in diagnostics
            if not (item.code == "UNKNOWN_TOP_LEVEL_BLOCK" and item.path in contributed)
        ]
    return diagnostics, composition


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
