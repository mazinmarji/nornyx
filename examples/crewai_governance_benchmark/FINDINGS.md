# Findings — all resolved

Originally found against base SHA `d4026a1a06789453de86ea60cd4a78c31da87da2` (`main`)
Packages: `nornyx` 1.8.0 (SPI 1.0), `nornyx-agentic-adapters` 0.1.0, `crewai` 1.15.4

| # | Finding | Status |
|---|---|---|
| F1 | A correctly refused non-human approval cannot appear in a valid stream | **Resolved** — `nornyx/agentic_evidence.py` |
| F2 | A delegated capability's `tool_invoked` event cannot validate | **Resolved** — `nornyx_agentic_adapters` |
| F3 | The legacy `integrations/` tree shadows the supported adapter package | **Resolved** — renamed to `nornyx_reference_adapters` |

Building this benchmark surfaced three defects in the audited packages. Two of
them stopped the benchmark's runtime-event stream from validating; the third made
the supported and legacy adapters unable to coexist in one Python process. All
three were reproducible without any benchmark code, and **none of them ever
affected an enforcement result** — every authorization decision was correct and
every prevented callable stayed at zero side effects. What they blocked was a
clean *evidence* claim.

All three are now fixed in this repository, each with its own regression test.
The reproductions below are kept verbatim so the fixes stay auditable: each
section states what went wrong, how to reproduce it against the original
revision, what changed, and which test pins the behaviour. With the fixes in
place the full event stream validates with zero diagnostics and the benchmark's
verdict is `GO`.

The benchmark still reports the full-stream validation status verbatim and lists
every diagnostic; it has no allow-list of tolerated codes and no reduced-stream
fallback.

---

## F1 — A correctly refused non-human approval cannot appear in a valid stream

**Status:** **Resolved.**
**Severity (as found):** blocked evidence validation for any run that refuses an AI approval.
**Component:** `nornyx/agentic/authz.py` (emitter) × `nornyx/agentic_evidence.py` (validator)
**Reproduced by:** scenario **S07** (mandatory scenario 7, "AI-generated or non-human approval")

### What happened

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

### Why it mattered

Refusing an AI-issued approval is one of the product's headline guarantees. As
shipped, exercising that guarantee made the evidence stream unvalidatable — so
the strongest governance outcome was the one that could not be evidenced.

### The fix

`approver` means two different things on the two approval outcomes, and the
validator was applying one meaning to both. On `approval_granted` it names the
party whose authority the action now rests on, so it must be a human holding a
composed module role. On `approval_rejected` it records the *claimed* approver of
an approval that was refused, and confers nothing.

`nornyx/agentic_evidence.py` now scopes both approver rules —
`AN_EVT_APPROVAL_NON_HUMAN` and `AN_EVT_APPROVAL_ROLE_INVALID` — to
`approval_granted`. The engine is unchanged: it still denies the non-human
approval with `APPROVAL_NON_HUMAN` and still records the claimant truthfully.
No human-approval guarantee is weakened; a granted approval must still name a
human with an authorized role, and forging one still fails validation.

### Regression tests

`tests/test_agentic_authz.py`:

- `test_refused_non_human_approval_is_evidenced_truthfully` — the reproduction
  above, end to end: DENY / `APPROVAL_NON_HUMAN`, a truthful `approval_rejected`
  naming the model, and a stream that validates with zero diagnostics.
- `test_refused_invalid_role_approval_is_evidenced_truthfully` — same rule for a
  claimed role outside the composed authority.
- `test_granted_non_human_approval_still_fails_validation` and
  `test_granted_invalid_role_approval_still_fails_validation` — a forged
  `approval_granted` still fails, so the grant rule is provably intact.

---

## F2 — A delegated capability's `tool_invoked` event cannot validate

**Status:** **Resolved.**
**Severity (as found):** blocked evidence validation for any governed tool using a delegated capability.
**Component:** `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`
**Reproduced by:** scenario **S16** ("valid bounded delegation")

### What happened

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

### Why it mattered

Bounded, revocable delegation is a core reason to declare an agent network at
all. Any governed tool exercising a delegated capability emitted an event that
could not validate, so delegation and validatable evidence were mutually
exclusive on the supported CrewAI path.

### The fix

The authorizing delegation is now carried from the decision into the
observation. `enforce()` gained an optional `on_decision` observation hook,
called after the decision's intents are recorded and before any branch on the
outcome; it cannot change the outcome, and an exception raised from it
propagates before the wrapped action is reached, so the boundary still fails
closed. `_GovernedTool._run` uses it to read `DecisionBasis(kind="delegation")`
off the ALLOW and passes `delegation_ref` to `record_observation`.

The reference is read from the decision, **never** from the tool's arguments,
and is recorded only when the capability was actually authorized by delegation —
a directly-held capability's observation is unchanged, because the recorder
drops `None` fields.

### Regression tests

`adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py`:

- `test_delegated_capability_observation_carries_the_authorizing_delegation` —
  ALLOW, callable executes exactly once, `tool_invoked` carries
  `delegation_ref`, complete stream validates with zero diagnostics.
- `test_directly_held_capability_observation_omits_delegation_ref` — no field
  when the capability is held by membership.
