# Findings against the audited revision

Audited base SHA: `d4026a1a06789453de86ea60cd4a78c31da87da2` (`main`)
Packages: `nornyx` 1.8.0 (SPI 1.0), `nornyx-agentic-adapters` 0.1.0, `crewai` 1.15.4

Two defects in the audited packages stop the benchmark's runtime-event stream from
validating. Both are reproduced by **mandatory** benchmark scenarios, both are
reproducible without any benchmark code, and neither affects an enforcement
result: every authorization decision in the run is correct, and every prevented
callable stayed at zero side effects. What they block is a clean *evidence*
claim.

Nothing in these packages was modified. The benchmark reports the full-stream
validation status as `fail` and lists both diagnostics; it never suppresses them.

---

## F1 — A correctly refused non-human approval cannot appear in a valid stream

**Severity:** blocks evidence validation for any run that refuses an AI approval.
**Component:** `nornyx/agentic/authz.py` (emitter) × `nornyx/agentic_evidence.py` (validator)
**Reproduced by:** scenario **S07** (mandatory scenario 7, "AI-generated or non-human approval")

### What happens

`Authorizer._approval` correctly refuses an approval whose `claimed_actor_type`
is not `human`, and emits an `approval_rejected` event intent that mirrors the
*claimed* actor type back into the record:

```python
# nornyx/agentic/authz.py:616
_intent("approval_rejected", actor_ref=actor, approval_ref=a.approval_ref,
        approver={"role": a.role, "actor_type": a.claimed_actor_type})
```

`validate_runtime_events` then rejects that same event, because it requires a
human approver on *every* approval-outcome event, `approval_granted` and
`approval_rejected` alike:

```python
# nornyx/agentic_evidence.py:660
if event_type in {"approval_granted", "approval_rejected"}:
    approver = event.get("approver")
    if isinstance(approver, Mapping):
        if approver.get("actor_type") != "human":
            diagnostics.append(_diagnostic("AN_EVT_APPROVAL_NON_HUMAN", ...))
```

The engine is right to record who actually claimed the approval, and the
validator is right to insist that a *granted* approval be human. The two rules
collide on rejections: the more faithfully the engine records the refusal, the
more certainly the stream fails to validate.

### Minimal reproduction (no benchmark code)

```python
from nornyx.agentic import (load_authorizer, EvaluationContext, EvidenceRecorder,
                            ZoneCrossingRequest, ApprovalAssertion)

authorizer = load_authorizer(CONTRACT, LOCK, validation_as_of="2026-07-17T00:00:00Z")
ctx = EvaluationContext("2026-07-17T00:00:00Z", authorizer.subject_revision)
recorder = EvidenceRecorder(authorizer, ctx, producer_id="repro")

ai_approval = ApprovalAssertion(
    approval_ref="agentic_network_authority", claimed_approver_ref="model.x",
    claimed_actor_type="model", role="network_governance_owner", granted=True,
    action_ref="notify_customer", subject_revision=authorizer.subject_revision,
    issued_at="2026-07-16T00:00:00Z", expires_at="2026-07-20T00:00:00Z",
    evidence_refs=("approval_record", "agentic_network_contract_review"))

decision = authorizer.evaluate(
    ZoneCrossingRequest("identity.remediation_agent", "zone.remediation_internal",
                        "zone.customer_channel", ai_approval), context=ctx)
recorder.record_decision(decision, mission_id="M1")
```

Observed:

```
decision: APPROVAL_NON_HUMAN            <- correct refusal
emitted approver: {'role': 'network_governance_owner', 'actor_type': 'model'}
validator diagnostics: ['AN_EVT_APPROVAL_NON_HUMAN']
```

### Why it matters

Refusing an AI-issued approval is one of the product's headline guarantees. As
shipped, exercising that guarantee makes the evidence stream unvalidatable — so
the strongest governance outcome is the one that cannot be evidenced.

### Suggested direction (not applied here)

Scope the validator rule to `approval_granted` only, and let `approval_rejected`
carry the claimed actor type — a rejection recording a non-human claimant is the
evidence, not a violation. Alternatively give the rejected event a distinct field
(`claimed_approver`) so the `approver` slot keeps its "this actor approved"
meaning.

---

## F2 — A delegated capability's `tool_invoked` event cannot validate

**Severity:** blocks evidence validation for any governed tool using a delegated capability.
**Component:** `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`
**Reproduced by:** scenario **S16** ("valid bounded delegation")

### What happens

The adapter records its post-action observation with only the actor and the
capability:

```python
# crewai_adapter.py:239 (_GovernedTool._run)
recorder.record_observation(
    "tool_invoked", mission_id=mission_id,
    actor_ref=binding.identity_ref, capability_ref=binding.capability_ref)
```

The validator applies the same possession rule to `capability_allowed` *and*
`tool_invoked`, and its delegation check fails closed when no `delegation_ref` is
present:

```python
# nornyx/agentic_evidence.py:279
def delegated_capability(actor, capability, delegation_ref, timestamp) -> bool:
    if not isinstance(delegation_ref, str):
        return False
```

So when an identity holds a capability *only* by delegation, the decision is
correctly ALLOW and `capability_allowed` correctly carries
`delegation_ref`, but the adapter's `tool_invoked` drops it and the event is
reported as a capability the actor does not hold.

### Minimal reproduction (no benchmark code)

```python
decision = authorizer.evaluate(
    CapabilityRequest("identity.remediation_agent", "propose_refund"), context=ctx)
recorder.record_decision(decision, mission_id="M2")
# exactly what the adapter records after the action:
recorder.record_observation("tool_invoked", mission_id="M2",
    actor_ref="identity.remediation_agent", capability_ref="propose_refund")
```

