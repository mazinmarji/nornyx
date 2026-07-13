from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
import json
from pathlib import Path
from typing import Iterable

from .errors import error
from .loader import (
    _BUNDLED_RESOURCE_CAPABILITY,
    _absolute_without_resolving,
    _load_bundled_pack,
    _reserved_builtin_identity,
    inspect_local_directory,
    load_local_pack,
    reject_remote_or_device_path,
)
from .models import GovernanceModule, PackSourceTier, ProfilePack
from .versions import core_range_allows


SOURCE_TIER_PRIORITY = {"explicit_path": 0, "project": 1, "org": 2, "builtin": 3}


@dataclass(slots=True)
class GovernanceRegistry:
    _profiles_by_id: dict[str, ProfilePack] = field(default_factory=dict)
    _profiles_by_name: dict[str, ProfilePack] = field(default_factory=dict)
    _modules_by_id: dict[str, GovernanceModule] = field(default_factory=dict)
    _modules_by_name: dict[str, GovernanceModule] = field(default_factory=dict)
    _profile_order: list[str] = field(default_factory=list)
    _shadowed: list[tuple[str, str, str]] = field(default_factory=list)

    @classmethod
    def builtins(cls) -> GovernanceRegistry:
        root = resources.files("nornyx") / "profiles_data"
        catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
        if catalog.get("schema") != "nornyx.builtin_profile_catalog.v1":
            raise error("PACK_CATALOG_INVALID", "Bundled profile catalog has an invalid schema.")
        registry = cls()
        expected = list(catalog.get("profiles", []))
        for name in expected:
            resource = root / f"{name}.yaml"
            if not resource.is_file():
                raise error("PACK_CATALOG_INVALID", f"Bundled profile {name!r} is missing.")
            pack = _load_bundled_pack(
                resource,
                capability=_BUNDLED_RESOURCE_CAPABILITY,
            )
            if not isinstance(pack, ProfilePack) or pack.name != name:
                raise error("PACK_CATALOG_INVALID", f"Bundled profile {name!r} does not match its catalog entry.")
            registry._register_profile(pack, trusted_builtin=True)
        if registry.profile_names != tuple(expected):
            raise error("PACK_CATALOG_INVALID", "Bundled profile order is inconsistent.")
        module_names = list(catalog.get("modules", []))
        for name in module_names:
            resource = root / f"module_{name}.yaml"
            if not resource.is_file():
                raise error("PACK_CATALOG_INVALID", f"Bundled module {name!r} is missing.")
            pack = _load_bundled_pack(
                resource,
                capability=_BUNDLED_RESOURCE_CAPABILITY,
            )
            if not isinstance(pack, GovernanceModule) or pack.name != name:
                raise error("PACK_CATALOG_INVALID", f"Bundled module {name!r} is inconsistent.")
            registry._register_module(pack, trusted_builtin=True)
        return registry

    @property
    def profile_names(self) -> tuple[str, ...]:
        return tuple(self._profile_order)

    @property
    def module_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._modules_by_name))

    @property
    def resolution_trace(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {"id": pack_id, "selected_tier": selected, "shadowed_tier": shadowed}
            for pack_id, selected, shadowed in sorted(self._shadowed)
        )

    def _replacement(
        self,
        incoming: ProfilePack | GovernanceModule,
        existing_by_id: ProfilePack | GovernanceModule | None,
        existing_by_name: ProfilePack | GovernanceModule | None,
    ) -> ProfilePack | GovernanceModule | None:
        if existing_by_id is None and existing_by_name is None:
            return None
        if existing_by_id is not existing_by_name:
            raise error(
                "PACK_DUPLICATE_IDENTITY",
                f"Pack identity {incoming.id!r}/{incoming.name!r} collides ambiguously.",
                source_id=incoming.id,
            )
        existing = existing_by_id
        if existing is None:
            raise error("PACK_DUPLICATE_IDENTITY", "Pack identity collision is ambiguous.")
        old_tier = existing.provenance.source_tier
        new_tier = incoming.provenance.source_tier
        if old_tier == new_tier:
            raise error(
                "PACK_DUPLICATE_IDENTITY",
                f"Duplicate pack identity {incoming.id!r}/{incoming.name!r} at {new_tier!r} tier.",
                source_id=incoming.id,
            )
        if SOURCE_TIER_PRIORITY[new_tier] < SOURCE_TIER_PRIORITY[old_tier]:
            self._shadowed.append((incoming.id, new_tier, old_tier))
            return existing
        self._shadowed.append((existing.id, old_tier, new_tier))
        return incoming

    @staticmethod
    def _matches_packaged_builtin(pack: ProfilePack | GovernanceModule) -> bool:
        root = resources.files("nornyx") / "profiles_data"
        try:
            catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
            if isinstance(pack, ProfilePack):
                if pack.name not in catalog.get("profiles", []):
                    return False
                resource = root / f"{pack.name}.yaml"
            else:
                if pack.name not in catalog.get("modules", []):
                    return False
                resource = root / f"module_{pack.name}.yaml"
            canonical = _load_bundled_pack(
                resource,
                capability=_BUNDLED_RESOURCE_CAPABILITY,
            )
        except (OSError, TypeError, ValueError):
            return False
        return canonical == pack

    def _validate_namespace(
        self,
        pack: ProfilePack | GovernanceModule,
        *,
        trusted_builtin: bool,
    ) -> None:
        if pack.provenance.source_tier not in SOURCE_TIER_PRIORITY:
            raise error(
                "PACK_SOURCE_TIER_INVALID",
                f"Unsupported pack source tier {pack.provenance.source_tier!r}.",
                source_id=pack.id,
            )
        if (
            pack.provenance.source_tier == "builtin"
            and not trusted_builtin
            and not self._matches_packaged_builtin(pack)
        ):
            raise error(
                "PACK_SOURCE_TIER_INVALID",
                "The builtin source tier is reserved for packaged catalog entries.",
                source_id=pack.id,
            )
        if (
            pack.provenance.source_tier != "builtin"
            and _reserved_builtin_identity(pack.id)
        ):
            raise error(
                "PACK_RESERVED_NAMESPACE",
                "Only bundled packs may use the nornyx.builtin namespace.",
                source_id=pack.id,
            )

    @staticmethod
    def _cross_kind_collision(
        incoming: ProfilePack | GovernanceModule,
        others: Iterable[ProfilePack | GovernanceModule],
        *,
        incoming_kind: str,
        other_kind: str,
    ) -> None:
        incoming_tokens = {incoming.id, incoming.name}
        unique_others = {(item.id, item.name): item for item in others}
        collisions: list[tuple[tuple[str, ...], ProfilePack | GovernanceModule]] = []
        for other in unique_others.values():
            shared = tuple(sorted(incoming_tokens & {other.id, other.name}))
            if shared:
                collisions.append((shared, other))
        if not collisions:
            return
        shared_tokens = sorted({token for shared, _ in collisions for token in shared})
        identities = sorted(
            [
                (incoming_kind, incoming.id, incoming.name),
                *(
                    (other_kind, other.id, other.name)
                    for _, other in collisions
                ),
            ]
        )
        rendered = ", ".join(
            f"{kind}={pack_id!r}/{name!r}" for kind, pack_id, name in identities
        )
        raise error(
            "PACK_DUPLICATE_IDENTITY",
            f"Global pack identity collision on {shared_tokens!r}: {rendered}.",
            source_id=shared_tokens[0],
        )

    def register_profile(self, profile: ProfilePack) -> None:
        self._register_profile(profile, trusted_builtin=False)

    def _register_profile(
        self,
        profile: ProfilePack,
        *,
        trusted_builtin: bool,
    ) -> None:
        self._validate_namespace(profile, trusted_builtin=trusted_builtin)
        self._cross_kind_collision(
            profile,
            self._modules_by_id.values(),
            incoming_kind="profile",
            other_kind="module",
        )
        existing = self._replacement(
            profile,
            self._profiles_by_id.get(profile.id),
            self._profiles_by_name.get(profile.name),
        )
        if existing is profile:
            return
        if not core_range_allows(profile.compatible_core):
            raise error(
                "PACK_CORE_INCOMPATIBLE",
                f"Profile {profile.id!r} is incompatible with core 1.0.",
                source_id=profile.id,
            )
        if existing is not None:
            self._profiles_by_id.pop(existing.id)
            self._profiles_by_name.pop(existing.name)
            index = self._profile_order.index(existing.name)
            self._profile_order[index] = profile.name
        else:
            self._profile_order.append(profile.name)
        self._profiles_by_id[profile.id] = profile
        self._profiles_by_name[profile.name] = profile

    def register_module(self, module: GovernanceModule) -> None:
        self._register_module(module, trusted_builtin=False)

    def _register_module(
        self,
        module: GovernanceModule,
        *,
        trusted_builtin: bool,
    ) -> None:
        self._validate_namespace(module, trusted_builtin=trusted_builtin)
        self._cross_kind_collision(
            module,
            self._profiles_by_id.values(),
            incoming_kind="module",
            other_kind="profile",
        )
        existing = self._replacement(
            module,
            self._modules_by_id.get(module.id),
            self._modules_by_name.get(module.name),
        )
        if existing is module:
            return
        if not core_range_allows(module.compatible_core):
            raise error(
                "PACK_CORE_INCOMPATIBLE",
                f"Module {module.id!r} is incompatible with core 1.0.",
                source_id=module.id,
            )
        if existing is not None:
            self._modules_by_id.pop(existing.id)
            self._modules_by_name.pop(existing.name)
        self._modules_by_id[module.id] = module
        self._modules_by_name[module.name] = module

    def register_path(
        self,
        path: str | Path,
        *,
        allowed_root: str | Path,
        trust_root: str | Path | None = None,
        source_tier: PackSourceTier = "explicit_path",
    ) -> ProfilePack | GovernanceModule:
        pack = load_local_pack(
            path,
            allowed_root=allowed_root,
            trust_root=trust_root,
            source_tier=source_tier,
        )
        if isinstance(pack, ProfilePack):
            self.register_profile(pack)
        else:
            self.register_module(pack)
        return pack

    def register_directory(
        self,
        root: str | Path,
        *,
        source_tier: PackSourceTier,
        trust_root: str | Path | None = None,
    ) -> tuple[ProfilePack | GovernanceModule, ...]:
        reject_remote_or_device_path(root, code_prefix="PACK", noun="Pack")
        raw_directory = _absolute_without_resolving(Path(root))
        inspected = inspect_local_directory(
            raw_directory,
            allowed_root=raw_directory,
            trust_root=trust_root,
            code_prefix="PACK",
            noun="Pack directory",
        )
        assert inspected is not None
        try:
            candidates = sorted(inspected.glob("*.yaml"), key=lambda item: item.name)
        except OSError as exc:
            raise error(
                "PACK_PATH_INSPECTION_FAILED",
                f"Cannot enumerate pack directory: {exc}",
                path=str(root),
            ) from exc
        loaded = []
        for path in candidates:
            loaded.append(
                self.register_path(
                    path,
                    allowed_root=inspected,
                    trust_root=trust_root,
                    source_tier=source_tier,
                )
            )
        return tuple(loaded)

    def resolve_profile(self, identity: str) -> ProfilePack:
        profile = self._profiles_by_name.get(identity) or self._profiles_by_id.get(identity)
        if profile is None:
            raise error("PACK_NOT_FOUND", f"Unknown profile {identity!r}.", source_id=identity)
        return profile

    def resolve_module(self, identity: str) -> GovernanceModule:
        module = self._modules_by_name.get(identity) or self._modules_by_id.get(identity)
        if module is None:
            raise error("PACK_NOT_FOUND", f"Unknown governance module {identity!r}.", source_id=identity)
        return module

    def dependency_order(
        self,
        profile: ProfilePack | None,
        module_ids: Iterable[str] = (),
    ) -> tuple[GovernanceModule, ...]:
        roots = set(module_ids)
        if profile is not None:
            roots.update(profile.required_modules)
        visiting: list[str] = []
        visited: set[str] = set()
        result: list[GovernanceModule] = []

        def visit(identity: str) -> None:
            module = self.resolve_module(identity)
            if module.id in visited:
                return
            if module.id in visiting:
                cycle = visiting[visiting.index(module.id) :] + [module.id]
                raise error("PACK_DEPENDENCY_CYCLE", "Module dependency cycle: " + " -> ".join(cycle))
            visiting.append(module.id)
            for dependency in sorted(module.dependencies):
                visit(dependency)
            visiting.pop()
            visited.add(module.id)
            result.append(module)

        for identity in sorted(roots):
            visit(identity)
        return tuple(result)

    def selected_conflicts(
        self,
        profile: ProfilePack | None,
        modules: Iterable[GovernanceModule],
    ) -> tuple[tuple[str, str], ...]:
        selected = ([profile] if profile else []) + list(modules)
        selected_ids = {item.id for item in selected}
        conflicts = set()
        for item in selected:
            for conflict in item.conflicts:
                if conflict in selected_ids:
                    conflicts.add(tuple(sorted((item.id, conflict))))
        return tuple(sorted(conflicts))
