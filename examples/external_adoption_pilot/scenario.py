"""The adoption scenario, executed *inside* the clean environment.

Standalone by construction: the runner copies this single file into a
temporary directory and runs it with the clean environment's interpreter, so it
imports nothing from its own package and nothing from any checkout. Its imports
are the standard library and the installed distributions under test.

The scenario is a three-variant A/B/C over one identical action, driven through
CrewAI's own ReAct executor via ``Crew.kickoff()``:

``ungoverned``
    A plain ``crewai.tools.BaseTool``. The action runs. No authorization is
    evaluated and no evidence exists — not because anything failed, but because
    nothing was ever asked. This is the baseline an adopter starts from.
``governed_authorized``
    The same action wrapped by ``make_governed_tool`` for an identity that
    holds the capability. The action still runs, and now a decision and an
    evidence stream exist. Governance permits what is authorized.
``governed_unauthorized``
    The same wrapper, for an identity that does not hold the capability. The
    action does not run at all, and the denial is recorded.

The third variant is the one that matters, and the second is what keeps the
first honest: a control that only ever blocks is not governance, it is an
outage.

Everything is offline. The scripted model is a local ``BaseLLM`` subclass that
returns fixed strings; no API key, no network, no external model service.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import sysconfig
import traceback
from typing import Any

# CrewAI reads these at import time, so they must be set before it is imported.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

RESULT_SENTINEL = "PILOT_RESULT"

ADAPTER_DISTRIBUTION = "nornyx-agentic-adapters"
CORE_DISTRIBUTION = "nornyx"
FRAMEWORK_DISTRIBUTION = "crewai"

#: Governance contract shipped as package data by the adapter distribution.
#: The pilot reuses it rather than authoring one, so a first run needs no
#: contract of your own; substitute your own `.nyx` once the shape is clear.
FIXTURE_PACKAGE = "nornyx_agentic_adapters.conformance.fixtures"
FIXTURE_NAME = "conformance_network.nyx"

#: A fixed instant inside the fixture's validity window. Never `now()`, so two
#: runs of this pilot produce identical evidence and can be diffed.
DECISION_AT = "2026-07-17T10:00:00Z"
MISSION_ID = "GOAL-001"
PRODUCER_ID = "nornyx-external-adoption-pilot"
PRODUCER_TYPE = "synthetic_harness"

#: Identities and capabilities declared by the bundled contract. `researcher`
#: holds the read capability; `reviewer` does not hold the propose capability —
#: that asymmetry is what makes an A/B/C possible without editing the contract.
RESEARCHER = "identity.researcher.local"
REVIEWER = "identity.reviewer.local"
READ_CAPABILITY = "read_governed_context"
PROPOSE_CAPABILITY = "propose_research_finding"


class ScenarioFailure(Exception):
    """Raised by a stage; carries the failure class it maps to."""

    def __init__(self, failure_class: str, detail: str, **evidence: object) -> None:
        super().__init__(detail)
        self.failure_class = failure_class
        self.detail = detail
        self.evidence = evidence


# --------------------------------------------------------------------------
# Pure helpers -- importable without the distributions installed
# --------------------------------------------------------------------------


def normalize(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def path_is_inside(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> bool:
    target = Path(normalize(path))
    base = Path(normalize(root))
    return target == base or base in target.parents


def leakage_findings(
    origins: dict[str, str], *, site_packages: str, forbidden_roots: list[str]
) -> list[dict[str, str]]:
    """Positive evidence about where each artifact actually resolved from."""
    findings: list[dict[str, str]] = []
    for label, origin in sorted(origins.items()):
        if not path_is_inside(origin, site_packages):
            findings.append(
                {"label": label, "origin": origin, "reason": "outside site-packages"}
            )
            continue
        for root in forbidden_roots:
            if path_is_inside(origin, root):
                findings.append(
                    {
                        "label": label,
                        "origin": origin,
                        "reason": f"inside a repository root ({root})",
                    }
                )
                break
    return findings


def governance_problems(variants: dict[str, dict[str, Any]]) -> list[str]:
    """Did governance actually do what the pilot claims? Pure, so it is testable.

    Every check is a comparison between variants rather than an absolute
    assertion, because the claim being made is comparative: the *same* action,
    governed and ungoverned, behaves differently.
    """
    problems: list[str] = []
    ungoverned = variants.get("ungoverned", {})
    allowed = variants.get("governed_authorized", {})
    denied = variants.get("governed_unauthorized", {})

    # Baseline: the action really is reachable when nothing governs it.
    # Without this, a denial proves nothing -- the action might simply not work.
    if ungoverned.get("executions") != 1:
        problems.append(
            f"ungoverned baseline executed {ungoverned.get('executions')} times, expected 1; "
            "without a working baseline a denial demonstrates nothing"
        )
    if ungoverned.get("authorizations"):
        problems.append("the ungoverned variant somehow evaluated an authorization")
    if ungoverned.get("decision_events"):
        problems.append("the ungoverned variant somehow produced decision evidence")

    # Governance permits what is authorized.
    if allowed.get("executions") != 1:
        problems.append(
            f"governed+authorized executed {allowed.get('executions')} times, expected 1; "
            "a control that blocks authorized work is an outage, not governance"
        )
    if "capability_allowed" not in (allowed.get("decision_events") or []):
        problems.append("no capability_allowed event on the authorized path")

    # Governance prevents what is not authorized. The load-bearing check.
    if denied.get("executions") != 0:
        problems.append(
            f"governed+unauthorized executed the action {denied.get('executions')} times; "
            "fail-closed did not hold"
        )
    if "capability_denied" not in (denied.get("decision_events") or []):
        problems.append("no capability_denied event on the denied path")
    requested = (denied.get("decision_events") or []).count("capability_requested")
    refused = (denied.get("decision_events") or []).count("capability_denied")
    if requested != refused:
        problems.append(
            f"{requested} requests did not pair with {refused} denials; "
            "CrewAI may retry, but every request must still be answered"
        )
    if denied.get("observation_events"):
        problems.append(
            f"a success observation was recorded on denial: {denied['observation_events']}"
        )
    return problems


# --------------------------------------------------------------------------
# Scenario execution
# --------------------------------------------------------------------------


class _Counter:
    def __init__(self) -> None:
        self.count = 0

    def run(self, value: str) -> str:
        self.count += 1
        return value


class _CountingAuthorizer:
    """Wraps an Authorizer to observe how many evaluations really happened."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.evaluations = 0

    def evaluate(self, request: Any, *, context: Any) -> Any:
        self.evaluations += 1
        return self._inner.evaluate(request, context=context)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)


