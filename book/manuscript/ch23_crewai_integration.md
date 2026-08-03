---
chapter: 23
part: V
title: "CrewAI Integration"
---

# CrewAI Integration

> **Opening scenario.** Northstar's Engineering Platform team begins filling in the wrapper evaluation matrix from Chapter 22, and CrewAI goes first because the Research & Insights pilot already runs on it. The matrix immediately forces an uncomfortable honesty. The framework's documentation describes agents, tasks, crews, delegation between coworkers, and both synchronous and asynchronous tool execution — six or seven surfaces where consequential work happens. The supported adapter's documentation claims exactly one of them. A product manager reads the two documents side by side and asks the question this chapter exists to answer: *"If we adopt this, are we allowed to say 'our CrewAI agents are governed'? And if not, what sentence are we allowed to say?"* The team's answer will end up shorter than the marketing draft and longer than the product manager hoped, and every clause in it will be traceable to a file in the adapter's repository. The closing box of this chapter states it in full.

> **Learning objectives.**
> - Describe CrewAI's execution model — crews, agents, tasks, tools — precisely enough to locate its governable surfaces.
> - Explain how the supported adapter wraps the synchronous tool path through a governed tool class reached by the framework's native executor, and why governance state travels out-of-band.
> - Build one governed tool end to end: contract declarations, authorizer construction, wrapping, an allowed call, a denied call, and the evidence each produces.
> - Read the machine-readable coverage inventory and state what each unsupported surface means operationally, including the fail-closed asynchronous path.
> - Use the repository's bypass test and the A/B governance benchmark — including its declared non-wins — as the model for honest integration claims.
> - Apply the eight assurance questions to the sentence "CrewAI is governed" and produce its defensible replacement.

> **Prerequisites.** Chapter 14 (coverage states, bypass, negative controls — including the bypass test quoted there as Listing 14.2), Chapter 15 (the five-test obligation and the benchmark method of Section 15.7), Chapter 16 (status badges), Chapters 17–20 (contracts, locks, the authorization interface, evidence), and Chapter 22 (the adapter boundary, `SurfaceBinding`, and `enforce`). This chapter applies all of that to one concrete framework and re-teaches none of it.

## 23.1 CrewAI's execution model, briefly and neutrally

CrewAI is an open-source Python framework for orchestrating multiple cooperating agents [@crewai-docs]. Its vocabulary has four load-bearing nouns. An <span class="ix" data-ix="CrewAI!agents">agent</span> is a configured actor with a `role`, a `goal`, and a `backstory`, bound to a language model; the role string doubles as the agent's practical identity within a crew. A <span class="ix" data-ix="CrewAI!tasks">task</span> is a unit of work with a description and an expected output, assigned to an agent and optionally equipped with tools. A <span class="ix" data-ix="CrewAI!crews">crew</span> aggregates agents and tasks under a process — sequential or hierarchical — and `Crew.kickoff()` runs the whole arrangement. A <span class="ix" data-ix="CrewAI!tools">tool</span> is a callable capability exposed to agents, conventionally built by subclassing `crewai.tools.BaseTool`, whose synchronous work lives in a `_run` method and whose asynchronous variant lives in `_arun`. During a task, the framework's executor drives the model through a reason-and-act loop in the style of ReAct [@react]: the model emits an action naming a tool, the executor invokes that tool, and the observation is fed back until the model produces a final answer. CrewAI also provides delegation between "coworker" agents, implemented through tools the framework generates internally.

Two features of this model matter for governance. First, the *only* place where an agent's intent becomes an effect on the world is a tool invocation: agents and tasks produce text until a tool runs. That makes the tool boundary the highest-value interception point per unit of integration effort — Chapter 22's granularity trade-off resolved by the framework's own shape. Second, most of the machinery around that point — the executor's loop, its internal retry of failing tools, the delegation tools it synthesizes — is framework-internal, with no stable public hook. Which surfaces an adapter may claim is therefore decided as much by what CrewAI exposes as by what a governance layer wants.

This book's claims are about what the Nornyx repository pins and tests — CrewAI `1.15.4` exactly, enforced at import as Chapter 22 described **[implemented]** — not about the framework's evolution beyond that version.

## 23.2 The governed surface

The supported adapter **[implemented]** wraps exactly one CrewAI surface: subclassing `BaseTool` and overriding the synchronous `_run`, reached through `Crew.kickoff()`'s native executor. The module docstring says so and says why — CrewAI "exposes no callback or event-bus hook this package uses" (`adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py:11-22`). The resulting <span class="ix" data-ix="governed tool">governed tool</span> is not a patch on the framework: it is an ordinary CrewAI tool that the framework dispatches like any other, whose `_run` happens to be Chapter 22's protected execution sequence. Listing 23.1 is its core.

