from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class PolicyRuntimeError(Exception):
    pass


CAPABILITY_KINDS = {"tool", "connector", "model"}
EXTERNAL_CAPABILITY_KINDS = {"connector", "model"}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text_list(value: Any) -> list[str]:
    items = _as_list(value)
    return [str(item).strip() for item in items if str(item).strip()]


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _named_mapping(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def _bool_value(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "required"}:
            return True
        if lowered in {"false", "no", "0", "not_required"}:
            return False
    return bool(value)


def _top_level_items(doc: dict[str, Any], block: str) -> list[dict[str, Any]]:
    raw = doc.get(block)
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        items = []
        for name, value in raw.items():
            if isinstance(value, dict):
                item = dict(value)
            else:
                item = {"value": value}
            item.setdefault("name", name)
            items.append(item)
        return items
    return []


def normalize_policy_rules(policy: dict[str, Any] | None) -> dict[str, list[str]]:
    """Normalize both shorthand `rules:` and explicit `deny:`/`require:` policy forms."""
    if not isinstance(policy, dict):
        return {"deny": [], "require": []}

    deny = _text_list(policy.get("deny"))
    require = _text_list(policy.get("require"))
    other = []

    for rule in _text_list(policy.get("rules")):
        lowered = rule.lower()
        if lowered.startswith("deny "):
            deny.append(rule[5:].strip())
        elif lowered.startswith("deny:"):
            deny.append(rule[5:].strip())
        elif lowered.startswith("require "):
            require.append(rule[8:].strip())
        elif lowered.startswith("require:"):
            require.append(rule[8:].strip())
        else:
            other.append(rule)

    return {
        "deny": _dedupe(deny),
        "require": _dedupe(require + other),
    }


def normalize_capabilities(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Return explicit capability declarations.

    Absence of a capability means deny-by-default for tool, connector, and model steps.
    Declared capabilities require human approval unless `approval_required: false` is
    set explicitly.
    """
    capabilities = []
    for index, item in enumerate(_top_level_items(doc, "capabilities"), start=1):
        name = item.get("name") or item.get("id") or item.get("tool") or item.get("connector")
        kind = str(item.get("kind") or item.get("type") or "tool").strip().lower()
        if kind not in CAPABILITY_KINDS:
            kind = "tool"
        if not name:
            name = f"unnamed_{index}"
        allow = _text_list(item.get("allow") or item.get("actions") or item.get("verbs"))
        capabilities.append(
            {
                "id": f"{kind}:{name}",
                "name": str(name),
                "kind": kind,
                "allow": allow or ["*"],
                "approval_required": _bool_value(item.get("approval_required"), default=True),
                "source_index": index,
            }
        )
    return capabilities


def normalize_guardrails(doc: dict[str, Any]) -> list[dict[str, Any]]:
    guardrails = []
    for index, item in enumerate(_top_level_items(doc, "guardrails"), start=1):
        name = item.get("name") or item.get("id") or f"guardrail_{index}"
        validate = _text_list(item.get("validate") or item.get("checks") or item.get("rules"))
        guardrails.append(
            {
                "name": str(name),
                "validate": validate,
                "status": "pending_evidence",
                "reason": "Guardrail declaration is recorded; this local runtime does not execute validators.",
            }
        )
    return guardrails


def _harnesses(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(doc.get("harnesses")) if isinstance(item, dict)]


def select_harness(doc: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    harnesses = _harnesses(doc)
    if not harnesses:
        raise PolicyRuntimeError("No harnesses are defined in the .nyx document")
    if name is None:
        return harnesses[0]
    for harness in harnesses:
        if harness.get("name") == name:
            return harness
    raise PolicyRuntimeError(f"Harness {name!r} is not defined")


def _step_kind(step: dict[str, Any]) -> tuple[str, str | None]:
    for key in ["agent", "tool", "connector", "model", "eval", "evidence"]:
        if key in step:
            return key, str(step.get(key))
    return "unknown", None


def _step_text(step: dict[str, Any], kind: str, ref: str | None) -> str:
    parts = [kind, ref or "", str(step.get("action") or "")]
    parts.extend(str(value) for value in step.values() if isinstance(value, str))
    return " ".join(parts).lower()


def _matches_deny_rule(rule: str, step: dict[str, Any], kind: str, ref: str | None) -> bool:
    lowered_rule = rule.lower()
    text = _step_text(step, kind, ref)

    if "production" in lowered_rule and any(
        token in text for token in ["production", "prod", "deploy", "release"]
    ):
        return True
    if "secret" in lowered_rule and any(token in text for token in ["secret", "token", "credential"]):
        return True
    if "destructive" in lowered_rule and any(
        token in text for token in ["delete", "destroy", "drop", "wipe", "reset", "remove"]
    ):
        return True
    if "connector" in lowered_rule and kind == "connector":
        return True
    if "self_modification" in lowered_rule or "self-modification" in lowered_rule:
        return "self_modification" in text or "self-modification" in text or "modify self" in text
    return False


def _capability_lookup(capabilities: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = {}
    for capability in capabilities:
        lookup[capability["id"]] = capability
        lookup[capability["name"]] = capability
        lookup[f"{capability['kind']}:{capability['name']}"] = capability
    return lookup


def _action_allowed(action: Any, capability: dict[str, Any]) -> bool:
    allowed = {item.lower() for item in capability["allow"]}
    if "*" in allowed:
        return True
    if action is None:
        return "use" in allowed
    return str(action).lower() in allowed


def _has_external_guardrail(guardrails: list[dict[str, Any]]) -> bool:
    required_tokens = {"no_secrets", "no_pii", "schema_valid", "output_schema"}
    declared = {
        item.lower()
        for guardrail in guardrails
        for item in guardrail.get("validate", [])
    }
    return bool(required_tokens & declared)


def _policy_decision(
    index: int,
    step: dict[str, Any],
    kind: str,
    ref: str | None,
    agent_policies: dict[str, str],
    policy_rules: dict[str, dict[str, list[str]]],
) -> dict[str, Any] | None:
    if kind != "agent" or ref is None:
        return None

    policy_name = agent_policies.get(ref)
    rules = policy_rules.get(policy_name or "", {"deny": [], "require": []})
    denied_by = [
        rule for rule in rules["deny"] if _matches_deny_rule(rule, step, kind, ref)
    ]
    if denied_by:
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "blocked",
            "code": "POLICY_DENY_MATCHED",
            "policy": policy_name,
            "denied_by": denied_by,
            "reason": "Agent step matches a deny policy rule.",
        }

    return {
        "index": index,
        "kind": kind,
        "ref": ref,
        "action": step.get("action"),
        "status": "planned",
        "code": "POLICY_RECORDED",
        "policy": policy_name,
        "pending_requirements": [
            {"rule": rule, "status": "pending_evidence"} for rule in rules["require"]
        ],
        "reason": "Agent policy was recorded for local planning; no agent was executed.",
    }


def _capability_decision(
    index: int,
    step: dict[str, Any],
    kind: str,
    ref: str | None,
    capability_map: dict[str, dict[str, Any]],
    guardrails: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if kind not in CAPABILITY_KINDS:
        return None

    if ref is None:
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "blocked",
            "code": "CAPABILITY_REF_MISSING",
            "reason": f"{kind} step must name an explicit capability target.",
        }

    capability = capability_map.get(f"{kind}:{ref}") or capability_map.get(ref)
    if not capability or capability.get("kind") != kind:
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "blocked",
            "code": "CAPABILITY_NOT_DECLARED",
            "reason": f"{kind} use is denied until a matching explicit capability is declared.",
        }

    if not _action_allowed(step.get("action"), capability):
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "blocked",
            "code": "CAPABILITY_ACTION_DENIED",
            "capability": capability["id"],
            "reason": f"Action {step.get('action')!r} is not allowed by the declared capability.",
        }

    if kind in EXTERNAL_CAPABILITY_KINDS and not _has_external_guardrail(guardrails):
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "blocked",
            "code": "GUARDRAIL_REQUIRED_FOR_EXTERNAL_USE",
            "capability": capability["id"],
            "reason": "Model and connector use require an explicit no-secrets/no-PII/schema guardrail.",
        }

    if capability["approval_required"]:
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "requires_human_approval",
            "code": "CAPABILITY_APPROVAL_REQUIRED",
            "capability": capability["id"],
            "reason": "Declared capability requires human approval before use.",
        }

    return {
        "index": index,
        "kind": kind,
        "ref": ref,
        "action": step.get("action"),
        "status": "allowed",
        "code": "CAPABILITY_ALLOWED",
        "capability": capability["id"],
        "reason": "Declared capability permits this planned step.",
    }


def _passive_decision(index: int, step: dict[str, Any], kind: str, ref: str | None) -> dict[str, Any]:
    if kind in {"eval", "evidence"}:
        return {
            "index": index,
            "kind": kind,
            "ref": ref,
            "action": step.get("action"),
            "status": "planned",
            "code": "LOCAL_STEP_RECORDED",
            "reason": "Step is recorded in the local manifest; no runtime action was executed.",
        }
    return {
        "index": index,
        "kind": kind,
        "ref": ref,
        "action": step.get("action"),
        "status": "blocked",
        "code": "UNKNOWN_FLOW_STEP",
        "reason": "Flow step kind is unknown to the policy runtime.",
    }


def _summarize(decisions: list[dict[str, Any]], guardrails: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "allowed": 0,
        "planned": 0,
        "blocked": 0,
        "requires_human_approval": 0,
        "pending_evidence": 0,
    }
    for decision in decisions:
        status = decision.get("status")
        if status in summary:
            summary[status] += 1
        summary["pending_evidence"] += len(decision.get("pending_requirements", []))
    summary["pending_evidence"] += sum(
        1 for guardrail in guardrails if guardrail.get("status") == "pending_evidence"
    )
    return summary


def evaluate_harness_policy(doc: dict[str, Any], harness_name: str | None = None) -> dict[str, Any]:
    harness = select_harness(doc, harness_name)
    policies = _named_mapping(doc.get("policies"))
    policy_rules = {
        name: normalize_policy_rules(policy)
        for name, policy in policies.items()
    }
    agents = _named_mapping(doc.get("agents"))
    agent_policies = {
        name: str(agent.get("policy"))
        for name, agent in agents.items()
        if agent.get("policy")
    }
    capabilities = normalize_capabilities(doc)
    capability_map = _capability_lookup(capabilities)
    guardrails = normalize_guardrails(doc)

    decisions = []
    for index, step in enumerate(_as_list(harness.get("flow")), start=1):
        if not isinstance(step, dict):
            decisions.append(
                {
                    "index": index,
                    "kind": "invalid",
                    "ref": None,
                    "action": None,
                    "status": "blocked",
                    "code": "INVALID_FLOW_STEP",
                    "reason": "Flow step must be a mapping.",
                }
            )
            continue
        kind, ref = _step_kind(step)
        decision = (
            _policy_decision(index, step, kind, ref, agent_policies, policy_rules)
            or _capability_decision(index, step, kind, ref, capability_map, guardrails)
            or _passive_decision(index, step, kind, ref)
        )
        decisions.append(decision)

    return {
        "schema": "nornyx.policy_report.v0.1",
        "harness": str(harness.get("name", "UnnamedHarness")),
        "mode": "safe_local_policy_manifest",
        "default_capability_mode": "deny_unless_declared",
        "safety": {
            "tools_executed": False,
            "connectors_enabled": False,
            "models_called": False,
            "agents_executed": False,
            "arbitrary_commands_allowed": False,
        },
        "policy_rules": policy_rules,
        "capabilities": capabilities,
        "guardrails": guardrails,
        "decisions": decisions,
        "summary": _summarize(decisions, guardrails),
    }


def write_policy_report(report: dict[str, Any], path: str | Path) -> Path:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path