def _import_all() -> dict[str, Any]:
    try:
        import importlib.metadata as md

        import yaml

        import nornyx_agentic_adapters as naa
        from nornyx.agentic import (
            Authorizer,
            EvaluationContext,
            EvidenceRecorder,
            GovernanceRegistry,
            build_agentic_network_lock,
            compose_document_governance,
        )
    except Exception as exc:  # noqa: BLE001
        raise ScenarioFailure(
            "REGISTRY_INSTALL_FAILED",
            f"the installed distributions are not importable: {exc!r}",
            traceback=traceback.format_exc(),
        ) from exc

    try:
        import crewai
        from crewai.tools import BaseTool

        from nornyx_agentic_adapters.binding import SurfaceBinding
        from nornyx_agentic_adapters.crewai_adapter import make_governed_tool, resolve_identity
    except Exception as exc:  # noqa: BLE001
        raise ScenarioFailure(
            "FRAMEWORK_EXTRA_UNAVAILABLE",
            (
                f"the [crewai] extra did not deliver a usable framework: {exc!r}. "
                "The base package can be healthy while the extra is not."
            ),
            traceback=traceback.format_exc(),
        ) from exc

    return {
        "md": md,
        "yaml": yaml,
        "naa": naa,
        "crewai": crewai,
        "BaseTool": BaseTool,
        "SurfaceBinding": SurfaceBinding,
        "make_governed_tool": make_governed_tool,
        "resolve_identity": resolve_identity,
        "Authorizer": Authorizer,
        "EvaluationContext": EvaluationContext,
        "EvidenceRecorder": EvidenceRecorder,
        "GovernanceRegistry": GovernanceRegistry,
        "build_agentic_network_lock": build_agentic_network_lock,
        "compose_document_governance": compose_document_governance,
    }