```python
class _GovernedTool(BaseTool):
    """A ``BaseTool`` whose ``_run`` enforces one declared (identity,
    capability) binding before running the adapter-owned action, exactly once."""

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        binding: SurfaceBinding = self._nornyx_binding
        authorizer: Authorizer = self._nornyx_authorizer
        context: EvaluationContext = self._nornyx_context
        recorder: EvidenceRecorder = self._nornyx_recorder
        mission_id: str = self._nornyx_mission_id
        action: Callable[..., Any] = self._nornyx_action

        request = CapabilityRequest(
            identity_ref=binding.identity_ref, capability_ref=binding.capability_ref
        )
        authorizing: list[str] = []

        def capture(decision: Decision) -> None:
            if decision.allowed:
                authorizing.extend(
                    item.ref for item in decision.basis if item.kind == "delegation"
                )

        result = enforce(
            authorizer, request,
            context=context, recorder=recorder, mission_id=mission_id,
            action=lambda: action(*args, **kwargs),
            on_decision=capture,
        )
        recorder.record_observation(
            "tool_invoked",
            mission_id=mission_id,
            actor_ref=binding.identity_ref,
            capability_ref=binding.capability_ref,
            delegation_ref=authorizing[0] if authorizing else None,
        )
        return result
```

**Listing 23.1 — The governed tool's `_run`.** Abridged from `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py:211-262` (type-comment noise and inline comments removed; otherwise verbatim). Every framework dispatch of this tool becomes one `CapabilityRequest` built solely from the declared binding, one pass through `enforce`, and — only after the action returns — one `tool_invoked` observation. The `capture` hook reads any authorizing delegation from the decision's own basis, never from `args`/`kwargs`, and the recorder drops the `None` so a directly held capability's observation carries no delegation field.

Construction is the factory `make_governed_tool(name, description, binding, authorizer, context, recorder, mission_id, action, args_schema=None)` (`crewai_adapter.py:265-327`). It validates the binding first — a blank field fails closed with `AdapterConfigurationError` before any tool exists — then builds a `_GovernedTool` and attaches the six governance objects with `object.__setattr__`, bypassing the pydantic field machinery that CrewAI tools use for their schemas. That <span class="ix" data-ix="out-of-band state attachment">out-of-band attachment</span> is load-bearing rather than cosmetic: the authorizer, recorder, and binding never appear in the tool's pydantic schema, so they are never serialized as tool arguments and can never be supplied, overridden, or inspected through the executor's argument path. The optional `args_schema` — a pydantic `BaseModel` subclass describing the tool's <span class="ix" data-ix="structured tool arguments">structured inputs</span> — is the one framework-facing opening, and it is bounded: the schema describes inputs only, validated arguments reach `action` only after an allow decision, and a non-`BaseModel` schema fails closed at construction (`crewai_adapter.py:310-316`). The factory's docstring closes the loop on Chapter 22's refusals: "This is NOT arbitrary CrewAI-tool wrapping: it constructs a governed tool from an explicit `action` and (optional) `args_schema`."

Identity crosses the boundary through two small functions. `agent_identity_key(agent)` extracts the agent's `role` string and fails closed on a blank or missing one (`crewai_adapter.py:186-198`); `resolve_identity(authorizer, agent)` passes that key to `Authorizer.resolve_identity("crewai", key)`, and an unknown or ambiguous key raises `IdentityResolutionError` unchanged — a structural failure, not a denial, exactly as Section 22.3 required. This <span class="ix" data-ix="identity mapping!CrewAI role binding">role-to-identity mapping</span> is *binding*, not authentication: the adapter maps a framework name onto a declared identity and verifies nothing about who is actually behind it.

Figure 23.1 places the pieces on lifelines.

<figure class="nx-fig" id="fig-23-1">
  <div class="fig-body">
    <div class="seq">
      <div class="seq-cols" data-cols="CrewAI executor|Governed tool _run|Authorizer|EvidenceRecorder|Action (business callable)"></div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">tool call (native ReAct dispatch)</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">evaluate(CapabilityRequest)</div>
      <div class="msg" data-from="3" data-to="2" data-kind="return">Decision (allow | deny | approval_required)</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record_decision — intents, before any effect</div>
      <div class="msg" data-from="2" data-to="1" data-kind="deny">non-allow: raise AdapterDenied — action never called</div>
      <div class="msg" data-from="2" data-to="5" data-kind="call">allow: action(*args, **kwargs) — exactly once</div>
      <div class="msg" data-from="5" data-to="2" data-kind="return">result</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record_observation("tool_invoked") — after return only</div>
      <div class="msg" data-from="2" data-to="1" data-kind="return">result to the executor</div>
    </div>
  </div>
  <figcaption><b>Figure 23.1 — One governed CrewAI tool call.</b> The executor treats the governed tool as any other tool; everything between the first and last message is invisible to the framework. The deny message and the two calls that follow it are mutually exclusive branches of the same sequence. The teaching purpose is placement: the decision and its record sit strictly between dispatch and effect, and the success observation sits strictly after the effect — the ordering Chapter 22 formalized, drawn on the surface where it actually runs.</figcaption>