- `test_delegation_ref_is_not_taken_from_tool_arguments` — a caller-supplied
  `delegation_ref` argument is ignored in favour of the decision's own basis.
- `test_expired_delegation_denies_and_records_no_tool_invoked` — a lapsed
  delegation grants nothing and observes nothing.

`adapters/nornyx-agentic-adapters/tests/test_enforcement.py` pins the hook's own
contract: it sees the already-recorded decision before the action runs, it runs
on DENY without unblocking the action, and an error inside it fails closed.

---

## F3 — The legacy `integrations/` tree shadows the supported adapter package

**Status:** **Resolved.**
**Severity (as found):** the supported and legacy adapters could not coexist in one Python process.
**Component:** `integrations/` × `adapters/nornyx-agentic-adapters`
**Found by:** running this benchmark's tests in a full-suite run rather than alone.

### What happened

Both trees claimed the import name `nornyx_agentic_adapters`:

| Path | What it is |
|---|---|
| `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/` | the supported, installed distribution (ADR-0039 M2-A/M2-B) |
| `integrations/nornyx_agentic_adapters/` (as it was) | the legacy, unpackaged reference kernel (ADR-0037) |

Any process that put `integrations/` on `sys.path` got the legacy tree for that
name — for everything that followed, not just its own imports. Several of this
repository's own test modules do exactly that (`tests/test_agentic_integrations.py`,
`tests/test_agentic_crewai_native.py`, `tests/test_agentic_support_example.py`),
and they sort alphabetically ahead of anything using the supported package.

### Reproduction (against the original revision)

```python
import sys
sys.path.insert(0, "integrations")
import nornyx_agentic_adapters as pkg
print(pkg.__file__)                       # -> integrations/nornyx_agentic_adapters/__init__.py
from nornyx_agentic_adapters import AdapterDenied
# ImportError: cannot import name 'AdapterDenied' from 'nornyx_agentic_adapters'
```

`AdapterDenied`, `SurfaceBinding`, `enforce`, and `crewai_adapter` exist only in
the installed distribution; the legacy tree exposes `governance_kernel`,
`crewai_adapter` (a different one), `langgraph_adapter`, and `local_harness`.

### Why it mattered

A consumer that installed the supported package and also had this repository's
`integrations/` directory reachable silently got the wrong module, and the
failure surfaced as a confusing `ImportError` on a public name rather than as a
clear conflict.

### The fix

The legacy reference tree was renamed to `integrations/nornyx_reference_adapters/`,
so the supported distribution owns `nornyx_agentic_adapters` unambiguously. The
rename is source-only and breaks no installed distribution: the `integrations/`
tree is excluded from the `nornyx` wheel by construction (asserted by
`test_default_install_does_not_package_integrations`) and has never been
published, so it is reachable only by a caller that puts that directory on
`sys.path` itself. Every in-repo import, test, example, guide, and ADR reference
was migrated in the same change, and
`adapters/nornyx-agentic-adapters/docs/MIGRATION.md` records the old and new
names for anyone who wired the reference tree in by hand.

No compatibility shim was left under the old name: republishing
`nornyx_agentic_adapters` from `integrations/` would recreate exactly the
collision being fixed.

The benchmark's consumer-side workaround was removed with it —
`config.load_supported_adapter()` now performs a plain import and raises if the
name ever resolves under `integrations/` again. Nothing in the benchmark
manipulates `sys.path` or the module table.

### Regression tests

Order-dependent, and placed in a module that itself pollutes `sys.path`:

- `tests/test_agentic_integrations.py::test_legacy_reference_tree_does_not_claim_the_supported_import_name`
  — nothing importable under `integrations/` may collide with a distribution.
- `tests/test_agentic_integrations.py::test_supported_adapter_resolves_despite_integrations_on_sys_path`
  — with `integrations/` already ahead on `sys.path`, a plain import still
  resolves to the installed distribution and exposes its public names.
- `tests/test_crewai_governance_benchmark.py::test_supported_adapter_is_not_shadowed_by_the_legacy_reference_tree`
  — the same guarantee from the benchmark's side, with the pollution reproduced
  explicitly and the legacy tree still importable under its own name.

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

### O3 — Historical: the adapter package was not yet published

**Current status:** resolved operationally. Nornyx 1.10.0 and
`nornyx-agentic-adapters` 0.2.0 are published on PyPI. The text below records
the environment in which this observation was originally made; it is not a
current availability statement.

`adapters/nornyx-agentic-adapters/README.md` documents:

```bash
pip install nornyx-agentic-adapters
```

At the time of the 1.8.0 / adapter 0.1.0 snapshot, that distribution was not on
PyPI (`pip index versions nornyx-agentic-adapters` returned "No matching
distribution found"), while `nornyx` 1.8.0 was. The historical benchmark
installed the adapter from the repository and recorded
`adapters_package_published_on_pypi: false` in `environment.json`.

### O4 — The packaged `__init__` docstring predates the CrewAI adapter

`nornyx_agentic_adapters/__init__.py` still says framework submodules are
"not yet present in this foundation release", although `crewai_adapter` shipped
in the same package. Cosmetic, but it is the first thing a reader sees.