def _check_versions(mods: dict[str, Any], expected: dict[str, str]) -> dict[str, str]:
    md = mods["md"]
    resolved: dict[str, str] = {}
    for distribution in (CORE_DISTRIBUTION, ADAPTER_DISTRIBUTION, FRAMEWORK_DISTRIBUTION):
        try:
            resolved[distribution] = md.version(distribution)
        except Exception as exc:  # noqa: BLE001
            failure = (
                "FRAMEWORK_EXTRA_UNAVAILABLE"
                if distribution == FRAMEWORK_DISTRIBUTION
                else "REGISTRY_INSTALL_FAILED"
            )
            raise ScenarioFailure(
                failure, f"no installed metadata for {distribution}: {exc!r}"
            ) from exc

    for distribution, want in expected.items():
        got = resolved.get(distribution)
        if got != want:
            failure = (
                "FRAMEWORK_EXTRA_UNAVAILABLE"
                if distribution == FRAMEWORK_DISTRIBUTION
                else "INSTALLED_VERSION_MISMATCH"
            )
            raise ScenarioFailure(
                failure,
                f"{distribution} resolved to {got!r}, expected {want!r}",
                resolved=resolved,
            )
    return resolved


def _build_governance(mods: dict[str, Any]) -> dict[str, Any]:
    """Compose, lock and load the bundled contract using public core API only."""
    from importlib import resources

    try:
        resource = resources.files(FIXTURE_PACKAGE).joinpath(FIXTURE_NAME)
        text = resource.read_text(encoding="utf-8")
        origin = str(Path(str(resource)).resolve())
    except Exception as exc:  # noqa: BLE001
        raise ScenarioFailure(
            "REGISTRY_INSTALL_FAILED",
            (
                f"the bundled governance contract did not resolve from the "
                f"installed distribution: {exc!r}"
            ),
        ) from exc

    try:
        document = mods["yaml"].safe_load(text)
        composition = mods["compose_document_governance"](
            document, registry=mods["GovernanceRegistry"].builtins()
        )
        lock = mods["build_agentic_network_lock"](document, composition)
        authorizer = mods["Authorizer"](document, composition, lock)
    except Exception as exc:  # noqa: BLE001
        raise ScenarioFailure(
            "SCENARIO_EXECUTION_FAILED",
            f"the bundled contract did not compose, lock and load: {exc!r}",
            traceback=traceback.format_exc(),
        ) from exc

    return {
        "authorizer": authorizer,
        "contract_origin": origin,
        "subject_revision": authorizer.subject_revision,
    }


def _scripted_llm(mods: dict[str, Any], tool_name: str | None, final_answer: str) -> Any:
    """A local, offline model that drives CrewAI's real ReAct executor.

    Its call count is what proves a variant went through the framework rather
    than calling the wrapper directly -- a direct call would leave it at zero.
    """
    base = mods["crewai"].BaseLLM

    class _ScriptedLLM(base):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__(model="nornyx-adoption-pilot-offline")
            self.calls = 0

        def call(self, messages: Any, tools: Any = None, callbacks: Any = None,
                 available_functions: Any = None, **kwargs: Any) -> str:
            self.calls += 1
            if tool_name is not None and self.calls == 1:
                return (
                    "Thought: I must use the tool.\n"
                    f"Action: {tool_name}\n"
                    "Action Input: {}"
                )
            return f"Thought: I now can give a great answer\nFinal Answer: {final_answer}"

        def supports_function_calling(self) -> bool:
            return False

        def supports_stop_words(self) -> bool:
            return False

        def get_context_window_size(self) -> int:
            return 8192

    return _ScriptedLLM()


def _kickoff(mods: dict[str, Any], role: str, llm: Any, tool: Any) -> Any:
    crewai = mods["crewai"]
    agent = crewai.Agent(
        role=role,
        goal="Demonstrate governed behavior on a shared action.",
        backstory="Deterministic offline adoption-pilot agent.",
        allow_delegation=False,
        verbose=False,
        llm=llm,
    )
    task = crewai.Task(
        description="Use the available tool as instructed.",
        expected_output="A short answer.",
        agent=agent,
        tools=[tool],
    )
    crew = crewai.Crew(agents=[agent], tasks=[task], process=crewai.Process.sequential)
    return agent, crew.kickoff()


