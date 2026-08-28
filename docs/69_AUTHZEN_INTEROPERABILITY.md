# Nornyx ↔ OpenID AuthZEN Interoperability

**Status:** Public Core interoperability surface
**Milestone:** M7-A
**Decision:** ADR-0044
**Implementation:** `nornyx.agentic.authzen`

## Why this exists

Nornyx has a framework-neutral authorization SPI, while OpenID AuthZEN defines a
standard boundary for authorization requests from Policy Enforcement Points
(PEPs) to Policy Decision Points (PDPs). Nornyx should interoperate with that
boundary rather than invent a competing generic authorization wire protocol.

OpenID AuthZEN Authorization API 1.0 is a Final Specification approved on
2026-01-12. Its Access Evaluation API uses:

- `subject` — the user or machine principal;
- `action` — the requested operation;
- `resource` — the target of the request;
- optional `context` — environmental/request attributes;
- boolean `decision` — `true` to permit, `false` to deny;
- optional response `context` — additional information for the PEP.

Authoritative source:

- https://openid.net/specs/authorization-api-1_0.html

The AuthZEN Working Group announced AARP (Access Request and Approval Profile)
and COAZ (Profile for MCP Tool Authorization) as official Working Group Drafts
on 2026-06-15:

- https://openid.net/openid-foundation-advances-authorization-for-the-agent-era-with-new-authzen-working-group-drafts/

Nornyx tracks those drafts but does not claim AARP or COAZ conformance in this
milestone.

## Public Core scope boundary

This repository owns **portable semantics and interoperability**.

It does not own a hosted authorization service.

```text
PEP / gateway / agent integration
              |
              | AuthZEN Access Evaluation
              v
      Nornyx mapping boundary
       nornyx.agentic.authzen
              |
              v
       nornyx.agentic.Authorizer
              |
              v
        Nornyx Decision
              |
              | AuthZEN Decision
              v
      external PEP enforcement
```

Public Core includes the codec, semantic mapping, tests, and documentation —
that is, **portable deterministic authorization semantics and interoperability**.

Outside this public implementation: transport, service hosting, service
discovery, governance distribution, caching policy, clustering, multi-tenancy,
organizational hierarchy operation, change-impact intelligence, HA/DR, external
enforcement, and commercial deployment.

The division is deliberate. Nornyx Core decides what a governed request *means*
at a stated decision time against a stated subject revision. Delivering that
decision to a process, keeping it available, and acting on it are the
integrator's responsibilities and are not simulated here.

## Supported mapping: capability evaluation

The first stable mapping deliberately covers one Nornyx request type:

```python
CapabilityRequest(identity_ref, capability_ref)
```

It maps as follows:

| Nornyx | AuthZEN |
|---|---|
| `identity_ref` | `subject.id` |
| Nornyx agent identity | `subject.type = "nornyx.agent"` |
| capability use | `action.name = "nornyx.capability.use"` |
| `capability_ref` | `resource.id` |
| Nornyx capability | `resource.type = "nornyx.capability"` |
| mapping identity | `context.nornyx.profile = "nornyx.authzen.capability.v1"` |
| decision time | `context.nornyx.decision_at` |
| observed revision | `context.nornyx.observed_subject_revision` |

The mapping identifier is Nornyx-owned. It is not an OpenID-registered profile.

## Example

```python
from nornyx.agentic import CapabilityRequest, EvaluationContext
from nornyx.agentic.authzen import capability_request_to_authzen

payload = capability_request_to_authzen(
    CapabilityRequest(
        identity_ref="agent.research",
        capability_ref="research.summarize",
    ),
    context=EvaluationContext(
        decision_at="2026-08-10T10:00:00Z",
        observed_subject_revision="git:" + "a" * 40,
    ),
)
```

The resulting Access Evaluation object is:

```json
{
  "subject": {
    "type": "nornyx.agent",
    "id": "agent.research"
  },
  "action": {
    "name": "nornyx.capability.use"
  },
  "resource": {
    "type": "nornyx.capability",
    "id": "research.summarize"
  },
  "context": {
    "nornyx": {
      "profile": "nornyx.authzen.capability.v1",
      "decision_at": "2026-08-10T10:00:00Z",
      "observed_subject_revision": "git:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }
}
```