</figure>

## 23.3 A worked example: one research tool, governed end to end

We now govern one tool completely, in the shape of Thread A's Atlas — a research agent whose capability set is deliberately small and low-risk. The contract is the repository's own example agentic-network contract, whose declarations happen to be Atlas-shaped: a researcher identity holding a read capability and a proposal capability, and a reviewer identity holding read only. Listing 23.2 shows the blocks that matter.

```yaml
capabilities:
  - name: read_governed_context
    actions: [read_context]
    risk: low
    scope_type: context
    scope_refs: [GovernedNetworkContext]
    delegable: false
    required_gate_refs: []
    required_approval_refs: []
    required_evidence_refs: []

agent_identities:
  - id: identity.researcher.local
    role_ref: Researcher
    identity_class: local_agent
    namespace: local.research
    subject: researcher
    framework_bindings: [{framework: contract_fixture, agent_key: researcher}]
    capability_refs: [read_governed_context, propose_research_finding]
    status: active
    valid_from: "2026-01-01T00:00:00Z"
    expires_at: "2026-08-01T00:00:00Z"
    revocation_refs: []
    authority: non_human
    can_approve: false
```

**Listing 23.2 — The declarations one governed tool binds to.** From `examples/agentic_network.nyx:123-132,143-156`. The capability is a closed declaration — actions, risk, scope, delegability, required gates and evidence — validated against `schemas/agentic_capabilities_v1.schema.json`, whose own description states it "is not a runtime token, authority grant, command, script, credential, or approval." The identity holds capabilities by reference and carries a validity window; the adapter suite adds a `{framework: crewai, agent_key: researcher}` binding to this list so `resolve_identity` can map the CrewAI role.

The wiring is four steps, shown in Listing 23.3 in the form the adapter's own native tests use.

```python
authorizer = load_authorizer(
    "atlas_network.nyx", "nornyx.agentic_network.lock",
    validation_as_of="2026-07-17T10:00:00Z",
)                                       # assured path: validate + lock-verify (Ch. 19)
context = EvaluationContext(
    decision_at="2026-07-17T10:00:00Z",
    observed_subject_revision="git:0123456789abcdef0123456789abcdef01234567",
)
recorder = EvidenceRecorder(authorizer, context, producer_id="atlas-crewai-adapter")

agent = Agent(role="researcher", goal="...", backstory="...", llm=llm)
identity_ref = resolve_identity(authorizer, agent)   # -> "identity.researcher.local"

tool = make_governed_tool(
    name="governed_reader",
    description="Read governed context.",
    binding=SurfaceBinding(
        surface="tool:governed_reader",
        identity_ref=identity_ref,
        capability_ref="read_governed_context",
    ),
    authorizer=authorizer, context=context, recorder=recorder,
    mission_id="GOAL-001",
    action=lambda: "sanitized governed context",
)

task = Task(description="Read the governed context.", expected_output="...",
            agent=agent, tools=[tool])
crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
result = crew.kickoff()
```

**Listing 23.3 — Wiring a governed tool into a native crew.** Verified against source signatures — `load_authorizer` (`nornyx/agentic/authz.py:1166`), `make_governed_tool` (`crewai_adapter.py:265-327`), `resolve_identity` (`crewai_adapter.py:201-208`) — and against the adapter's own end-to-end test `tests/test_crewai_adapter.py:531-590`, which runs this exact shape through a real `Crew.kickoff()` with sockets and subprocesses forbidden. Not executed for this book: CrewAI is not installed in the writing environment. The `Agent`/`Task`/`Crew` construction follows the CrewAI programming model [@crewai-docs].

What does a call produce? The parts of this pipeline below the framework — the enforcement boundary, the authorizer, the recorder — run without CrewAI installed, and Listing 23.4 is their observed output: one allowed invocation of the researcher's read tool, then one denied attempt to exercise `propose_research_finding` under the reviewer identity, which does not hold it.

