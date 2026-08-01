# Migration status

ADR-0039 M2-D is implemented. The unpackaged
`integrations/nornyx_reference_adapters/GovernanceKernel` remains available as
a deprecated source-compatibility shim, but its decisions, evidence, and every
compatibility projection now come from the public Nornyx agentic SPI 1.2 —
specifically `Authorizer.state`, first published in Nornyx 1.11.0. The published
`nornyx-agentic-adapters` package remains the supported replacement.

## Completed: the legacy reference tree's import name

The AN-005 reference adapters used to live at
`integrations/nornyx_agentic_adapters/` — the **same import name** as this
installed distribution. Any process that put `integrations/` on `sys.path`
silently rebound that name to the unpackaged legacy tree, and the failure
surfaced as an `ImportError` on a public name such as `AdapterDenied`.

| Before | After |
| --- | --- |
| `integrations/nornyx_agentic_adapters/` | `integrations/nornyx_reference_adapters/` |
| `from nornyx_agentic_adapters.governance_kernel import GovernanceKernel` | `from nornyx_reference_adapters.governance_kernel import GovernanceKernel` |
| `from nornyx_agentic_adapters.crewai_adapter import CrewAIGovernanceAdapter` | `from nornyx_reference_adapters.crewai_adapter import CrewAIGovernanceAdapter` |
| `from nornyx_agentic_adapters.langgraph_adapter import LangGraphGovernanceAdapter` | `from nornyx_reference_adapters.langgraph_adapter import LangGraphGovernanceAdapter` |
| `from nornyx_agentic_adapters.local_harness import ...` | `from nornyx_reference_adapters.local_harness import ...` |

`nornyx_agentic_adapters` now unambiguously means **this installed
distribution**. The rename breaks no published package: the `integrations/`
tree is excluded from the `nornyx` wheel by construction and has never been
published, so it was only ever reachable by a caller that added that directory
to `sys.path` itself. If you did that, update the module name as above.

No compatibility shim was left under the old name — republishing
`nornyx_agentic_adapters` from `integrations/` would recreate exactly the
collision this rename fixes.

## What exists today

Nornyx's existing reference adapters live in the main `nornyx` repository
under `integrations/nornyx_reference_adapters/` (added by AN-005 / ADR-0037).
That directory:

- is **not** part of the `nornyx` wheel;
- preserves the historical `GovernanceKernel` signatures and local
  `AN_ADAPTER_*` diagnostics;
- delegates authorization to `nornyx.agentic.Authorizer` and evidence
  construction to `EvidenceRecorder` rather than retaining hand-rolled policy
  or event logic;
- emits one standard `DeprecationWarning` on construction naming this package
  and `nornyx.agentic` as the replacement.

## Complete legacy method mapping

| Legacy method | Current SPI 1.2 path | Preserved result |
| --- | --- | --- |
| `from_local_controls(contract_path, lock_path, *, framework, as_of, clock=None)` | `load_authorizer(..., validation_as_of=as_of)` only; every compatibility projection is derived from that Authorizer's public `state`, with no second read, composition, or verification | `GovernanceKernel` or the matching legacy load violation |
| `resolve_identity(agent_key)` | `Authorizer.resolve_identity(framework, agent_key)` | identity ref; unknown and ambiguous both remain `AN_ADAPTER_IDENTITY_UNKNOWN` |
| `check_capability(identity_id, capability, *, mission_id)` | `CapabilityRequest` → one `evaluate` → `record_decision` | recorded `capability_allowed` event or stable capability/identity violation |
| `invoke_tool(identity_id, capability, *, mission_id)` | same capability request; because this legacy signature accepts no callable, method entry is its complete protected occurrence | recorded `tool_invoked` after ALLOW |
| `request_delegation(delegation_id, *, mission_id)` | `DelegationRequest` | `None` or stable delegation violation |
| `request_handoff(handoff_id, *, mission_id)` | `HandoffRequest`; `handoff_initiated` observation after ALLOW | `None` or stable handoff violation |
| `complete_handoff(handoff_id, *, mission_id)` | `handoff_completed` observation for the already-authorized lifecycle; no second evaluation | `None` or `AN_ADAPTER_HANDOFF_UNKNOWN` |
| `require_human_approval(record, *, mission_id, actor_ref, approval_ref=...)` | normalized `ApprovalAssertion` inside `ApprovalRequest` | `None` or stable approval violation |
| `record_zone_crossing(identity_id, source_zone, target_zone, *, mission_id, approval_ref=None)` | `ZoneCrossingRequest`; optional legacy reference normalized from the authoritative requirement and gate | `None` or stable crossing/approval violation |
| `record_data_shared(identity_id, target_id, categories, *, mission_id, source_zone, target_zone)` | `DataShareRequest` | `None` or stable sharing violation |
| `events_payload()` | `EvidenceRecorder.stream()` | runtime-events envelope |
| `write_events(path)` | serializes `EvidenceRecorder.stream()` | requested `Path` |