The reverse decoder returns the exact public Nornyx values:

```python
from nornyx.agentic.authzen import capability_request_from_authzen

request, context = capability_request_from_authzen(payload)
```

The decoder fails closed if the subject type, action name, resource type,
profile identifier, decision time, or revision binding is absent or belongs to a
different semantic mapping.

## Decision mapping

AuthZEN 1.0 uses a boolean decision. Nornyx has three effects.

| Nornyx effect | AuthZEN decision | Enforcement meaning |
|---|---:|---|
| `ALLOW` | `true` | the PEP may proceed |
| `DENY` | `false` | the PEP must not proceed |
| `APPROVAL_REQUIRED` | `false` | the PEP must not proceed; obtain the prerequisite and evaluate again |

Example Nornyx-aware deny response:

```json
{
  "decision": false,
  "context": {
    "nornyx": {
      "profile": "nornyx.authzen.capability.v1",
      "effect": "deny",
      "code": "CAPABILITY_DENIED",
      "reason": "Capability is not held."
    }
  }
}
```

For an approval prerequisite, Nornyx additionally emits:

```json
{
  "decision": false,
  "context": {
    "nornyx": {
      "profile": "nornyx.authzen.capability.v1",
      "effect": "approval_required",
      "code": "APPROVAL_REQUIRED",
      "prerequisite": "human_approval"
    }
  }
}
```

The `prerequisite` field is a Nornyx-namespaced hint under the AuthZEN 1.0
optional decision context. It is **not an AARP claim**. A future AARP mapping must
be separately reviewed against the then-current Working Group specification.

## Local bridge

A caller that already owns transport can use the local helper:

```python
from nornyx.agentic.authzen import evaluate_authzen_capability

response = evaluate_authzen_capability(authorizer, payload)
```

The helper only performs:

```text
AuthZEN dict
  -> CapabilityRequest + EvaluationContext
  -> Authorizer.evaluate(...)
  -> AuthZEN decision dict
```

It opens no socket, serves no endpoint, loads no credential, and executes no
governed action.

The standard HTTPS default path is exported only as metadata for adapters:

```python
AUTHZEN_ACCESS_EVALUATION_PATH == "/access/v1/evaluation"
```

## Local decision use is a supported deployment pattern

Once a contract has been validated and lock-verified by `load_authorizer`, an
ordinary authorization decision is a local computation over already-loaded
state. It reads no file and opens no connection.

That makes embedded and edge deployment a first-class option rather than a
degraded mode: a caller may hold an `Authorizer` in-process and evaluate against
it, with or without any network at all.

```python
authorizer = load_authorizer(contract_path, lock_path, validation_as_of=as_of)
# ... network may now be unavailable ...
decision = authorizer.evaluate(request, context=context)
response = evaluate_authzen_capability(authorizer, payload)
```

**Measured, not asserted — both halves.**
`tests/test_agentic_authzen_equivalence.py` loads a real contract, then refuses
`socket.socket`, `socket.create_connection` and `socket.getaddrinfo`, **proves
each of those three refuses before proceeding**, and requires every case to
decide identically offline through both paths. A separate test counts calls to
`open` across a decision on both paths and requires zero.

The bound of that evidence, network half: it blocks network use through the
`socket` module, which is the path CPython's networking stack and the standard
library's clients take. It does not constrain a C extension that opens a
descriptor without importing `socket`, nor a module holding a
`from socket import ...` reference bound before the patch.

The bound of that evidence, file half: the count covers `open` and `io.open`,
the Python-level paths every stdlib reader takes. A raw `os.open` descriptor
read would not be counted.

What remains the integrator's responsibility: obtaining the contract and lock,
deciding when to reload them, and any caching, distribution, or availability
policy around that state. Nornyx Core does not schedule, refresh, or replicate
governed state.

## Direct-vs-AuthZEN equivalence

