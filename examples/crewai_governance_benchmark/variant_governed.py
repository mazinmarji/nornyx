"""Variant B — the same application governed by Nornyx.

Identical agents, tasks, model, business callables, inputs, and business rules as
Variant A. The only difference is that each tool is built by the **supported**
CrewAI adapter (``nornyx_agentic_adapters.crewai_adapter.make_governed_tool``)
instead of by ``runtime.plain_tool``, so the wrapped surface is evaluated against
the loaded, lock-verified contract before the shared business callable runs.

Everything here uses the public SPI (``nornyx.agentic``) and the supported
adapter package's public contract (``SurfaceBinding``, ``enforce``). No private
kernel API and no CrewAI internal is touched.

Enforcement order for a governed tool with an additional guard:

    capability check  (adapter, in _GovernedTool._run)
        -> crossing / share check  (enforce, inside the action)
            -> the shared business callable
                -> post-action observations (only after it returns)

Two deliberate, disclosed integration choices
---------------------------------------------
``GovernedInvocationTool`` is the CrewAI tool actually attached to the agent. It
delegates straight into the adapter's own governed ``_run`` — the adapter's
enforcement path is what executes — and adds exactly two things a real
integration needs:

1. **One mission per invocation.** ``EvidenceRecorder`` stamps every event with
   the bound ``decision_at`` and has no monotonic component, so two genuinely
   repeated decisions inside one mission serialize to identical content and the
   evidence validator reports ``AN_EVT_REPLAY``. Minting a fresh mission id per
   tool invocation makes repeated decisions distinguishable, which matters
   because CrewAI retries a failing tool up to three times internally (see
   ``benchmark.md``).
2. **A denial becomes a tool observation.** ``enforce`` raises ``AdapterDenied``
   *before* the wrapped action, which is the fail-closed guarantee and is left
   untouched. The wrapper catches that exception at the CrewAI boundary and
   returns it as text, because an agent framework needs a tool result rather
   than an unhandled exception. The business callable is unreachable either way —
   the side-effect ledger is what proves it, not the exception's shape.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from crewai_governance_benchmark import config  # noqa: F401  (telemetry kill-switch side effect)
from crewai_governance_benchmark.config import (
    APPROVAL_EVIDENCE,
    APPROVAL_REF,
    AS_OF,
    CONTRACT,
    CONTRACT_DIR,
    HUMAN_APPROVER_ROLE,
    LOCK,
    MISSION,
    PRODUCER_ID,
    PRODUCER_TYPE,
)
from crewai_governance_benchmark.ledger import BusinessTool, Ledger
from crewai_governance_benchmark.runtime import FALLBACK_ANSWER, kickoff_single_task, plain_tool
from crewai_governance_benchmark.scenarios import BYPASS, LOAD, SCENARIOS, Scenario, work_callable
from crewai_governance_benchmark.variant_plain import EXPECTED_OUTPUT

from nornyx.agentic import (  # noqa: E402
    ApprovalAssertion,
    Authorizer,
    AuthorizerLoadError,
    DataShareRequest,
    Decision,
    EvaluationContext,
    EvidenceRecorder,
    IdentityResolutionError,
    ZoneCrossingRequest,
    load_authorizer,
)
from crewai.tools import BaseTool  # noqa: E402

# A plain import of the installed distribution, guarded: load_supported_adapter
# raises if the name ever resolves to a source tree under integrations/ again
# (finding F3, resolved by renaming the legacy tree to nornyx_reference_adapters).
_adapters, _crewai_adapter = config.load_supported_adapter()

AdapterDenied = _adapters.AdapterDenied
SurfaceBinding = _adapters.SurfaceBinding
enforce = _adapters.enforce
COVERAGE_INVENTORY = _crewai_adapter.COVERAGE_INVENTORY
FRAMEWORK = _crewai_adapter.FRAMEWORK
METADATA = _crewai_adapter.METADATA
make_governed_tool = _crewai_adapter.make_governed_tool

# A well-formed revision that the contract does not govern (revision mismatch).
FOREIGN_REVISION = "git:" + "0" * 40
# A value that is not a valid immutable revision identifier at all (malformed).
MALFORMED_REVISION = "main"


class MissionCounter:
    """Mints one mission id per governed tool invocation.

    Ids match the runtime-event schema's id pattern
    (``^[A-Za-z0-9][A-Za-z0-9._:-]*$``) and encode the scenario and the
    invocation number, so a retried invocation is a distinct mission rather
    than an apparent replay of the first one.
    """

    def __init__(self, base: str, scenario_id: str) -> None:
        self._base = base
        self._scenario_id = scenario_id
        self.count = 0

    def mint(self) -> str:
        self.count += 1
        return self.current

    @property
    def current(self) -> str:
        return f"{self._base}:{self._scenario_id}:{max(self.count, 1)}"


class GovernedInvocationTool(BaseTool):
    """The CrewAI tool attached to the agent; delegates into the adapter's ``_run``.

    See the module docstring: this mints a per-invocation mission and converts
    the adapter's ``AdapterDenied`` into a tool observation. It never reaches
    around the adapter and never calls the business callable itself.
    """

    def _run(self, *args: Any, **kwargs: Any) -> str:
        governed = self._nornyx_governed_tool  # type: ignore[attr-defined]
        mission: MissionCounter = self._nornyx_mission  # type: ignore[attr-defined]
        object.__setattr__(governed, "_nornyx_mission_id", mission.mint())
        try:
            return governed._run(*args, **kwargs)
        except AdapterDenied as exc:
            decision = exc.decision
            return (
                f"Refused by Nornyx governance [{decision.code.value}]: "
                f"{decision.reason or decision.code.value}"
            )


def governed_invocation_tool(
    *, name: str, description: str, governed_tool: Any, mission: MissionCounter
) -> GovernedInvocationTool:
    tool = GovernedInvocationTool(name=name, description=description)
    object.__setattr__(tool, "_nornyx_governed_tool", governed_tool)
    object.__setattr__(tool, "_nornyx_mission", mission)
    return tool


class TracingRecorder(EvidenceRecorder):
    """An ``EvidenceRecorder`` that also stamps each decision on the ledger.

    This observes the enforcement path; it never alters it. ``record_decision``
    is the SPI's own hook, called by ``enforce`` *before* the wrapped action, so
    stamping here gives a truthful ordering signal rather than an assumed one.
    """

    def __init__(self, authorizer: Authorizer, context: EvaluationContext, *, ledger: Ledger, **kw):
        super().__init__(authorizer, context, **kw)
        self._ledger = ledger
        self.current_scenario = ""
        self.decisions: list[tuple[str, Decision]] = []

    def record_decision(self, decision: Decision, *, mission_id: str) -> None:
        self.decisions.append((self.current_scenario, decision))
        self._ledger.decision(self.current_scenario, decision.code.value, decision.effect.value)
        super().record_decision(decision, mission_id=mission_id)

    # -- read models ---------------------------------------------------------
    def event_count(self) -> int:
        return len(self.stream()["events"])

    def for_scenario(self, scenario_id: str) -> list[Decision]:
        return [d for sid, d in self.decisions if sid == scenario_id]

    def diagnostic(self, scenario_id: str) -> str | None:
        """The decisive code for a scenario: the first non-ALLOW, else ALLOWED."""
        decisions = self.for_scenario(scenario_id)
        if not decisions:
            return None
        for decision in decisions:
            if not decision.allowed:
                return decision.code.value
        return decisions[-1].code.value

    def basis(self, scenario_id: str) -> list[str]:
        return [
            f"{b.kind}:{b.ref}"
            for decision in self.for_scenario(scenario_id)
            for b in decision.basis
        ]


def build_approval(kind: str, subject_revision: str) -> ApprovalAssertion | None:
    """Construct an externally supplied approval record of the requested shape.

    The adapter never creates approvals in a real deployment; these stand in for
    records a human governance owner supplies out of band. Every field except the
    one under test is correct, so each scenario isolates exactly one defect.
    """
    if kind is None:
        return None
    common = dict(
        approval_ref=APPROVAL_REF,
        claimed_approver_ref="human.network_governance_owner",
        claimed_actor_type="human",
        role=HUMAN_APPROVER_ROLE,
        granted=True,
        action_ref="notify_customer",
        subject_revision=subject_revision,
        issued_at="2026-07-16T00:00:00Z",
        expires_at="2026-07-20T00:00:00Z",
        evidence_refs=APPROVAL_EVIDENCE,
    )
    if kind == "valid":
        pass
    elif kind == "ai":
        # A model self-issuing an approval for its own action.
        common.update(claimed_actor_type="model", claimed_approver_ref="model.remediation_llm")
    elif kind == "wrong_action":
        # Genuine, human, unexpired — but scoped to a different governed action.
        common.update(action_ref="issue_refund")
    elif kind == "expired":
        # Correct in every respect except temporal validity at decision_at.
        common.update(expires_at="2026-07-16T00:00:00Z")
    else:  # pragma: no cover - guarded by the scenario matrix
        raise ValueError(f"unknown approval kind {kind!r}")
    return ApprovalAssertion(**common)


def load(contract: Path = CONTRACT, lock: Path = LOCK) -> Authorizer:
    """Load and lock-verify the contract at the pinned validation instant."""
    return load_authorizer(contract, lock, validation_as_of=AS_OF)


def _evaluation_context(authorizer: Authorizer, scenario: Scenario) -> EvaluationContext:
    """The context the *runtime* claims for this scenario.

    Two scenarios deliberately claim a wrong subject revision; every other
    scenario claims the contract's exact revision.
    """
    revision = authorizer.subject_revision
    if scenario.revision_claim == "malformed":
        revision = MALFORMED_REVISION
    elif scenario.revision_claim == "mismatched":
        revision = FOREIGN_REVISION
    return EvaluationContext(decision_at=AS_OF, observed_subject_revision=revision)


def _governed_action(
    scenario: Scenario,
    tool_impl: BusinessTool,
    *,
    authorizer: Authorizer,
    context: EvaluationContext,
    recorder: TracingRecorder,
    identity_ref: str,
    approval: ApprovalAssertion | None,
    mission: MissionCounter,
):
    """Compose the adapter-owned action: extra governed checks, then the work.

    The business callable is reached only after every applicable check returns
    ALLOW. Post-action observations are recorded strictly after it returns, so a
    failure after authorization can never be recorded as a completed action.
    """

    def action(*args: Any, **kwargs: Any) -> str:
        def work() -> str:
            return tool_impl.run(*args, **kwargs)

        if scenario.guard == "crossing":
            source, target = scenario.crossing  # type: ignore[misc]
            result = enforce(
                authorizer,
                ZoneCrossingRequest(identity_ref, source, target, approval),
                context=context,
                recorder=recorder,
                mission_id=mission.current,
                action=work,
            )
            recorder.record_observation(
                "trust_zone_crossed",
                mission_id=mission.current,
                actor_ref=identity_ref,
                source_zone_ref=source,
                target_zone_ref=target,
                # Required by the evidence validator for an external target zone.
                approval_ref=APPROVAL_REF if approval is not None else None,
            )
            return result

        if scenario.guard == "share":
            result = enforce(
                authorizer,
                DataShareRequest(
                    identity_ref,
                    scenario.share_target or "",
                    scenario.share_categories,
                    *(scenario.crossing or ("zone.remediation_internal", "zone.remediation_internal")),
                ),
                context=context,
                recorder=recorder,
                mission_id=mission.current,
                action=work,
            )
            recorder.record_observation(
                "data_shared",
                mission_id=mission.current,
                actor_ref=identity_ref,
                target_ref=scenario.share_target,
                share_categories=list(scenario.share_categories),
            )
            return result

        return work()

    return action


def _drift_probe(out_dir: Path) -> tuple[str, str]:
    """Copy the contract, make a governance-relevant edit, keep the stale lock.

    Returns ``(diagnostic_code, note)``. The lock is deliberately *not*
    regenerated, which is exactly the drift a real repository produces when a
    contract is edited and the lock is not rebuilt.
    """
    probe = out_dir / "drift_probe"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(CONTRACT_DIR, probe)
    contract = probe / CONTRACT.name
    text = contract.read_text(encoding="utf-8")
    # A realistic edit: someone broadens the declared purpose of a delegation and
    # does not regenerate the lock. The contract still validates on its own — only
    # the lock, which binds this exact contract revision, catches it.
    original = "purpose: Delegate bounded refund proposals to the remediation specialist."
    mutated = "purpose: Delegate bounded refund proposals to any remediation identity."
    if original not in text:  # pragma: no cover - guarded by a test
        raise AssertionError("drift probe could not find the delegation purpose to mutate")
    contract.write_text(text.replace(original, mutated, 1), encoding="utf-8")
    try:
        load(contract, probe / LOCK.name)
    except AuthorizerLoadError as exc:
        return exc.code.value, str(exc)
    return "NO_ERROR", "The authorizer loaded a drifted contract — the drift gate did not fire."


def _run_scenario(
    scenario: Scenario,
    ledger: Ledger,
    *,
    authorizer: Authorizer,
    recorder: TracingRecorder,
    out_dir: Path,
) -> dict[str, Any]:
    recorder.current_scenario = scenario.id
    before_events = recorder.event_count()
    # One mission per governed tool invocation; also the invocation counter the
    # result reports, so a retried invocation is visible rather than collapsed.
    invocations = MissionCounter(MISSION, scenario.id)

    def result(outcome: str, note: str, *, diagnostic: str | None, crew_output: str | None) -> dict[str, Any]:
        outputs = ledger.outputs(scenario.id)
        events = recorder.stream()["events"][before_events:]
        return {
            "scenario": scenario.id,
            "outcome": outcome,
            "governed_tool_invocations": invocations.count,
            "diagnostic_code": diagnostic,
            "decision_basis": recorder.basis(scenario.id),
            "business_output": outputs[0] if outputs else None,
            "crew_output": crew_output,
            "event_types": [e["event_type"] for e in events],
            "events_emitted": len(events),
            "events_bound_to_contract_digest": sum(
                1 for e in events if e.get("contract_digest") == authorizer.contract_digest
            ),
            "events_bound_to_lock_digest": sum(
                1 for e in events if e.get("network_lock_digest") == authorizer.network_lock_digest
            ),
            "note": note,
            **ledger.snapshot(scenario.id),
        }

    # -- control-plane drift: no crew can exist -------------------------------
    if scenario.stage == LOAD:
        code, detail = _drift_probe(out_dir)
        return result(
            "load_refused" if code != "NO_ERROR" else "load_succeeded",
            f"The authorizer refused to load the drifted contract: {detail}",
            diagnostic=code,
            crew_output=None,
        )

    tool_impl = BusinessTool(
        name=scenario.tool,
        describe=scenario.tool_description,
        work=work_callable(scenario),
        ledger=ledger,
    ).bind(scenario.id)

    # -- deliberate bypass: an ordinary, ungoverned CrewAI tool ---------------
    if scenario.stage == BYPASS:
        crew_output = kickoff_single_task(
            role=scenario.role,
            tool=plain_tool(scenario.tool, scenario.tool_description, tool_impl.run),
            description=scenario.task,
            expected_output=EXPECTED_OUTPUT,
            final_answer="Completed the requested remediation step.",
        )
        return result(
            "executed_ungoverned",
            "This tool never entered the adapter, so no decision was evaluated and no "
            "evidence was emitted. It is outside the governed boundary by construction.",
            diagnostic="NOT_GOVERNED",
            crew_output=crew_output,
        )

    # -- identity binding, before anything is built ---------------------------
    try:
        identity_ref = authorizer.resolve_identity(FRAMEWORK, scenario.role)
    except IdentityResolutionError as exc:
        return result(
            "binding_refused",
            f"The CrewAI role {scenario.role!r} resolves to no declared identity: {exc}",
            diagnostic=exc.code.value,
            crew_output=None,
        )

    context = _evaluation_context(authorizer, scenario)
    approval = build_approval(scenario.approval, authorizer.subject_revision)
    mission = invocations
    binding = SurfaceBinding(
        surface=f"tool:{scenario.tool}",
        identity_ref=identity_ref,
        capability_ref=scenario.capability_ref or "",
    )
    governed = make_governed_tool(
        name=scenario.tool,
        description=scenario.tool_description,
        binding=binding,
        authorizer=authorizer,
        context=context,
        recorder=recorder,
        mission_id=mission.current,
        action=_governed_action(
            scenario,
            tool_impl,
            authorizer=authorizer,
            context=context,
            recorder=recorder,
            identity_ref=identity_ref,
            approval=approval,
            mission=mission,
        ),
    )

    crew_output = kickoff_single_task(
        role=scenario.role,
        tool=governed_invocation_tool(
            name=scenario.tool,
            description=scenario.tool_description,
            governed_tool=governed,
            mission=mission,
        ),
        description=scenario.task,
        expected_output=EXPECTED_OUTPUT,
        final_answer=(
            FALLBACK_ANSWER
            if scenario.expected_governed_side_effects == 0
            else "Completed the requested remediation step."
        ),
    )

    diagnostic = recorder.diagnostic(scenario.id)
    if ledger.successes(scenario.id):
        outcome = "allowed"
        note = "Authorized at every applicable check; the shared business callable ran once."
    elif ledger.failures(scenario.id):
        outcome = "allowed_then_failed"
        note = (
            "Authorization succeeded and the callable was entered; the work then failed. "
            "No completed side effect and no successful tool_invoked observation."
        )
    else:
        outcome = "denied"
        note = "Refused before the business callable was entered."

    return result(outcome, note, diagnostic=diagnostic, crew_output=crew_output)


def run(
    out_dir: Path, only: tuple[str, ...] | None = None
) -> tuple[dict[str, dict[str, Any]], Ledger, TracingRecorder, Authorizer]:
    """Run every scenario (or just ``only``) through the supported CrewAI adapter."""
    ledger = Ledger()
    authorizer = load()
    context = EvaluationContext(
        decision_at=AS_OF, observed_subject_revision=authorizer.subject_revision
    )
    recorder = TracingRecorder(
        authorizer,
        context,
        ledger=ledger,
        producer_id=PRODUCER_ID,
        producer_version="1.0",
        producer_type=PRODUCER_TYPE,
    )
    selected = [s for s in SCENARIOS if only is None or s.id in only]
    results = {
        s.id: _run_scenario(
            s, ledger, authorizer=authorizer, recorder=recorder, out_dir=out_dir
        )
        for s in selected
    }
    return results, ledger, recorder, authorizer


def adapter_surface() -> dict[str, Any]:
    """The adapter's own declared identity and coverage inventory, verbatim."""
    return {
        "adapter_name": METADATA.adapter_name,
        "adapter_version": METADATA.adapter_version,
        "spi_version": METADATA.spi_version,
        "framework_name": METADATA.framework_name,
        "framework_version_range": METADATA.framework_version_range,
        "nornyx_version_range": METADATA.nornyx_version_range,
        **COVERAGE_INVENTORY.as_dict(),
    }