Observed:

```
decision: ALLOWED  basis: [('delegation', 'delegation.refund_proposal')]
capability_allowed carries delegation_ref: delegation.refund_proposal
tool_invoked        carries delegation_ref: None
validator diagnostics: [('AN_EVT_CAPABILITY_NOT_HELD', 'events[2].capability_ref')]
```

### Why it matters

Bounded, revocable delegation is a core reason to declare an agent network at
all. Any governed tool exercising a delegated capability emits an event that
cannot validate, so delegation and validatable evidence are currently mutually
exclusive on the supported CrewAI path.

### Suggested direction (not applied here)

Carry the authorizing delegation from the decision into the observation — the
`Decision` already exposes it as `DecisionBasis(kind="delegation", ref=...)`, so
`_GovernedTool._run` can pass `delegation_ref` to `record_observation` without
any new API.

---

## F3 — The legacy `integrations/` tree shadows the supported adapter package

**Severity:** the supported and legacy adapters cannot coexist in one Python process.
**Component:** `integrations/nornyx_agentic_adapters/` × `adapters/nornyx-agentic-adapters`
**Found by:** running this benchmark's tests in a full-suite run rather than alone.

### What happens

Both trees claim the import name `nornyx_agentic_adapters`:

| Path | What it is |
|---|---|
| `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/` | the supported, installed distribution (ADR-0039 M2-A/M2-B) |
| `integrations/nornyx_agentic_adapters/` | the legacy, unpackaged reference kernel (ADR-0037) |

Any process that puts `integrations/` on `sys.path` gets the legacy tree for that
name — for everything that follows, not just its own imports. Several of this
repository's own test modules do exactly that (`tests/test_agentic_integrations.py`,
`tests/test_agentic_crewai_native.py`, `tests/test_agentic_support_example.py`,
`tests/test_authoring_assistant_roadmap.py`), and they sort alphabetically ahead
of anything using the supported package.

### Reproduction

```python
import sys, importlib
sys.path.insert(0, "integrations")
import nornyx_agentic_adapters as pkg
print(pkg.__file__)                       # -> integrations/nornyx_agentic_adapters/__init__.py
from nornyx_agentic_adapters import AdapterDenied
# ImportError: cannot import name 'AdapterDenied' from 'nornyx_agentic_adapters'
```

`AdapterDenied`, `SurfaceBinding`, `enforce`, and `crewai_adapter` exist only in
the installed distribution; the legacy tree exposes `governance_kernel`,
`crewai_adapter` (a different one), `langgraph_adapter`, and `local_harness`.

### Why it matters

The `nornyx-agentic-adapters` README already lists "Legacy `integrations/`
compatibility shim — Pending". This is the concrete failure that pending item
has to resolve: today a consumer that installs the supported package and also
has this repository's `integrations/` directory reachable will silently get the
wrong module, and the failure surfaces as a confusing `ImportError` on a public
name rather than as a clear conflict.

### How this benchmark works around it

`config.load_supported_adapter()` resolves the name explicitly: if the legacy
tree currently owns it, the benchmark temporarily lifts `integrations/` off
`sys.path`, imports the installed distribution, and then **restores `sys.path`
and every `nornyx_agentic_adapters` entry in `sys.modules` exactly as it found
them**, so the repo's legacy-dependent tests are unaffected. This is a consumer
workaround, not a fix — `test_supported_adapter_wins_over_the_legacy_same_named_tree`
pins the behavior.

### Suggested direction (not applied here)

Rename the legacy tree's package (for example to `nornyx_reference_adapters`),
or move it under a distinct namespace, so the supported distribution owns the
name unambiguously.

---

## Non-defect observations

These are not bugs, but they shaped the benchmark and are worth recording.

### O1 — CrewAI retries a failing tool three times, with no public knob

`crewai.tools.tool_usage.ToolUsage._max_parsing_attempts` is `3` and is not
exposed on `Agent`, `Task`, or `Crew`; `Agent(max_retry_limit=0)` does not change
it. A tool that raises is therefore entered three times.

For governance this is **good news, and the benchmark verifies it**: each retry
re-enters the adapter and receives its own independent authorization decision
rather than reusing the first one. Scenario S14 measures it — 3 callable entries,
3 recorded decisions, 0 completed side effects.

### O2 — Repeated decisions inside one mission look like replays

`EvidenceRecorder._stamp` timestamps every event with the bound
`context.decision_at` and has no monotonic component, so two genuinely repeated
decisions in one mission serialize to identical content and
`validate_runtime_events` reports `AN_EVT_REPLAY`. Combined with O1, a naive
integration that uses one mission id for a whole run will emit an unvalidatable
stream the moment any tool is retried.

The benchmark works around this by minting one mission id per tool invocation
(`MissionCounter` in `variant_governed.py`). Integrators should do the same. It
is worth documenting in the adapter package, since the failure mode is
non-obvious and appears only under retry.

### O3 — The adapter package README shows a PyPI install that does not work

`adapters/nornyx-agentic-adapters/README.md` documents:

```bash
pip install nornyx-agentic-adapters
```

That distribution is not on PyPI (`pip index versions nornyx-agentic-adapters` →
"No matching distribution found"), while `nornyx` 1.8.0 is. The benchmark
installs the adapter from the repository and records
`adapters_package_published_on_pypi: false` in `environment.json`.

### O4 — The packaged `__init__` docstring predates the CrewAI adapter

`nornyx_agentic_adapters/__init__.py` still says framework submodules are
"not yet present in this foundation release", although `crewai_adapter` shipped
in the same package. Cosmetic, but it is the first thing a reader sees.