Both supported paths — direct `Authorizer.evaluate(...)` and the AuthZEN
mapping with `evaluate_authzen_capability(...)` — decide the same governed
request identically when bound to the same `decision_at` and
`observed_subject_revision`.

**The domain of that claim** is a capability request whose `identity_ref` and
`capability_ref` are non-empty strings. Outside it the two paths both fail
closed but not identically: the direct path returns a Nornyx `DENY` decision,
while the AuthZEN path refuses at the mapping boundary and returns no decision
at all. That difference is pinned by a test rather than left to be discovered.

Equivalence is asserted field by field over what the mapping represents, because
the AuthZEN 1.0 response is a *projection* of a Nornyx `Decision`, not a copy:

| Nornyx `Decision` | AuthZEN response |
|---|---|
| `effect` | `decision` (boolean), and `context.nornyx.effect` |
| `code` | `context.nornyx.code` |
| `reason` | `context.nornyx.reason` (omitted when empty) |
| `basis` | `context.nornyx.basis` |
| `APPROVAL_REQUIRED` | `context.nornyx.prerequisite = "human_approval"` |

The last row is **not exercised by the equivalence cases** and is listed for
completeness of the mapping, not as something these cases establish: no
capability request produces `APPROVAL_REQUIRED` (see below), so the two paths
cannot diverge on it here. The codec's encoding of that marker is covered
separately in `tests/test_agentic_authzen.py` against a constructed `Decision`.

**Not represented, and therefore not claimed equivalent:**
`Decision.event_intents`. The mapping carries no encoding for decision-event
intents, so a consumer reading only AuthZEN cannot reconstruct them.

This limitation is enforced structurally: a test asserts the encoded document's
key set is exactly the documented one, so intents cannot arrive under a new
field however it is spelled, and every represented field is compared to the
direct decision by exact equality.

Comparing the two paths would not by itself establish correctness — both could
drift to the same wrong answer — so each case also asserts the specific effect
and decision code the contract produces. Covered outcomes, all produced by the
real example contract rather than constructed: `ALLOWED`, `CAPABILITY_DENIED`,
`CAPABILITY_UNKNOWN`, `PARTY_INEFFECTIVE`, `REVISION_MISMATCH`.

`APPROVAL_REQUIRED` is **not** among them. `CapabilityRequest` is the only
request type this mapping supports, and capability evaluation returns ALLOW or
DENY only, so no honest capability request produces it. The codec's handling of
that effect is covered separately against a constructed `Decision`.

## What is deliberately not mapped yet

The current Nornyx SPI also models:

- delegation;
- handoff;
- approval assertions;
- trust-zone crossings;
- data sharing.

Those are not forced into AuthZEN 1.0 merely to increase apparent coverage.
They require explicit semantic work. In particular:

- approval/prerequisite interoperability should be evaluated against AARP;
- MCP tool authorization should be evaluated against COAZ;
- delegation/handoff mapping needs a clear subject/resource model and evidence
  boundary before it can be called interoperable.

## AARP and COAZ tracking rule

For both Working Group Drafts:

1. use the OpenID specification as the upstream source of truth;
2. do not copy a draft into a Nornyx-specific competing protocol;
3. document fit/gaps before implementation;
4. do not modify MCP semantics merely to make mapping easier;
5. require deterministic conformance tests before claiming support;
6. keep automatic approval prohibited;
7. keep enforcement outside Nornyx Core.

## Assurance boundary

This bridge proves only that Nornyx can deterministically translate the declared
request and decision semantics represented by this mapping.

It does **not** prove:

- who authenticated the caller or subject;
- that a PEP cannot be bypassed;
- that the PEP enforced the returned result;
- that runtime events actually occurred;
- that a hosted PDP is available or correctly operated;
- AARP or COAZ conformance;
- Tier-3 independent enforcement.

The same ADR-0039/ADR-0040 boundaries continue to apply.

## Commercial neutrality

The mapping is intentionally public. Any organization, adapter, gateway, or
commercial product may use the same public contract.

Nornyx's portable value remains in governance semantics, deterministic
composition, authority modeling, revision/evidence binding, and conformance.
Large-scale hosted operation of those semantics is not implemented here.
