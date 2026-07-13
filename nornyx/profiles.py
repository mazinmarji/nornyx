from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from importlib import resources
import json
from pathlib import Path
from typing import Any

import yaml

from .governance.projection import project_profile_to_v03
from .governance.registry import GovernanceRegistry
from .governance.models import ProfilePack


PROFILE_CONFORMANCE_LEVEL = "v0.6"
_PROJECT_NAME_SENTINEL = "__NORNYX_PROJECT_NAME__"


@lru_cache(maxsize=1)
def builtin_profile_registry() -> GovernanceRegistry:
    return GovernanceRegistry.builtins()


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = resources.files("nornyx") / "profiles_data" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


PROFILE_NAMES = list(_catalog()["profiles"])
BASE_PROFILE_NAMES = list(_catalog()["base_profiles"])
DOMAIN_PROFILE_NAMES = list(_catalog()["domain_profiles"])


def _profile(name: str):
    try:
        return builtin_profile_registry().resolve_profile(name)
    except ValueError as exc:
        raise ValueError(
            f"Unknown profile {name!r}. Expected one of: {', '.join(PROFILE_NAMES)}"
        ) from exc


def profile_pack(profile: str) -> dict[str, Any]:
    if profile not in DOMAIN_PROFILE_NAMES:
        raise ValueError(
            f"Unknown v0.3 domain profile {profile!r}. "
            f"Expected one of: {', '.join(DOMAIN_PROFILE_NAMES)}"
        )
    return project_profile_to_v03(_profile(profile)).legacy_dict()


def profile_pack_catalog() -> list[dict[str, Any]]:
    return [profile_pack(name) for name in DOMAIN_PROFILE_NAMES]


def profile_pack_v1(profile: str) -> dict[str, Any]:
    """Return an independent copy of the authoritative built-in v1 pack."""
    return _profile(profile).as_dict()


def profile_projection_report(profile: str) -> dict[str, Any]:
    return project_profile_to_v03(_profile(profile)).report.to_dict()


def _compatibility_row(name: str) -> dict[str, list[str]]:
    raw = _profile(name).raw
    compatibility = raw["compatibility"]
    return {
        "compatible_with": list(compatibility["compatible_with"]),
        "requires_review_with": list(compatibility["requires_review_with"]),
        "conflicts_with": list(raw["conflicts"]),
    }


def profile_compatibility_matrix() -> dict[str, dict[str, list[str]]]:
    return {name: _compatibility_row(name) for name in DOMAIN_PROFILE_NAMES}


# Heavy constants are computed lazily via module __getattr__ (PEP 562) so that
# importing nornyx.profiles (and therefore nornyx.cli) does not load and
# schema-validate every built-in pack up front. `from nornyx.profiles import
# GENERAL_CORE_CONCEPTS` still works and returns the same shapes as before.
_LAZY_EXPORTS = (
    "GENERAL_CORE_CONCEPTS",
    "PROFILE_NON_GOALS",
    "PROFILE_STABILITY",
    "PROFILE_COMPATIBILITY_MATRIX",
    "DOMAIN_PROFILE_PACKS",
)


@lru_cache(maxsize=1)
def _lazy_constants() -> dict[str, Any]:
    packs = {name: profile_pack(name) for name in DOMAIN_PROFILE_NAMES}
    return {
        "GENERAL_CORE_CONCEPTS": list(packs[DOMAIN_PROFILE_NAMES[0]]["core_concepts"]),
        "PROFILE_NON_GOALS": list(_profile(PROFILE_NAMES[0]).non_goals),
        "PROFILE_STABILITY": {
            name: deepcopy(pack["conformance"]) for name, pack in packs.items()
        },
        "PROFILE_COMPATIBILITY_MATRIX": profile_compatibility_matrix(),
        "DOMAIN_PROFILE_PACKS": packs,
    }


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        return _lazy_constants()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def validate_profile_pack_catalog() -> list[str]:
    issues: list[str] = []
    required_pack_fields = {
        "name",
        "version",
        "core_surface",
        "status",
        "purpose",
        "domain",
        "required_blocks",
        "recommended_blocks",
        "graph_node_kinds",
        "validation_rules",
        "conformance",
        "non_goals",
        "core_concepts",
    }
    allowed_core_concepts = set(_lazy_constants()["GENERAL_CORE_CONCEPTS"])

    for name in DOMAIN_PROFILE_NAMES:
        pack = profile_pack(name)
        missing = sorted(required_pack_fields - set(pack))
        if missing:
            issues.append(f"{name}: missing fields {missing}")
        if pack.get("name") != name:
            issues.append(f"{name}: pack name mismatch")
        if pack.get("version") != "v0.3":
            issues.append(f"{name}: version must be v0.3")
        if pack.get("core_surface") != "v0.2":
            issues.append(f"{name}: core_surface must remain v0.2")
        if pack.get("status") != "optional_profile":
            issues.append(f"{name}: status must be optional_profile")
        if not set(pack.get("core_concepts", [])) <= allowed_core_concepts:
            issues.append(f"{name}: profile introduces non-core concepts as mandatory core")
        required_blocks = pack.get("required_blocks", [])
        if not isinstance(required_blocks, list) or not {
            "project",
            "policies",
            "evidence",
            "goals",
        }.issubset(required_blocks):
            issues.append(
                f"{name}: required_blocks must include project, policies, evidence, and goals"
            )
        if not pack.get("validation_rules"):
            issues.append(f"{name}: validation_rules must be a non-empty list")
        non_goals = set(pack.get("non_goals", []))
        if not {
            "live agent runtime",
            "automatic approvals",
            "production deployment",
        }.issubset(non_goals):
            issues.append(
                f"{name}: non_goals must block runtime, automatic approvals, and production deployment"
            )
    return issues