```text
ALLOW  -> action ran once, returned "sanitized governed context"

DENY   -> AdapterDenied: CAPABILITY_DENIED: Identity 'identity.reviewer.local'
          neither holds nor validly receives 'propose_research_finding'
          at decision_at.
          action ran zero times

event types: ['capability_requested', 'capability_allowed', 'tool_invoked',
              'capability_requested', 'capability_denied']
recorder.validate() -> status: pass, diagnostics: []

events[2] (the success observation):
{
  "event_id": "GOAL-001-0003",
  "event_type": "tool_invoked",
  "mission_id": "GOAL-001",
  "sequence": 3,
  "timestamp": "2026-07-17T10:00:00Z",
  "network_id": "network.research",
  "contract_digest": "sha256:85a5617465afb0fc221f24cc57e7ae2e7d1183224806eb41c51a3d6ea27902a8",
  "network_lock_digest": "sha256:0ddcafe9060163f8b24558ba8a5198f80188ab535e93f23bef3340027cbd7aeb",
  "subject_revision": "git:0123456789abcdef0123456789abcdef01234567",
  "producer": {"type": "framework_adapter", "id": "atlas-crewai-adapter", "version": "1.0"},
  "actor_ref": "identity.researcher.local",
  "capability_ref": "read_governed_context"
}
```

**Listing 23.4 — Observed output of the governed path.** Produced by running the installed core (`nornyx` 1.11.0, SPI 1.2) and the adapter package's framework-neutral modules (`enforce`, `SurfaceBinding` from `adapters/nornyx-agentic-adapters/src/`) against `examples/agentic_network.nyx`, with the authorizer built the way the adapter's own test fixtures build one (`tests/test_crewai_adapter.py:92-95`). The CrewAI layer above this is exercised by the repository's native tests, not re-run here. Read the denied half closely: the stream gains `capability_requested` and `capability_denied` — the denial is *evidence*, not merely an exception — and gains no `tool_invoked`, and the action's side-effect counter stayed at zero.

Every event in the stream carries the contract digest, the lock digest, and the subject revision, which is Chapter 20's envelope binding doing its work: this stream validates against exactly one locked contract revision and would fail validation against any other. Under the framework, the same denied case behaves one way worth knowing about: CrewAI's executor may internally retry a failing tool, so the native denied-kickoff test asserts the invariant rather than a count — every recorded event is a decision intent, `capability_denied` appears at least once, `tool_invoked` never appears, and the side effect never ran (`tests/test_crewai_adapter.py:593-655`). Each internal retry re-enters `_run` and is independently evaluated and recorded, which is Chapter 22's exactly-once locality observed in the wild.

One more allowed-path detail completes the worked example. When an identity holds the capability only by delegation, the allow decision's basis names the authorizing delegation, and the governed tool carries that reference into `tool_invoked` as `delegation_ref` — taken from the decision, never from tool arguments (tests at `tests/test_crewai_adapter.py:342,394,421`; an expired delegation denies and records no success, `:451`). This was the benchmark's finding F2: before the fix, delegation and validatable evidence were mutually exclusive on this path, because the validator's possession check failed a `tool_invoked` that did not state its delegation ground.

> **Case study — Gateway.** The support-refund comparison now has its governed CrewAI arm in code rather than on the whiteboard. The refund callable becomes the `action` of a governed tool bound to `(identity, refund capability)`; the wrapper evaluation matrix's CrewAI rows are filled from the coverage inventory of the next section; and the decision table gains its first measured column: on the wrapped path, a denied refund produces a recorded deny and a ledger that never moved. The bypass row — the same callable invoked directly — stays in the comparison unchanged, because nothing in this section made it go away. Chapter 24 builds the LangGraph arm; Chapter 25 compares them under one conformance frame.

## 23.4 What is not covered, in the adapter's own words

Chapter 14 established that the inventory of uncovered surfaces is part of the interface. Here is the <span class="ix" data-ix="coverage inventory!CrewAI adapter">CrewAI adapter's inventory</span>, quoted from the module constant that ships beside the wrapper **[implemented]**:

```python
COVERAGE_INVENTORY = CoverageInventory(
    entries=(
        SurfaceCoverage(
            surface="tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.WRAPPED,
            reason=(
                "Synchronous tool execution wrapped via a "
                "crewai.tools.BaseTool._run override, reached through "
                "Crew.kickoff()'s native ReAct executor. Covers the sync "
                "_run path only; see async_tool_invocation for the async path."
            ),
        ),
        SurfaceCoverage(
            surface="async_tool_invocation",
            framework=FRAMEWORK,
            status=SurfaceStatus.UNSUPPORTED,
            reason=(
                "M2-B overrides only the synchronous BaseTool._run and does NOT "
                "override _arun. CrewAI's asynchronous tool path (arun/_arun) is "
                "not a governed surface: the inherited BaseTool._arun raises "
                "NotImplementedError, so the wrapped action never executes and no "
                "tool_invoked observation is recorded. Callers must not infer that "
                "synchronous tool coverage extends to async execution."
            ),
        ),
        ...
    )
)
```