The legacy CrewAI `guarded_task` and LangGraph `guard_node` wrappers now use one
shared shim enforcement path: normalize; authorize exactly once; stop on
denial; execute once; record success after the callable returns; record
`runtime_failed` if it raises. No success event is recorded for a denied or
failed callable.

### Approval-field compatibility

The old approval mapping contains only `role`, `actor_type`, and `granted`; a
zone crossing may contain only an `approval_ref`. The current SPI requires an
`ApprovalAssertion` with action, revision, issuance, evidence, and claimed
approver fields. For omitted fields only, the shim takes the action/evidence and
role from the composed approval requirement and governing gate, the revision
from the bound Authorizer, and issuance from `EvaluationContext.decision_at`.
Caller-supplied fields are not overwritten and remain subject to Authorizer
checks. A bare legacy approval reference remains a cooperative claimed-human
assertion; neither the shim nor the supported package authenticates it.

Unknown requirements/gates and malformed values fail closed. This translation
preserves the old minimal input while making the current Authorizer the only
policy decision point; it is not a new public approval guarantee.

### Diagnostic mapping

Direct equivalents retain the established code stem:

| SPI outcome | Legacy shim outcome |
| --- | --- |
| `CAPABILITY_UNKNOWN` / `CAPABILITY_DENIED` | `AN_ADAPTER_CAPABILITY_UNKNOWN` / `AN_ADAPTER_CAPABILITY_DENIED` |
| `DELEGATION_UNKNOWN` / `DELEGATION_INACTIVE` | `AN_ADAPTER_DELEGATION_UNKNOWN` / `AN_ADAPTER_DELEGATION_INACTIVE` |
| `HANDOFF_UNKNOWN` / `HANDOFF_AUTHORITY` | `AN_ADAPTER_HANDOFF_UNKNOWN` / `AN_ADAPTER_HANDOFF_AUTHORITY` |
| `APPROVAL_NON_HUMAN` / `APPROVAL_ROLE_INVALID` / `APPROVAL_NOT_GRANTED` | matching `AN_ADAPTER_APPROVAL_*` code |
| `APPROVAL_STALE`, approval revision/action mismatch, missing approval evidence | existing `AN_ADAPTER_APPROVAL_NOT_GRANTED` |
| `ZONE_CROSSING_DENIED` / `CROSSING_APPROVAL_REQUIRED` | `AN_ADAPTER_ZONE_CROSSING_DENIED` / `AN_ADAPTER_CROSSING_APPROVAL_REQUIRED` |
| `SENSITIVE_SHARING` / `SHARE_NOT_ALLOWED` | `AN_ADAPTER_SENSITIVE_SHARING` / `AN_ADAPTER_SHARE_NOT_ALLOWED` |
| SPI-only party/revision/malformed denial | applicable legacy surface denial; malformed adapter input is `AN_ADAPTER_REQUEST_MALFORMED` before evaluation |
| recorder rejection | `AN_ADAPTER_EVIDENCE_INVALID` |

These remain compatibility codes only. They are not exported by
`nornyx.agentic` and must not be treated as new public SPI guarantees.

## Runtime-events compatibility

- A historical lock declaring runtime-events 1.0 produces the exact 1.0
  envelope branch: no `occurrence_mode` and no occurrence fields.
- A lock declaring runtime-events 1.1 produces `occurrence_mode: legacy` and
  retains the legacy event shape. The shim does not infer operation,
  occurrence, or attempt identity.
- Explicit 1.1 occurrence recording belongs to supported adapters such as
  `nornyx_agentic_adapters.langgraph`; a legacy stream cannot be silently
  upgraded or resumed as explicit.
- Both modes retain the Authorizer's exact contract, lock, and subject-revision
  binding and validate through the existing runtime-events schema id.

## Deprecation and retention

Construction warns once per normal load path with `DeprecationWarning`; method
calls do not repeat it. The shim will remain for at least one published Nornyx
minor release after M2-D. Removal has no assigned version and requires all of:

1. the minimum published-minor window has elapsed;
2. this mapping and the installed-wheel compatibility corpus remain complete;
3. a supported adapter covers the consumer's required surface, or that surface
   is explicitly documented as unsupported; and
4. a separate owner-authorized removal decision.

It is not disabled by this migration.

## Unsupported surfaces

The shim does not provide occurrence-explicit retries/resume, asynchronous
CrewAI or LangGraph interception, remote/distributed execution, framework-wide
coverage, identity/approver authentication, or Tier-3 attestation. It does not
import either framework into core. Unsupported behavior is not approximated as
covered; use the supported package coverage inventories.

## Using the supported package today

CrewAI is supported (`nornyx_agentic_adapters.crewai_adapter`, M2-B, tool
invocation only — see README Coverage). LangGraph synchronous StateGraph nodes
are supported by `nornyx_agentic_adapters.langgraph` (M2-C).
Consumers of the existing `integrations/nornyx_reference_adapters/` reference
code for CrewAI may migrate to this package's `crewai_adapter` module now — and,
because of the rename above, the two can now coexist in one Python process.
LangGraph consumers should migrate guarded node construction to
`make_governed_node` and an occurrence-aware core recorder. The legacy
reference code remains available only for the retention window above.
