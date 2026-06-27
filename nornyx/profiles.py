from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any
import yaml

BASE_PROFILE_NAMES = [
    "minimal",
    "standard",
    "ai_coding",
    "regulated",
    "legacy_upgrade",
    "nornyx_language",
]

DOMAIN_PROFILE_NAMES = [
    "ai_coding",
    "agentic_repo_harness",
    "telecom_ops",
    "business_ops",
    "ai_governance",
    "finance_ops",
]

PROFILE_CONFORMANCE_LEVEL = "v0.6"

PROFILE_NAMES = [
    "minimal",
    "standard",
    "ai_coding",
    "regulated",
    "legacy_upgrade",
    "nornyx_language",
    "agentic_repo_harness",
    "telecom_ops",
    "business_ops",
    "ai_governance",
    "finance_ops",
]

GENERAL_CORE_CONCEPTS = [
    "Intent",
    "Agent",
    "Policy",
    "Eval",
    "Approval",
    "Evidence",
    "Context",
    "Artifact",
    "Graph",
    "Goal",
    "Budget",
    "Trace",
]

PROFILE_NON_GOALS = [
    "live agent runtime",
    "tool execution",
    "MCP/A2A live connectors",
    "LLM/model calls",
    "automatic approvals",
    "self-modification",
    "production deployment",
    "enterprise/regulated GOAL-100 promotion",
    "general-purpose programming language features",
]

PROFILE_STABILITY: dict[str, dict[str, Any]] = {
    "ai_coding": {
        "v1_readiness": "stable_candidate",
        "migration": "Existing ai_coding starters remain compatible; add profile_pack metadata when upgrading.",
    },
    "agentic_repo_harness": {
        "v1_readiness": "stable_candidate",
        "migration": "Use when harness gates and local evidence flows are first-class.",
    },
    "telecom_ops": {
        "v1_readiness": "profile_candidate",
        "migration": "Keep telecom concepts in profile metadata until adapter conformance matures.",
    },
    "business_ops": {
        "v1_readiness": "profile_candidate",
        "migration": "Keep business workflow concepts in profile metadata until adapter conformance matures.",
    },
    "ai_governance": {
        "v1_readiness": "stable_candidate",
        "migration": "Use when policy, eval, approval, and evidence are the primary adoption path.",
    },
    "finance_ops": {
        "v1_readiness": "optional_candidate",
        "migration": "Use only when finance operations governance is explicitly needed.",
    },
}

PROFILE_COMPATIBILITY_MATRIX: dict[str, dict[str, list[str]]] = {
    "ai_coding": {
        "compatible_with": ["agentic_repo_harness", "ai_governance"],
        "requires_review_with": ["telecom_ops", "business_ops", "finance_ops"],
        "conflicts_with": [],
    },
    "agentic_repo_harness": {
        "compatible_with": ["ai_coding", "ai_governance"],
        "requires_review_with": ["telecom_ops", "business_ops", "finance_ops"],
        "conflicts_with": [],
    },
    "telecom_ops": {
        "compatible_with": ["ai_governance"],
        "requires_review_with": ["ai_coding", "agentic_repo_harness", "business_ops", "finance_ops"],
        "conflicts_with": [],
    },
    "business_ops": {
        "compatible_with": ["ai_governance"],
        "requires_review_with": ["ai_coding", "agentic_repo_harness", "telecom_ops", "finance_ops"],
        "conflicts_with": [],
    },
    "ai_governance": {
        "compatible_with": ["ai_coding", "agentic_repo_harness", "telecom_ops", "business_ops", "finance_ops"],
        "requires_review_with": [],
        "conflicts_with": [],
    },
    "finance_ops": {
        "compatible_with": ["ai_governance"],
        "requires_review_with": ["ai_coding", "agentic_repo_harness", "telecom_ops", "business_ops"],
        "conflicts_with": [],
    },
}