def _events(recorder: Any) -> tuple[list[str], list[str]]:
    decision = {
        "capability_requested", "capability_allowed", "capability_denied",
        "delegation_requested", "delegation_accepted", "delegation_rejected",
        "approval_requested", "approval_granted", "approval_rejected",
        "policy_violation",
    }
    types = [event["event_type"] for event in recorder.stream()["events"]]
    return (
        [item for item in types if item in decision],
        [item for item in types if item not in decision],
    )


def _variant_ungoverned(mods: dict[str, Any]) -> dict[str, Any]:
    counter = _Counter()
    BaseTool = mods["BaseTool"]

    class _PlainTool(BaseTool):  # type: ignore[misc, valid-type]
        name: str = "context_reader"
        description: str = "Read context."

        def _run(self, *args: Any, **kwargs: Any) -> str:
            return counter.run("ungoverned read complete")

    llm = _scripted_llm(mods, "context_reader", "ungoverned run complete")
    _, result = _kickoff(mods, "researcher", llm, _PlainTool())
    return {
        "id": "ungoverned",
        "description": "A plain CrewAI tool. Nothing asks whether this is allowed.",
        "governed": False,
        "identity": None,
        "capability": None,
        "executions": counter.count,
        "authorizations": 0,
        "decision_events": [],
        "observation_events": [],
        "model_calls": llm.calls,
        "framework_result_contains_final_answer": "ungoverned run complete" in str(result),
    }