**Listing 23.5 — The coverage inventory, first two of six entries.** Verbatim from `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py:118-143`. The reason strings are not comments; they are data, serialized deterministically by `as_dict()` and asserted by tests — including one that checks this exact async reason survives serialization unchanged (`tests/test_crewai_adapter.py:673-687`).

Table 23.1 completes the picture.

| Surface | Status | Declared reason (abridged from `crewai_adapter.py:118-183`) |
|---|---|---|
| `tool_invocation` | **wrapped** | Sync `BaseTool._run` override via `Crew.kickoff()`'s native ReAct executor; sync path only |
| `async_tool_invocation` | unsupported | `_arun` deliberately not overridden; inherited method raises, action never runs, nothing recorded |
| `agent_invocation` | unsupported | No public, stable CrewAI hook fires on agent invocation distinct from tool-level interception |
| `task_invocation` | unsupported | Same rationale as agent invocation |
| `delegation` | unsupported | Coworker delegation is implemented via CrewAI's internally generated tools; wrapping it would depend on undocumented internals |
| `handoff` | unsupported | CrewAI has no distinct handoff concept or public hook separate from delegation |

**Table 23.1 — Six declared surfaces, one wrapped.** The declared coverage of the CrewAI adapter at the snapshot. Read operationally: rows two through six name paths on which a deployment either gets loud failure (row two) or gets ordinary ungoverned CrewAI behavior (rows three through six, where the framework's own mechanisms run without interception). None is an `unwrapped` caller-obligation surface — that third status appears only in the LangGraph inventory, Chapter 24's subject.

The <span class="ix" data-ix="asynchronous tool path!fail-closed">asynchronous row</span> deserves the close reading, because it is the best small example in the repository of *designed* non-coverage. The adapter's authors could have overridden `_arun` to raise a governance error, or to run the sequence on an event loop; they did neither. They left the inherited `BaseTool._arun`, which raises `NotImplementedError`. The consequence is verified against the real framework: calling `arun()` on a governed tool raises, the wrapped action never runs, and the recorder stream stays completely empty — no decision, no observation, nothing (`test_async_arun_fails_closed_and_records_nothing`, `tests/test_crewai_adapter.py:690-715`). The path is uncovered *and it is loud*, which is the distinction Chapter 14 drew between an unsupported surface that fails and one that silently succeeds ungoverned. A deployment that needs asynchronous tools cannot use this adapter and cannot claim it governs them; the inventory converts that from a discovery into a sentence.

The delegation row states a subtler limit. The core engine can evaluate delegation requests, and the governed tool carries delegation grounds into evidence — Section 23.3 showed both. What is unsupported is intercepting *CrewAI's own* coworker-delegation mechanism, which the framework implements through tools it generates internally. A crew configured with `allow_delegation=True` will delegate through machinery no governed tool sits inside. Governed delegation in this integration therefore means Nornyx-declared delegations exercised through governed tools, not framework-native delegation — a distinction a claim register must preserve.

> **Misconception.** *"One wrapped surface out of six means the integration is one-sixth done."* The count measures declared surfaces, not value or completeness. The wrapped surface is the one where intent becomes effect; several unsupported rows are surfaces where CrewAI offers no stable public interception point at all, so the alternative to "unsupported" was not "wrapped" but "wrapped through undocumented internals," which Chapter 22's transparency trade-off rejected because such coverage can vanish in any framework patch. The honest reading of the table is not a progress bar. It is a map of where enforcement stands, where it loudly refuses, and where the framework runs as if the adapter did not exist.

## 23.5 The bypass test and the honesty anchor

The adapter's test suite contains the negative control Chapter 14 reproduced in full (Listing 14.2): the <span class="ix" data-ix="bypass test!CrewAI adapter">bypass test</span> `test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely` (`adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py:506-527`) **[implemented]**. It constructs an action under an identity that does *not* hold the relevant capability — routed through `make_governed_tool` it would be denied — calls the action directly, and asserts that it runs. Its docstring names the principle: "bypassing the adapter bypasses enforcement... This test makes that boundary explicit rather than implicit."

What Chapter 14 treated as a general lesson in claim engineering, this chapter can state as the specific anchor of the CrewAI integration's claim. Everything Sections 23.2 and 23.3 demonstrated — evaluate before effect, deny means zero side effects, evidence that validates — holds *on the wrapped surface*. The bypass test is the executable statement that the wrapped surface is a place the integrator chose to stand, not a chokepoint the framework enforces. It runs on every pull request beside the tests that prove enforcement works, so the suite as a whole asserts both halves of the truthful claim at once: the governed path governs, and the ungoverned path exists. The package README's assurance-boundary section says the same in prose — cooperative Tier 2, "declared, wrapped surfaces only," no gateway, sandbox, or mandatory interception, no agent or approver authentication, evidence as "contract-state binding only, not runtime proof" (`adapters/nornyx-agentic-adapters/README.md:133-150`).

## 23.6 The benchmark: what cooperative governance actually prevented

A wrapped surface, a coverage inventory, and a bypass test establish the boundary. The remaining question is empirical: on the wrapped surface, what does governance *change*? The repository answers with the <span class="ix" data-ix="governance benchmark!CrewAI A/B">A/B governance benchmark</span> whose method Chapter 15 examined; here we read its results as evidence about this specific integration **[implemented]**.

The design, in one sentence: one customer-support and financial-remediation workflow runs twice — Variant A as an ordinary CrewAI application, Variant B with "the *same* agents, tasks, model, inputs, business rules, and business callables, with each tool built by the supported Nornyx CrewAI adapter" (`examples/crewai_governance_benchmark/README.md:7-14`) — across nineteen scenarios, offline, with a scripted deterministic model, exiting nonzero unless every clause of its contract holds and the complete evidence stream validates; the verdict is `GO` or `NO_GO`, with no partial pass. Prevention is proved by the side-effect ledger, not by exceptions: a denied scenario must hold attempts and completions at exactly zero, the k-th business-callable entry must be preceded by a k-th recorded decision, and an authorized action that then fails must produce zero completions and no `tool_invoked`. Figure 23.2 shows the structure.

<figure class="nx-fig" id="fig-23-2">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Scenario inputs<br/>(19, shared)</div><div class="arr">→</div><div class="node">Variant A<br/>plain CrewAI tools</div><div class="arr">→</div><div class="node">Side-effect ledger<br/>+ monotonic clock</div></div>
      <div class="flow"><div class="node">Scenario inputs<br/>(19, shared)</div><div class="arr">→</div><div class="node">Variant B ✋<br/>adapter-built tools</div><div class="arr">→</div><div class="node">Same ledger method<br/>+ decisions + evidence</div></div>
      <div class="flow"><div class="node">Both ledgers</div><div class="arr">→</div><div class="node authority">Benchmark contract<br/>checks + evidence validation</div><div class="arr">→</div><div class="node">GO / NO_GO</div></div>
    </div>
  </div>
  <figcaption><b>Figure 23.2 — The A/B structure.</b> The intended variable is the presence of governance; everything else is shared code. The authoritative element is the machine-checked contract over both ledgers plus full evidence validation, not any human reading of the runs. The teaching purpose is that "what governance prevented" is defined as a ledger difference between arms under identical inputs — a falsifiable quantity — rather than as a count of exceptions raised.</figcaption>
</figure>

What the governed arm prevented, per scenario, is a catalogue of this book's Part II and Part III concepts landing as decision codes on one framework: an undeclared capability (`CAPABILITY_UNKNOWN`), a known capability under the wrong identity (`CAPABILITY_DENIED`), an unmapped runtime identity (`IDENTITY_UNKNOWN`), a high-risk action without approval (`CROSSING_APPROVAL_REQUIRED`), an AI-generated approval (`APPROVAL_NON_HUMAN`), an approval bound to the wrong action (`APPROVAL_ACTION_MISMATCH`), an expired approval (`APPROVAL_STALE`), restricted-data sharing (`SENSITIVE_SHARING`), an undeclared zone crossing (`ZONE_CROSSING_DENIED`), contract/lock drift (`LOCK_STALE`), malformed governance metadata (`REQUEST_MALFORMED`), and a runtime revision mismatch (`REVISION_MISMATCH`). Scenario S14 shows the failure obligation at system scale — an authorized action that fails afterwards yields zero completions and no success observation, across CrewAI's internal three-try retry, each try independently authorized. S16 shows valid bounded delegation flowing into evidence. In Variant A, every one of the prevented effects simply happens.

The benchmark's credibility, though, rests on what it refuses to claim, and three refusals matter here.

**The declared non-wins.** Scenario S15 is a deliberate unwrapped-tool bypass, and it "runs in both variants": the benchmark documentation states that "enforcement is cooperative, and a tool that never enters the adapter is never evaluated." Scenario S18 is a request refused by the application's own business rule in both arms. "S15 and S18 are controls, not wins," and neither counts toward any prevention metric (`examples/crewai_governance_benchmark/README.md:99-103`). S15 is Section 23.5's bypass test promoted to a benchmark scenario; S18 guards against crediting governance for a control the baseline already had. A benchmark without both kinds of control is measuring its own experimental setup.

**The disclosed integration choices.** Variant B documents two departures a real deployment would also face (`variant_governed.py:20-40`). It mints a fresh mission identifier per tool invocation, because the recorder stamps every event with the bound `decision_at` and has no monotonic component, so genuinely repeated identical decisions inside one mission would serialize identically and trip the validator's replay detection (`AN_EVT_REPLAY`) — a real friction of Chapter 20's replay semantics, disclosed rather than papered over. And it catches `AdapterDenied` at the CrewAI boundary and returns the denial as tool text, because a framework needs a tool result rather than an unhandled exception — with the ledger, not the exception's shape, proving the callable was unreachable. That is Chapter 22's failure-semantics resolution, deployed.

**The scoped findings.** Building the benchmark surfaced three real defects — F1, a correctly refused non-human approval produced an unvalidatable stream; F2, the missing `delegation_ref` of Section 23.3; F3, the legacy tree claiming the supported package's import name — all fixed with regression tests, and all scoped by the sentence that matters: "None of them ever affected an enforcement result... What they blocked was a clean *evidence* claim" (`examples/crewai_governance_benchmark/README.md:119-137`). The committed `results/` directory is described as "a snapshot of one run, not a continuously verified claim"; the continuously verified claim is the dedicated CI job, which builds the candidate core and adapter, runs the benchmark offline, and fails on any non-`GO` verdict, any evidence diagnostic, or any silently skipped test (`.github/workflows/ci.yml:293-416`).

For Northstar's product manager, the benchmark supplies the honest middle of the sentence being drafted: on the wrapped tool surface, against this pinned toolchain, cooperative governance measurably prevented twelve classes of ungoverned effect that the identical ungoverned application performed — and the same benchmark demonstrates the path on which it prevents nothing.

## 23.7 The sentence you are allowed to say

> **Assurance boundary.** The eight questions applied to the claim *"CrewAI is governed."* **What exactly is guaranteed?** Not the claim as stated. What is guaranteed **[implemented]**: for tools constructed by `make_governed_tool` and reached through `Crew.kickoff()`'s synchronous native tool path, each dispatch is evaluated against the loaded, lock-verified contract; the decision is recorded before any effect; on any non-allow decision the wrapped callable does not run; a success observation is recorded only after it returns. **Which component enforces it?** The governed tool's own `_run`, cooperatively, inside the agent process — nothing outside that method enforces anything. **What evidence proves it?** A validating runtime-events stream binding every event to the contract digest, lock digest, and subject revision (Listing 23.4); the adapter test suite against real CrewAI 1.15.4 with a zero-skip CI gate; and the benchmark's ledger differences. **What assumptions are required?** The authorizer came from the assured path; every consequential tool was built by the factory; the deployment uses the synchronous path only; the pinned framework version; the role-to-identity binding reflects reality — resolution is not authentication. **How can it be bypassed?** Call the underlying callable directly (tested, `test_crewai_adapter.py:506`; benchmark S15); use `_arun` (fails loudly, governs nothing); act through agent, task, delegation, or handoff surfaces the inventory declares unsupported. **What happens when the enforcing component fails?** Evaluation, recording, and hook errors fail closed before the action; a wrong framework version refuses to import; but a process that never routes through the wrapper fails nothing, because nothing is watching. **Which assurance tier does the claim support?** Tier 2 — cooperative, declared surfaces only, per the package's own boundary statement. **What remains unproven?** That wrapped tools are the only route to any effect; that agents are who their role strings say; that recorded events are true accounts of the world; and everything about the five unsupported surfaces. The defensible sentence, assembled: *"Tool calls reaching CrewAI's synchronous tool path through adapter-built tools are evaluated against the locked contract and recorded before execution, at cooperative Tier 2, on CrewAI 1.15.4 exactly; asynchronous tools fail without executing; all other CrewAI surfaces, and any direct call to the underlying callables, are ungoverned and declared so."*

## Summary

CrewAI's execution model concentrates consequence at one point — the tool invocation — and the supported adapter stands exactly there: a governed `BaseTool` subclass whose synchronous `_run` performs Chapter 22's evaluate-record-execute sequence, built by a factory that validates its declarative binding and attaches all governance state out-of-band so it can never travel as tool arguments. The worked example ran the whole path: contract declarations, an assured authorizer, a wrapped research tool, an allowed call producing `capability_requested`/`capability_allowed`/`tool_invoked` in a stream that validates, and a denied call producing a recorded denial, a typed exception carrying the decision, and zero side effects. The machine-readable coverage inventory declares six surfaces and wraps one; the asynchronous path is deliberately unoverridden and fails without executing or recording, and agent, task, delegation, and handoff surfaces are unsupported for the stated reason that no stable public hook exists. The bypass test anchors the claim's honesty by asserting, on every pull request, that the underlying callable runs ungoverned when called directly. The A/B benchmark measures what the wrapped surface prevented across nineteen scenarios by ledger difference rather than exception counting, declares its bypass and application-rule scenarios as non-wins, discloses its integration frictions, and scopes its three findings as evidence defects rather than enforcement defects. The result is not "CrewAI is governed" but a longer, checkable sentence — which is the only kind worth registering.

- One wrapped surface: sync `BaseTool._run` via the native executor; everything else declared, not implied.
- Governance state rides out-of-band via `object.__setattr__`; `args_schema` describes inputs only, and validated inputs reach the action only after allow.
- Identity mapping is role-string binding with fail-closed resolution — never authentication.
- A denial is evidence: recorded intents, a typed `AdapterDenied`, and an untouched ledger.
- The async path is uncovered but loud; the direct-call path is uncovered and silent, and a test says so.
- Benchmark prevention is a ledger difference under identical inputs; S15 and S18 are controls, not wins.
- The three benchmark findings blocked evidence claims, never enforcement results — a distinction Chapter 3's layers make precise.

## Review questions

1. Why does the governed tool attach its authorizer, recorder, and binding with `object.__setattr__` instead of declaring pydantic fields? Name the specific attack surface the alternative would open through the executor's argument path.
2. A teammate reports "the denied kickoff test asserts a set of event types instead of an exact sequence — that's a weaker test." Explain why the assertion is set-based, what invariant it still pins exactly, and what framework behavior the exact-sequence version would wrongly couple to.
3. The async path records nothing at all — not even a denial. Contrast this with the denied synchronous path, and explain why "fails closed and records nothing" is the correct behavior for an unsupported surface but would be a defect on a wrapped one.
4. CrewAI's coworker delegation is unsupported, yet Section 23.3 showed delegation references in evidence. Reconcile the two statements, and write the one-sentence claim about delegation a Northstar claim register could carry.
5. Scenario S18 is refused by the application's own rule in both arms. What error in the benchmark's prevention metric would counting S18 introduce, and what general lesson does that give for comparing a governed system against its baseline?
6. Using the closing assurance-boundary box, identify which of the eight questions the original sentence "CrewAI is governed" answers *incorrectly* rather than merely incompletely, and justify the distinction.

## Exercises

1. **Reproduce the governed path without the framework.** Using the repository at the snapshot, build an authorizer from `examples/agentic_network.nyx` as the adapter test fixtures do, then drive `enforce` with an allowed and a denied `CapabilityRequest`, record a `tool_invoked` after the allowed action, and validate the stream. Compare your event-type sequence and validation status with Listing 23.4, then explain in three sentences which parts of the CrewAI claim your reproduction did and did not exercise.
2. **Write the missing denial test.** For a governed tool of your own design (any callable), write the denial test to Chapter 14's standard: assert the decision code, assert the recorded `capability_requested`/`capability_denied` pair, and assert zero side effects — then break your own wrapper by swapping the record and execute lines and confirm which assertion catches it.
3. **Draft the claim register rows.** Using Table 23.1 and the closing box, write one claim-register row per declared surface for a Northstar deployment of this adapter: claim, enforcing component, evidence, tier, residual risk. The `tool_invocation` row should cite the tests and benchmark scenarios that support it; each unsupported row should state what a deployer must do (avoid, accept, or externally control) and what evidence would show the surface was never used.

## Further reading

- [@crewai-docs] — the framework's own account of crews, agents, tasks, tools, and processes; read the tool documentation against Table 23.1 to practice locating a coverage boundary in vendor prose.
- [@react] — the reason-and-act pattern behind the executor loop the governed tool sits inside; useful for seeing why the tool boundary is where intent becomes effect.
- [@schneider-enforceable] — the formal frame for why the wrapped surface, and only the wrapped surface, supports an enforcement claim.
- [@owasp-agentic] — tool misuse and control-circumvention threats catalogued for agentic systems; maps directly onto the unsupported rows of Table 23.1.
- [@nornyx-repo] — `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py` (337 lines) and `examples/crewai_governance_benchmark/` are the primary sources of this chapter; the benchmark's `REVIEWER_QUICKSTART.md` is a model of how to hand a sceptical reviewer the means of verification.