DOMAIN_PROFILE_PACKS: dict[str, dict[str, Any]] = {
    "ai_coding": {
        "name": "ai_coding",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Govern AI-assisted software engineering in a repository.",
        "domain": "ai_engineering",
        "required_blocks": ["project", "intents", "contexts", "agents", "policies", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "approvals", "budgets", "traces", "evals"],
        "graph_node_kinds": ["profile", "context", "agent", "policy", "approval", "budget", "goal"],
        "validation_rules": [
            "profile metadata remains optional",
            "generated starter document passes nornyx check",
            "contract references declared graph nodes, approvals, and budgets",
            "evidence and approval semantics remain required for goals",
        ],
        "conformance": PROFILE_STABILITY["ai_coding"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
    "agentic_repo_harness": {
        "name": "agentic_repo_harness",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Describe repo harness governance, local quality gates, and evidence collection.",
        "domain": "agentic_repo_control_plane",
        "required_blocks": ["project", "contexts", "agents", "harnesses", "policies", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "approvals", "budgets", "traces", "evals"],
        "graph_node_kinds": ["profile", "context", "agent", "policy", "harness", "approval", "budget", "goal"],
        "validation_rules": [
            "harnesses are plans and gates, not arbitrary command execution",
            "contract references declared graph nodes, approvals, and budgets",
            "profile-specific harness defaults do not weaken core policy checks",
        ],
        "conformance": PROFILE_STABILITY["agentic_repo_harness"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
    "telecom_ops": {
        "name": "telecom_ops",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Represent telecom operations governance as optional profile metadata.",
        "domain": "telecom_operations",
        "required_blocks": ["project", "intents", "contexts", "policies", "approvals", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "budgets", "traces", "evals"],
        "graph_node_kinds": ["profile", "context", "policy", "approval", "budget", "goal"],
        "validation_rules": [
            "telecom concepts stay under optional profile metadata",
            "no telecom adapter or production network action is enabled",
            "profile contracts still require approval, budget, and evidence references",
        ],
        "conformance": PROFILE_STABILITY["telecom_ops"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
    "business_ops": {
        "name": "business_ops",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Represent business operations governance as optional profile metadata.",
        "domain": "business_operations",
        "required_blocks": ["project", "intents", "contexts", "policies", "approvals", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "budgets", "traces", "evals"],
        "graph_node_kinds": ["profile", "context", "policy", "approval", "budget", "goal"],
        "validation_rules": [
            "business operations concepts stay under optional profile metadata",
            "no business adapter or production workflow action is enabled",
            "profile contracts still require approval, budget, and evidence references",
        ],
        "conformance": PROFILE_STABILITY["business_ops"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
    "ai_governance": {
        "name": "ai_governance",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Represent AI governance policy, eval, approval, and evidence requirements.",
        "domain": "ai_governance",
        "required_blocks": ["project", "intents", "policies", "evals", "approvals", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "budgets", "traces", "contexts"],
        "graph_node_kinds": ["profile", "policy", "eval", "approval", "budget", "goal"],
        "validation_rules": [
            "governance rules remain explicit policy/eval/evidence declarations",
            "no automatic approval or compliance certification is implied",
            "profile contracts still require approval, budget, and evidence references",
        ],
        "conformance": PROFILE_STABILITY["ai_governance"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
    "finance_ops": {
        "name": "finance_ops",
        "version": "v0.3",
        "core_surface": "v0.2",
        "status": "optional_profile",
        "purpose": "Represent finance operations governance where a project explicitly needs it.",
        "domain": "finance_operations_optional",
        "required_blocks": ["project", "intents", "contexts", "policies", "approvals", "budgets", "evidence", "goals"],
        "recommended_blocks": ["graph", "contracts", "traces", "evals"],
        "graph_node_kinds": ["profile", "context", "policy", "approval", "budget", "goal"],
        "validation_rules": [
            "finance_ops remains opt-in and is not a mandatory core concept",
            "no trading, payments, or production financial action is enabled",
            "profile contracts still require approval, budget, and evidence references",
        ],
        "conformance": PROFILE_STABILITY["finance_ops"],
        "non_goals": PROFILE_NON_GOALS,
        "core_concepts": GENERAL_CORE_CONCEPTS,
    },
}


def profile_pack(profile: str) -> dict[str, Any]:
    if profile not in DOMAIN_PROFILE_PACKS:
        raise ValueError(
            f"Unknown v0.3 domain profile {profile!r}. Expected one of: {', '.join(DOMAIN_PROFILE_NAMES)}"
        )
    return deepcopy(DOMAIN_PROFILE_PACKS[profile])


def profile_pack_catalog() -> list[dict[str, Any]]:
    return [profile_pack(name) for name in DOMAIN_PROFILE_NAMES]


def profile_compatibility_matrix() -> dict[str, dict[str, list[str]]]:
    return deepcopy(PROFILE_COMPATIBILITY_MATRIX)


def validate_profile_conformance() -> list[str]:
    issues = validate_profile_pack_catalog()
    required_safety_non_goals = set(PROFILE_NON_GOALS)
    allowed_readiness = {"stable_candidate", "profile_candidate", "optional_candidate"}

    for name in DOMAIN_PROFILE_NAMES:
        pack = DOMAIN_PROFILE_PACKS.get(name, {})
        conformance = pack.get("conformance")
        if not isinstance(conformance, dict):
            issues.append(f"{name}: missing conformance metadata")
            continue
        readiness = conformance.get("v1_readiness")
        if readiness not in allowed_readiness:
            issues.append(f"{name}: invalid v1_readiness {readiness!r}")
        if not _is_metadata_string(conformance.get("migration")):
            issues.append(f"{name}: migration guidance is required")
        if set(pack.get("non_goals", [])) != required_safety_non_goals:
            issues.append(f"{name}: profile non_goals must match the shared safety boundary")
        if pack.get("core_concepts") != GENERAL_CORE_CONCEPTS:
            issues.append(f"{name}: core_concepts must remain the general Nornyx core list")

    matrix = PROFILE_COMPATIBILITY_MATRIX
    matrix_names = set(matrix)
    expected_names = set(DOMAIN_PROFILE_NAMES)
    if matrix_names != expected_names:
        issues.append("profile compatibility matrix must cover every domain profile exactly")
    for name, row in matrix.items():
        if name not in expected_names:
            continue
        for field in ["compatible_with", "requires_review_with", "conflicts_with"]:
            values = row.get(field)
            if not isinstance(values, list):
                issues.append(f"{name}: compatibility matrix {field} must be a list")
                continue
            unknown = sorted(set(values) - expected_names)
            if unknown:
                issues.append(f"{name}: compatibility matrix {field} has unknown profiles {unknown}")
            if name in values:
                issues.append(f"{name}: compatibility matrix {field} must not include itself")
        overlap = set(row.get("compatible_with", [])) & set(row.get("conflicts_with", []))
        if overlap:
            issues.append(f"{name}: compatible/conflict overlap {sorted(overlap)}")

    return issues


def profile_conformance_report() -> dict[str, Any]:
    return {
        "schema": "nornyx.profile_conformance.v0.6",
        "status": "conformant" if not validate_profile_conformance() else "needs_review",
        "conformance_level": PROFILE_CONFORMANCE_LEVEL,
        "core_boundary": "Profiles are optional overlays and do not add mandatory core concepts.",
        "profiles": profile_pack_catalog(),
        "compatibility_matrix": profile_compatibility_matrix(),
        "issues": validate_profile_conformance(),
    }


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
    allowed_core_concepts = set(GENERAL_CORE_CONCEPTS)

    for name in DOMAIN_PROFILE_NAMES:
        pack = DOMAIN_PROFILE_PACKS.get(name)
        if not pack:
            issues.append(f"missing domain profile pack: {name}")
            continue
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
        if not isinstance(required_blocks, list) or not {"project", "policies", "evidence", "goals"}.issubset(required_blocks):
            issues.append(f"{name}: required_blocks must include project, policies, evidence, and goals")
        validation_rules = pack.get("validation_rules", [])
        if not isinstance(validation_rules, list) or not validation_rules:
            issues.append(f"{name}: validation_rules must be a non-empty list")
        non_goals = set(pack.get("non_goals", []))
        if not {"live agent runtime", "automatic approvals", "production deployment"}.issubset(non_goals):
            issues.append(f"{name}: non_goals must block runtime, automatic approvals, and production deployment")

    return issues


def _is_metadata_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def profile_document(profile: str, project_name: str) -> dict[str, Any]:
    if profile not in PROFILE_NAMES:
        raise ValueError(f"Unknown profile {profile!r}. Expected one of: {', '.join(PROFILE_NAMES)}")
    pack = DOMAIN_PROFILE_PACKS.get(profile)

    base: dict[str, Any] = {
        "nornyx": "0.2" if pack else "0.1",
        "project": {
            "name": project_name,
            "profile": profile,
            "purpose": "Generated by nornyx init. Edit this file as the project source of truth.",
        },
        "intents": [
            {"name": "ProjectIntent", "goal": f"Deliver {project_name} through governed AI-assisted engineering."}
        ],
        "contexts": [
            {
                "name": "RepoContext",
                "include": ["README.md", "docs/**/*.md", "src/**/*", "tests/**/*"],
                "exclude": [".env", "secrets/**", "generated/**", "**/__pycache__/**"],
                "authority": ["manifest.json", "docs/spec/**/*.md", "tests/**/*", "chat_notes/**"],
                "budget": {"max_tokens": 32000, "reserve_output_tokens": 4000},
            }
        ],
        "agents": [
            {"name": "Architect", "role": "Design bounded goals and acceptance criteria", "skills": ["SpecDesign"], "policy": "SafeRepoEdit"},
            {"name": "Builder", "role": "Implement scoped changes with tests", "skills": ["PatchBuild"], "policy": "SafeRepoEdit"},
            {"name": "Reviewer", "role": "Review design, security, tests, and evidence", "skills": ["Review"], "policy": "SafeReview"},
        ],
        "skills": [
            {"name": "SpecDesign", "purpose": "Turn goals into spec and acceptance criteria", "input": ["Goal"], "output": ["Spec"]},
            {"name": "PatchBuild", "purpose": "Produce small coherent patches", "input": ["Spec"], "output": ["PatchDiff"]},
            {"name": "Review", "purpose": "Review patch, tests, policy, and evidence", "input": ["PatchDiff"], "output": ["ReviewReport"]},
        ],
        "policies": [
            {"name": "SafeRepoEdit", "deny": ["secrets_to_llm", "production_write_without_approval"], "require": ["tests_if_code_changed", "evidence_if_goal_completed"]},
            {"name": "SafeReview", "require": ["risk_check", "evidence_check", "approval_before_merge"]},
        ],
        "harnesses": [
            {
                "name": "StandardDevHarness",
                "context": "RepoContext",
                "flow": [
                    {"agent": "Architect", "action": "plan"},
                    {"agent": "Builder", "action": "implement"},
                    {"tool": "tests", "action": "run"},
                    {"agent": "Reviewer", "action": "review"},
                    {"tool": "evidence", "action": "pack"},
                ],
                "gates": ["tests.pass", "policy.pass", "evidence.exists", "approval.before_merge"],
            }
        ],
        "evals": [{"name": "RegressionEval", "metrics": ["tests_pass", "no_policy_regression", "evidence_complete"]}],
        "evidence": {"required": ["patch.diff", "test_report.json", "risk_update.md", "approval_log.json"]},
        "goals": [
            {
                "id": "GOAL-001",
                "title": "Bootstrap governed project baseline",
                "phase": "v0.1",
                "goal": "Create initial Nornyx-governed development baseline.",
                "scope": ["project.nyx", "README.md", "docs/qa/evidence/GOAL-001/"],
                "non_goals": ["production deployment", "external connector enablement"],
                "validation": ["nornyx check project.nyx", "pytest -q"],
                "evidence": "docs/qa/evidence/GOAL-001/",
                "approval": "required before merge or release",
                "stop_rules": [
                    "stop on security ambiguity",
                    "stop after 3 failed validation attempts",
                ],
            }
        ],
    }

    if pack:
        base["project"]["profile_pack"] = {
            "name": pack["name"],
            "version": pack["version"],
            "core_surface": pack["core_surface"],
            "status": pack["status"],
        }
        base["experimental"] = {
            "profile_pack": {
                "name": pack["name"],
                "domain": pack["domain"],
                "required_blocks": pack["required_blocks"],
                "recommended_blocks": pack["recommended_blocks"],
                "graph_node_kinds": pack["graph_node_kinds"],
                "validation_rules": pack["validation_rules"],
                "non_goals": pack["non_goals"],
            }
        }
        base["approvals"] = [
            {"name": "HumanOwner", "required_for": ["merge", "policy_change", "connector_write"]}
        ]
        base["budgets"] = [
            {"name": "DefaultBudget", "max_tokens": 100000, "max_tool_calls": 40, "max_runtime_minutes": 30}
        ]
        base["graph"] = {
            "nodes": [
                {"id": f"profile.{profile}", "kind": "profile", "ref": profile},
                {"id": "context.repo", "kind": "context", "ref": "RepoContext"},
                {"id": "agent.builder", "kind": "agent", "ref": "Builder"},
                {"id": "policy.safe_repo_edit", "kind": "policy", "ref": "SafeRepoEdit"},
                {"id": "approval.human_owner", "kind": "approval", "ref": "HumanOwner"},
                {"id": "budget.default", "kind": "budget", "ref": "DefaultBudget"},
                {"id": "evidence.patch", "kind": "evidence", "ref": "patch.diff"},
                {"id": "goal.bootstrap", "kind": "goal", "ref": "GOAL-001"},
            ],
            "edges": [
                {"from": f"profile.{profile}", "to": "context.repo", "relation": "scopes_context"},
                {"from": "context.repo", "to": "agent.builder", "relation": "authorizes_context_for"},
                {"from": "policy.safe_repo_edit", "to": "agent.builder", "relation": "governs"},
                {"from": "agent.builder", "to": "evidence.patch", "relation": "must_produce"},
                {"from": "approval.human_owner", "to": "goal.bootstrap", "relation": "gates"},
                {"from": "budget.default", "to": "goal.bootstrap", "relation": "bounds"},
            ],
        }
        base["contracts"] = [
            {
                "name": f"{profile}_profile_contract",
                "nodes": [
                    f"profile.{profile}",
                    "context.repo",
                    "agent.builder",
                    "policy.safe_repo_edit",
                    "approval.human_owner",
                    "budget.default",
                    "evidence.patch",
                    "goal.bootstrap",
                ],
                "approval": "HumanOwner",
                "budget": "DefaultBudget",
            }
        ]
        base["goals"][0]["phase"] = "v0.3"
        base["goals"][0]["scope"] = [
            "project.nyx",
            f"profiles/{profile}.yaml",
            "docs/qa/evidence/GOAL-001/",
        ]
        base["goals"][0]["non_goals"] = [
            "production deployment",
            "external connector enablement",
            "domain-specific runtime execution",
        ]

    if profile in {"ai_coding", "regulated", "nornyx_language"} or pack:
        base["guardrails"] = [{"name": "NoSecretOutput", "validate": ["no_secrets", "schema_valid"]}]
        base["traces"] = [{"name": "AgentTrace", "standard": "OpenTelemetry.GenAI", "capture": ["llm_call", "tool_call", "policy_decision", "approval_event"]}]
        base.setdefault("budgets", [{"name": "DefaultBudget", "max_tokens": 100000, "max_tool_calls": 40, "max_runtime_minutes": 30}])

    if profile in {"regulated", "nornyx_language"}:
        base["approvals"] = [{"name": "HumanOwner", "required_for": ["merge", "production_write", "policy_change", "connector_write"]}]
        base["supply_chain"] = {"require": ["dependency_scan", "signed_tools_where_available", "sbom_for_release"]}

    return base


def write_profile(path: str | Path, profile: str, project_name: str, *, force: bool = False) -> Path:
    p = Path(path)
    if p.exists() and not force:
        raise FileExistsError(f"{p} already exists. Use --force to overwrite.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(profile_document(profile, project_name), sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return p