def _variant_governed(
    mods: dict[str, Any],
    governance: dict[str, Any],
    *,
    variant_id: str,
    role: str,
    identity: str,
    capability: str,
    tool_name: str,
    final_answer: str,
) -> dict[str, Any]:
    counter = _Counter()
    counting = _CountingAuthorizer(governance["authorizer"])
    context = mods["EvaluationContext"](
        decision_at=DECISION_AT, observed_subject_revision=governance["subject_revision"]
    )
    recorder = mods["EvidenceRecorder"](
        counting, context, producer_id=PRODUCER_ID, producer_type=PRODUCER_TYPE
    )
    tool = mods["make_governed_tool"](
        name=tool_name,
        description="Read context.",
        binding=mods["SurfaceBinding"](f"tool:{tool_name}", identity, capability),
        authorizer=counting,
        context=context,
        recorder=recorder,
        mission_id=MISSION_ID,
        action=lambda: counter.run("governed read complete"),
    )
    llm = _scripted_llm(mods, tool_name, final_answer)
    agent, result = _kickoff(mods, role, llm, tool)
    decision_events, observation_events = _events(recorder)

    resolved_identity = None
    try:
        resolved_identity = mods["resolve_identity"](counting, agent)
    except Exception:  # noqa: BLE001 - reported, not fatal
        resolved_identity = None

    return {
        "id": variant_id,
        "description": (
            "The same action, wrapped by make_governed_tool for an identity that "
            + ("holds" if variant_id.endswith("authorized") and "un" not in variant_id
               else "does not hold")
            + " the capability."
        ),
        "governed": True,
        "identity": identity,
        "resolved_identity": resolved_identity,
        "capability": capability,
        "executions": counter.count,
        "authorizations": counting.evaluations,
        "decision_events": decision_events,
        "observation_events": observation_events,
        "model_calls": llm.calls,
        "framework_result_contains_final_answer": final_answer in str(result),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External adoption pilot scenario.")
    parser.add_argument("--expect-adapter", required=True)
    parser.add_argument("--expect-crewai", required=True)
    # Core is recorded, not pinned. The adapter declares `nornyx>=1.10,<2`, so
    # a new core minor is a supported resolution -- asserting an exact core
    # version here would break this pilot the day 1.12.0 publishes, which is
    # the opposite of what an adoption check should do.
    parser.add_argument("--expect-core", default=None)
    parser.add_argument("--forbidden-root", action="append", default=[])
    # CrewAI's executor writes rich console output to stdout and does not always
    # terminate it with a newline, so an envelope printed there can end up
    # appended to framework output rather than on a line of its own. The file is
    # the reliable channel; the printed line is kept for humans running this
    # module directly.
    parser.add_argument("--envelope", type=Path, default=None)
    args = parser.parse_args(argv)

    def emit(envelope: dict[str, Any], code: int) -> int:
        payload = json.dumps(envelope, sort_keys=True, default=str)
        if args.envelope is not None:
            args.envelope.write_text(payload, encoding="utf-8")
        print(f"{RESULT_SENTINEL} {payload}")
        return code

    site_packages = str(Path(sysconfig.get_paths()["purelib"]).resolve())
    forbidden = [str(Path(root).resolve()) for root in args.forbidden_root]

    try:
        mods = _import_all()
        expected = {
            ADAPTER_DISTRIBUTION: args.expect_adapter,
            FRAMEWORK_DISTRIBUTION: args.expect_crewai,
        }
        if args.expect_core:
            expected[CORE_DISTRIBUTION] = args.expect_core
        versions = _check_versions(mods, expected)
        governance = _build_governance(mods)

        origins = {
            "nornyx_agentic_adapters": str(Path(mods["naa"].__file__).resolve()),
            "crewai": str(Path(mods["crewai"].__file__).resolve()),
            "governance_contract": governance["contract_origin"],
        }
        findings = leakage_findings(
            origins, site_packages=site_packages, forbidden_roots=forbidden
        )
        if findings:
            raise ScenarioFailure(
                "SOURCE_TREE_LEAKAGE_DETECTED",
                "one or more artifacts did not resolve from the installed distributions",
                findings=findings,
            )

        try:
            variants = [
                _variant_ungoverned(mods),
                _variant_governed(
                    mods, governance,
                    variant_id="governed_authorized",
                    role="researcher",
                    identity=RESEARCHER,
                    capability=READ_CAPABILITY,
                    tool_name="governed_reader",
                    final_answer="governed run complete",
                ),
                _variant_governed(
                    mods, governance,
                    variant_id="governed_unauthorized",
                    role="reviewer",
                    identity=REVIEWER,
                    capability=PROPOSE_CAPABILITY,
                    tool_name="proposer",
                    final_answer="should never be reached",
                ),
            ]
        except ScenarioFailure:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScenarioFailure(
                "SCENARIO_EXECUTION_FAILED",
                f"a scenario variant did not complete: {exc!r}",
                traceback=traceback.format_exc(),
            ) from exc

        by_id = {variant["id"]: variant for variant in variants}
        problems = governance_problems(by_id)
        if problems:
            raise ScenarioFailure(
                "GOVERNANCE_EXPECTATION_UNMET",
                "; ".join(problems),
                variants=by_id,
            )

        record = {
            "pilot": "nornyx-external-adoption-pilot",
            "environment": {
                "python": sys.version.split()[0],
                "executable": sys.executable,
                "site_packages": site_packages,
                "working_directory": os.getcwd(),
            },
            "distributions": versions,
            "import_origins": origins,
            "governance_contract": {
                "source": "package data of nornyx-agentic-adapters",
                "package": FIXTURE_PACKAGE,
                "name": FIXTURE_NAME,
                "origin": governance["contract_origin"],
                "subject_revision": governance["subject_revision"],
                "decision_at": DECISION_AT,
                "mission_id": MISSION_ID,
            },
            "variants": variants,
            "governance_delta": {
                "action_reachable_ungoverned": by_id["ungoverned"]["executions"],
                "action_permitted_when_authorized": (
                    by_id["governed_authorized"]["executions"]
                ),
                "action_prevented_when_unauthorized": (
                    by_id["governed_unauthorized"]["executions"] == 0
                ),
                "evidence_absent_ungoverned": not by_id["ungoverned"]["decision_events"],
                "evidence_present_when_governed": bool(
                    by_id["governed_authorized"]["decision_events"]
                ),
            },
            "safety": {
                "external_model_service_called": {
                    "value": False,
                    "kind": "structural_constant",
                    "means": "the pilot ships a scripted local model and calls no service",
                },
                "scripted_in_process_model_called": {
                    "value": any(v["model_calls"] > 0 for v in variants),
                    "kind": "observed",
                    "means": "measured; CrewAI's executor drives the scripted local model",
                },
                "credentials_loaded": False,
                "external_connectors_used": False,
            },
        }
    except ScenarioFailure as failure:
        return emit(
            {
                "status": "fail",
                "failure_class": failure.failure_class,
                "detail": failure.detail,
                "evidence": failure.evidence,
            },
            1,
        )

    return emit(
        {"status": "pass", "failure_class": None, "detail": "", "record": record}, 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
