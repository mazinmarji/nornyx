# ADR-0044 — OpenID AuthZEN interoperability belongs in public Nornyx Core

- **Status:** Accepted
- **Date:** 2026-08-10
- **Decision scope:** public `nornyx.agentic` interoperability only
- **Related:** ADR-0039, ADR-0040, ADR-0043, M7 / issue #79

## Context

Nornyx already exposes a framework-neutral authorization SPI through
`nornyx.agentic`. The SPI evaluates declared Nornyx governance semantics and
returns typed decisions while deliberately avoiding execution, transport,
identity-provider behavior, and enforcement ownership.

OpenID AuthZEN Authorization API 1.0 became an OpenID Final Specification on
2026-01-12. It standardizes the exchange between a Policy Enforcement Point
(PEP) and a Policy Decision Point (PDP). Its Access Evaluation request contains
`subject`, `action`, `resource`, and optional `context`; its successful decision
contains a required boolean `decision` and optional `context`.

Official specification:

- https://openid.net/specs/authorization-api-1_0.html

OpenID Foundation approval notice:

- https://openid.net/authorization-api-1-0-final-specification-approved/

On 2026-06-15 the AuthZEN Working Group also announced official Working Group
Drafts for:

- AuthZEN Access Request and Approval Profile (AARP);
- AuthZEN Profile for Model Context Protocol Tool Authorization (COAZ).

Working Group announcement:

- https://openid.net/openid-foundation-advances-authorization-for-the-agent-era-with-new-authzen-working-group-drafts/

Those two profiles are drafts, not Final Specifications. Nornyx must not claim
conformance to draft semantics it has not implemented and tested.

## Decision

Nornyx Core will support **open AuthZEN interoperability**, beginning with a
small deterministic mapping between the stable Nornyx capability-evaluation SPI
and AuthZEN Authorization API 1.0.

The public implementation is a library-level codec and local evaluation bridge:

```text
AuthZEN Access Evaluation
        |
        v
nornyx.agentic.authzen
        |
        v
CapabilityRequest + EvaluationContext
        |
        v
nornyx.agentic.Authorizer
        |
        v
Nornyx Decision
        |
        v
AuthZEN Decision
```

The initial mapping is intentionally narrow:

```text
AuthZEN subject.type     = nornyx.agent
AuthZEN subject.id       = Nornyx identity_ref
AuthZEN action.name      = nornyx.capability.use
AuthZEN resource.type    = nornyx.capability
AuthZEN resource.id      = Nornyx capability_ref
AuthZEN context.nornyx   = Nornyx profile + decision/revision bindings
```

The Nornyx-defined mapping identifier is:

```text
nornyx.authzen.capability.v1
```

It is a **Nornyx project mapping identifier**, not an OpenID-registered profile
or a claim of OpenID certification.

### Decision translation

AuthZEN 1.0's decision is boolean. The mapping is therefore:

| Nornyx effect | AuthZEN `decision` | Meaning |
|---|---:|---|
| `allow` | `true` | PEP may proceed subject to its own enforcement responsibilities |
| `deny` | `false` | PEP must not proceed |
| `approval_required` | `false` | PEP must not proceed; a fresh decision is required after approval is satisfied |

For Nornyx-aware consumers, the optional AuthZEN decision `context` includes a
namespaced `nornyx` object containing the Nornyx effect, decision code, and
optional reason/basis. An approval-required result also carries the
project-defined `prerequisite: human_approval` marker.

That marker is **not an AARP conformance claim**. AARP is tracked as a draft
compatibility target and will require a separate reviewed mapping before any
conformance statement.

## Public Core boundary

Public Nornyx MAY contain:

- AuthZEN 1.0 request/decision mappings;
- stable Nornyx profile identifiers and semantic mappings;
- deterministic codecs;
- local reference evaluation helpers;
- conformance fixtures and tests;
- AARP/COAZ gap/fit documentation;
- generic MCP/COAZ mapping research;
- examples showing how a PEP can call a separately operated PDP.