def validate_profile_conformance() -> list[str]:
    issues = validate_profile_pack_catalog()
    required_safety_non_goals = set(_lazy_constants()["PROFILE_NON_GOALS"])
    allowed_readiness = {"stable_candidate", "profile_candidate", "optional_candidate"}

    for name in DOMAIN_PROFILE_NAMES:
        pack = profile_pack(name)
        conformance = pack.get("conformance")
        if not isinstance(conformance, dict):
            issues.append(f"{name}: missing conformance metadata")
            continue
        if conformance.get("v1_readiness") not in allowed_readiness:
            issues.append(f"{name}: invalid v1_readiness {conformance.get('v1_readiness')!r}")
        if not isinstance(conformance.get("migration"), str) or not conformance["migration"].strip():
            issues.append(f"{name}: migration guidance is required")
        if set(pack.get("non_goals", [])) != required_safety_non_goals:
            issues.append(f"{name}: profile non_goals must match the shared safety boundary")
        if pack.get("core_concepts") != _lazy_constants()["GENERAL_CORE_CONCEPTS"]:
            issues.append(f"{name}: core_concepts must remain the general Nornyx core list")

    matrix = profile_compatibility_matrix()
    expected_names = set(DOMAIN_PROFILE_NAMES)
    if set(matrix) != expected_names:
        issues.append("profile compatibility matrix must cover every domain profile exactly")
    for name, row in matrix.items():
        for field in ("compatible_with", "requires_review_with", "conflicts_with"):
            values = row[field]
            unknown = sorted(set(values) - expected_names)
            if unknown:
                issues.append(f"{name}: compatibility matrix {field} has unknown profiles {unknown}")
            if name in values:
                issues.append(f"{name}: compatibility matrix {field} must not include itself")
        overlap = set(row["compatible_with"]) & set(row["conflicts_with"])
        if overlap:
            issues.append(f"{name}: compatible/conflict overlap {sorted(overlap)}")
    return issues


def profile_conformance_report() -> dict[str, Any]:
    issues = validate_profile_conformance()
    return {
        "schema": "nornyx.profile_conformance.v0.6",
        "status": "conformant" if not issues else "needs_review",
        "conformance_level": PROFILE_CONFORMANCE_LEVEL,
        "core_boundary": "Profiles are optional overlays and do not add mandatory core concepts.",
        "profiles": profile_pack_catalog(),
        "compatibility_matrix": profile_compatibility_matrix(),
        "issues": issues,
    }


def _merge_fragment(existing: Any, incoming: Any, *, path: str) -> Any:
    if isinstance(existing, dict) and isinstance(incoming, dict):
        result = deepcopy(existing)
        for key, value in incoming.items():
            child_path = f"{path}.{key}" if path else str(key)
            result[key] = (
                _merge_fragment(result[key], value, path=child_path)
                if key in result
                else deepcopy(value)
            )
        return result
    if isinstance(existing, list) and isinstance(incoming, list):
        result = deepcopy(existing)
        for value in incoming:
            if value not in result:
                result.append(deepcopy(value))
        return result
    if existing != incoming:
        raise ValueError(f"Starter fragment conflicts at {path!r}.")
    return deepcopy(existing)


def render_profile_document(pack: ProfilePack, project_name: str) -> dict[str, Any]:
    document_fragments = [
        fragment for fragment in pack.starter_fragments if fragment.target == "document"
    ]
    if len(document_fragments) > 1:
        raise ValueError(f"Profile {pack.name!r} defines multiple document fragments.")
    if document_fragments:
        document = document_fragments[0].copy_content()
    elif pack.name != "minimal":
        document = render_profile_document(_profile("minimal"), project_name)
        document["nornyx"] = "0.2"
        document["project"]["profile"] = pack.name
        document["project"]["profile_pack"] = {
            "name": pack.name,
            "version": pack.version,
            "status": pack.status,
        }
    else:
        raise ValueError("The minimal built-in profile must define a document fragment.")
    if not isinstance(document, dict):
        raise ValueError(f"Profile {pack.name!r} document fragment must be a mapping.")
    if document_fragments:
        try:
            if document["project"]["name"] != _PROJECT_NAME_SENTINEL:
                raise ValueError("project.name sentinel is missing")
            expected_goal = (
                f"Deliver {_PROJECT_NAME_SENTINEL} through governed AI-assisted engineering."
            )
            if document["intents"][0]["goal"] != expected_goal:
                raise ValueError("intent goal sentinel is missing")
            document["project"]["name"] = project_name
            document["intents"][0]["goal"] = (
                f"Deliver {project_name} through governed AI-assisted engineering."
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"Profile {pack.name!r} has an invalid starter fragment.") from exc
    for fragment in sorted(
        (item for item in pack.starter_fragments if item.target != "document"),
        key=lambda item: (item.target, item.source_index),
    ):
        content = fragment.copy_content()
        document[fragment.target] = (
            _merge_fragment(document[fragment.target], content, path=fragment.target)
            if fragment.target in document
            else content
        )
    return document


def profile_document(profile: str, project_name: str) -> dict[str, Any]:
    return render_profile_document(_profile(profile), project_name)


def write_profile(
    path: str | Path,
    profile: str,
    project_name: str,
    *,
    force: bool = False,
) -> Path:
    target = Path(path)
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists. Use --force to overwrite.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(
            profile_document(profile, project_name),
            sort_keys=False,
            allow_unicode=True,
            width=100,
        ),
        encoding="utf-8",
    )
    return target
