from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
import json
from pathlib import Path
from typing import Iterable

from .errors import error
from .loader import _reject_symlink_components, load_bundled_pack, load_local_pack
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
            pack = load_bundled_pack(resource)
            if not isinstance(pack, ProfilePack) or pack.name != name:
                raise error("PACK_CATALOG_INVALID", f"Bundled profile {name!r} does not match its catalog entry.")
            registry.register_profile(pack)
        if registry.profile_names != tuple(expected):
            raise error("PACK_CATALOG_INVALID", "Bundled profile order is inconsistent.")
        module_names = list(catalog.get("modules", []))
        for name in module_names:
            resource = root / f"module_{name}.yaml"
            if not resource.is_file():
                raise error("PACK_CATALOG_INVALID", f"Bundled module {name!r} is missing.")
            pack = load_bundled_pack(resource)
            if not isinstance(pack, GovernanceModule) or pack.name != name:
                raise error("PACK_CATALOG_INVALID", f"Bundled module {name!r} is inconsistent.")
            registry.register_module(pack)
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

    def register_profile(self, profile: ProfilePack) -> None:
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
        raw_directory = Path(root)
        inspection_root = raw_directory if trust_root is None else Path(trust_root)
        _reject_symlink_components(
            raw_directory,
            inspection_root,
            code_prefix="PACK",
            noun="Pack",
        )
        if not raw_directory.is_dir():
            raise error(
                "PACK_NOT_FOUND",
                "Pack directory does not exist.",
                path=str(root),
            )
        loaded = []
        for path in sorted(raw_directory.glob("*.yaml"), key=lambda item: item.name):
            loaded.append(
                self.register_path(
                    path,
                    allowed_root=raw_directory,
                    trust_root=inspection_root,
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