Public Nornyx MUST NOT use this work to add:

- a hosted authorization service;
- an HTTP server or client that becomes a product control plane;
- caller authentication or credential management;
- organization/BU/application/agent/mission hierarchy services;
- governance-graph or change-impact intelligence;
- enterprise policy distribution/caching;
- multi-tenancy, RBAC, HA, DR, SaaS or on-prem product topology;
- enforcement ownership or action execution.

Those are operational/product concerns outside the public Core boundary.

## Why AuthZEN instead of a Nornyx-specific wire protocol

Nornyx has no strategic reason to invent a generic PDP-to-PEP protocol when a
Final OpenID specification now exists for that boundary. The differentiation of
Nornyx is its governance semantics, deterministic composition, revision/evidence
binding, agentic authority model, and assurance discipline—not transport syntax.

The architectural rule is:

> **Nornyx determines governance meaning; AuthZEN carries the authorization exchange; the PEP enforces.**

## Why capability evaluation first

`CapabilityRequest(identity_ref, capability_ref)` has an exact, unsurprising
mapping to AuthZEN's Subject/Action/Resource model. Other Nornyx request types
include delegation, handoff, approval, zone crossing, and data sharing. Mapping
them prematurely would either invent semantics or freeze a profile before AARP
and COAZ mature.

The first implementation therefore supports capability evaluation only. New
request mappings require an ADR-backed extension with explicit interoperability
evidence.

## Security and assurance properties

The bridge:

- does not weaken Nornyx's revision binding;
- carries `decision_at` and `observed_subject_revision` explicitly;
- fails closed when the mapped subject/action/resource/profile does not match;
- preserves AuthZEN's boolean deny semantics for Nornyx `approval_required`;
- does not execute actions;
- does not authenticate the subject or caller;
- does not prove the PEP enforced the result;
- does not turn cooperative Tier-2 Nornyx evidence into Tier 3.

The Authorizer remains authoritative for the Nornyx decision. The mapping is not
a second policy engine.

## AARP and COAZ treatment

AARP and COAZ are tracked as **Working Group Draft compatibility targets**.
Until a separate implementation milestone is accepted:

- no AARP conformance claim;
- no COAZ conformance claim;
- no Nornyx-specific fork of either draft;
- no MCP schema modification;
- no automatic approval;
- no assumption that a draft feature is stable.

Future work should prefer mapping Nornyx semantics into the standard profiles
where fit is strong and documenting gaps where it is not.

## Consequences

### Positive

- Nornyx becomes interoperable with an open authorization boundary without
  becoming a runtime platform.
- PEP implementers can reuse a standard request/decision model.
- Any independently operated PDP service can later operate the same public
  semantics without forcing public Core consumers onto a proprietary protocol.
- The public Core boundary becomes clearer rather than weaker.

### Costs / limitations

- The initial mapping covers capability evaluation only.
- Nornyx-specific decision context is not automatically meaningful to generic
  AuthZEN PEPs.
- Approval prerequisites remain a Nornyx-namespaced hint under AuthZEN 1.0 until
  an AARP mapping is separately implemented.
- Network transport, PDP discovery, authentication, service hosting, and
  operational availability are deliberately outside this implementation.
- ADR-0039's curated `nornyx.agentic` facade remains frozen; AuthZEN is imported
  explicitly from the public `nornyx.agentic.authzen` submodule.

## Acceptance evidence

This ADR is implemented when:

1. `nornyx.agentic.authzen` provides deterministic capability request mapping;
2. the mapping round-trips to `CapabilityRequest` + `EvaluationContext`;
3. semantic mismatches fail closed;
4. allow/deny/approval-required decision translation is tested;
5. approval-required cannot become an AuthZEN allow;
6. the public `nornyx.agentic.authzen` module is packaged without expanding the frozen facade;
7. documentation states the AARP/COAZ draft status and the public Core boundary;
8. repository CI passes before merge.
