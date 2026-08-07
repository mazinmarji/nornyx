---
appendix: F
title: "Appendix F — Adapter and Integration Conformance Checklist"
---

# Appendix F — Adapter and Integration Conformance Checklist

This appendix turns the test obligations that exist in the repository into a checklist you can work
through before claiming that an adapter governs a framework surface. It is written for two
audiences: an engineer building an integration who wants to know what "done" means, and a reviewer
who has been handed such an integration and asked whether its claims hold.

The checklist is derived from real artifacts at the audited revision `70d2b40ad792`: the assurance
tier model of ADR-0040, the test suites of `adapters/nornyx-agentic-adapters/tests/`, the
continuous-integration jobs in `.github/workflows/ci.yml`, and the static conformance machinery of
`schemas/adapter_conformance_report.schema.json`. Nothing here is an invented requirement; where a
row goes beyond what the repository mechanically enforces, the row says so.

Chapter 25 teaches the reasoning behind these obligations. This appendix assumes it.

## F.1 What a Tier 2 claim requires

Before any checklist item, fix the target. ADR-0040 states the claim eligibility for cooperative
Tier 2 as Tier 1 plus five conditions: a supported adapter and interface version; declared
enforcement surfaces in the form of a coverage inventory naming which surfaces are wrapped;
deny-path validation, meaning at least one allow control and one deny control succeed on a declared
wrapped surface; required runtime events present; and successful digest and revision binding. The
claim applies **only to the wrapped surfaces named in the inventory**, never to an application as a
whole.

Three prohibitions come with it. A Tier 2 claim must not describe enforcement as tamper-proof,
mandatory, or independent; must not claim complete coverage of all agent actions; and must not imply
a gateway or sandbox. Every Tier 2 claim carries the qualifier "cooperative, declared surfaces
only".

Use the checklist below to assemble the evidence for that claim — and to discover, honestly, when
you cannot.

## F.2 Per claimed wrapped surface: the five tests

For **each** surface an inventory marks `WRAPPED`, five tests must exist and pass. The naming in the
"pattern in the repository" column points at a real test you can read as a model.

| ✅ | Test | What it must establish | Pattern in the repository | Evidence to attach |
|---|---|---|---|---|
| ☐ | **1. Allow executes exactly once and records** | On an ALLOW decision the wrapped callable runs exactly once, returns its result, and the expected decision events plus the post-action observation are recorded in order | `test_governed_tool_allow_runs_action_exactly_once_and_records_tool_invoked`; `test_sync_node_success_uses_public_task_identity` | Test output plus the recorded event-type sequence (for the CrewAI tool path: `capability_requested`, `capability_allowed`, `tool_invoked`) |
| ☐ | **2. Deny never executes and fails closed** | On DENY or APPROVAL_REQUIRED the callable is never invoked, `AdapterDenied` is raised carrying the core `Decision` unmodified, and no post-action observation is recorded | `test_governed_tool_deny_never_runs_action_and_raises_adapter_denied`; `test_policy_denial_never_calls_action`; `test_approval_required_never_invokes_action` | Side-effect counter at zero; the raised decision code |
| ☐ | **3. Internal failure fails closed before the action** | An unexpected error from evaluation, from decision recording, or from an observation hook propagates *before* the callable is reached; malformed adapter configuration or missing framework execution metadata fails before evaluation | `test_unexpected_evaluate_error_fails_closed`; `test_unexpected_record_decision_error_also_fails_closed`; `test_on_decision_error_fails_closed_before_the_action`; `test_missing_execution_info_fails_before_action`; `test_make_governed_tool_fails_closed_on_blank_binding_field` | Test output; a statement of which failure modes were injected |
| ☐ | **4. Bypass is demonstrated, not hidden** | Calling the underlying callable directly, outside the wrapper, skips enforcement entirely — and a test asserts that it does | `test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely` | The bypass test, plus a written statement of the residual risk in the claim register |
| ☐ | **5. The produced evidence stream validates** | The events the surface produces validate against the lock: `recorder.validate()` returns `status: pass`, with zero diagnostics | `test_native_crew_kickoff_allowed_capability_end_to_end` (asserts both the event sequence and `report["status"] == "pass"`) | The validation report, and the digests it bound |

**Table F.1 — The five tests per wrapped surface.** All five are required. Four of them are about
what does *not* happen, which is the correct emphasis for an enforcement claim.

A sixth obligation applies to surfaces the inventory marks `UNSUPPORTED` where a caller might
plausibly reach them anyway:

| ✅ | Test | What it must establish | Pattern in the repository | Evidence to attach |
|---|---|---|---|---|
| ☐ | **Unsupported path fails closed** | Reaching an unsupported surface does not silently execute ungoverned. In the CrewAI adapter the async path hits the inherited `_arun`, which raises, so the wrapped action never runs and nothing is recorded | `test_async_arun_fails_closed_and_records_nothing`; `test_coverage_inventory_declares_async_tool_invocation_unsupported` | Test output plus the inventory entry's reason string |

**Table F.2 — The unsupported-surface obligation.** An unsupported surface that silently succeeds
ungoverned is worse than an unwrapped one, because the inventory implies it was considered.

## F.3 Coverage inventory declaration

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | Inventory exists and is machine-readable | A `CoverageInventory` of `SurfaceCoverage(surface, framework, status, reason)` entries, with `as_dict()` producing a deterministic, sorted, JSON-serialisable record | The serialised inventory |
| ☐ | Every status is one of three values | `WRAPPED`, `UNSUPPORTED`, or `UNWRAPPED`. `UNWRAPPED` means caller-owned — the LangGraph adapter uses it for `graph_topology`, the only such use in the repository | The inventory |
| ☐ | Each non-wrapped entry carries a specific reason | Not "not supported" but why: no public stable hook, would depend on undocumented internals, no distinct concept exists in this framework | The reason strings |
| ☐ | The inventory claims no unnamed surface | A test asserts that surfaces outside the declared entries are not claimed | `test_coverage_never_claims_unnamed_surfaces` |
| ☐ | The inventory is immutable after construction | Entries are canonicalised to a fresh tuple, so mutating a retained caller list cannot alter it | `test_retained_caller_list_mutation_after_construction_has_no_effect` |
| ☐ | The inventory is not presented as application coverage | Written claims scope to the named surfaces | The claim register wording |

**Table F.3 — Coverage inventory conformance.** The inventory is the artifact that makes a Tier 2
claim reviewable. Without it, "we govern CrewAI" is unfalsifiable.

Note one gap honestly: `CoverageInventory.as_dict()` is JSON-serialisable, but no pipeline in the
repository writes it out as a published artifact. It is asserted in tests and in the installed-wheel
smoke. If you want the inventory as an audit deliverable, you must export it yourself.

## F.4 Version pin enforcement

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | Framework version is pinned exactly | The tested framework version is named with `==`, not a range. The repository pins `crewai==1.15.4` and `langgraph==1.2.2`, on the stated rationale that the pin "names the only version of each framework this package has been tested against" | The extras declaration |
| ☐ | The pin is **enforced**, not merely declared | Each framework submodule checks the installed distribution version at import time and refuses to run against an untested version | `test_installed_crewai_version_is_the_supported_exact_version`; `test_check_crewai_version_rejects_unsupported_version` |
| ☐ | Three failure cases are distinguished | Framework absent raises `MissingOptionalDependencyError` naming the extras install; installed-but-wrong or malformed metadata raises `AdapterConfigurationError` naming both versions; correct version imports normally | `test_crewai_adapter_missing_dependency.py`; `test_installed_crewai_version_fails_closed_on_malformed_metadata` |
| ☐ | The interface major version is asserted at import | The base package calls `check_spi_version` on import; a non-supported major raises `UnsupportedSPIVersionError` immediately rather than failing later | `test_check_spi_version_rejects_unsupported_major`; `test_installed_spi_version_is_actually_compatible` |
| ☐ | Metadata does not masquerade as enforcement | `AdapterMetadata.framework_version_range` is documentation; its own docstring says it is "not enforced by this dataclass itself" | A statement naming where enforcement actually lives |
| ☐ | Package version and changelog agree | Distribution version matches the packaging metadata, and the changelog names the release | `test_package_version_matches_pyproject`; `test_changelog_mentions_the_current_release_version` |

**Table F.4 — Version pin conformance.** A framework upgrade is a governance event: the wrapped
surface may move. Widening a pin without new test evidence is the framework-adapter drift failure
mode of Chapter 25.

## F.5 The injected-dependency rule

An adapter must not construct, read, or re-derive governance state. It receives it.

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | The adapter performs no filesystem input or output | Verified by absence: no `load_authorizer`, `open(`, `read_text`, or `Path(` in the adapter source | A source search result |
| ☐ | Authorizer, evaluation context, and recorder are explicit parameters | `make_governed_tool` and `make_governed_node` take all three; the adapter never builds them | The constructor signatures |
| ☐ | The adapter never re-composes or re-verifies | One authorizer is the single interpretation of the contract; nothing in the adapter re-reads the document, re-composes governance, or re-verifies the lock | Source review |
| ☐ | Bindings come from static configuration only | `SurfaceBinding` fields are built from the adapter's own declaration, never from raw framework arguments — commands, paths, URLs, or tool payloads | The binding construction site |
| ☐ | Delegation grounds come from the decision, not the caller | When a capability is held only by delegation, the `delegation_ref` on the post-action observation is read from the ALLOW decision's basis, never from tool arguments | `test_delegation_ref_is_not_taken_from_tool_arguments`; `test_directly_held_capability_observation_omits_delegation_ref` |
| ☐ | Governance state is never serialised as framework data | Governance objects are attached out-of-band so they never enter a tool's argument schema | `test_structured_schema_does_not_serialize_governance_state` |
| ☐ | The base package imports no framework | Framework code is confined to extras-gated submodules; the core package never imports the adapter package | `test_base_import_works_with_no_framework_installed`; `test_nornyx_core_never_imports_the_adapter_package`; `test_no_module_level_framework_import_in_source` |

**Table F.5 — Injected-dependency conformance.** The rule exists to prevent split-brain: two
components each reading the contract and disagreeing about what it says. Chapter 19 develops the
hazard.

## F.6 The enforcement ordering guarantee

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | Evaluate, then record, then execute | The decision is obtained, its event intents are recorded, and only then — and only on ALLOW — does the callable run | `test_allow_invokes_action_exactly_once_and_returns_its_result` |
| ☐ | The order is treated as a compatibility guarantee | Changing the ordering is classified a **breaking** change in the adapter's compatibility document | The compatibility declaration |
| ☐ | Observation hooks cannot unblock | A decision hook runs after recording and before any branch, on DENY as well as ALLOW, and cannot change the outcome | `test_on_decision_runs_on_deny_and_cannot_unblock_the_action` |
| ☐ | Post-action observations follow the action | The success observation is recorded only after the callable returns; an action that raises produces no success observation | `test_governed_tool_allow_runs_action_exactly_once_and_records_tool_invoked` and the failure-path tests |

**Table F.6 — Ordering conformance.** Recording *before* execution is what makes a denial provable
and an execution attributable; recording after would leave a window in which an action ran with no
decision on record.

## F.7 Occurrence semantics — where applicable

These items apply to any adapter that governs a surface a framework may re-enter: retries, loop
visits, parallel branches, and checkpoint resume. Skip them only if the surface genuinely cannot
re-enter, and say so in the inventory.

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | The recorder is occurrence-aware | The adapter requires an explicit-mode recorder built with `EvidenceRecorder.for_occurrences` and refuses one that is not | `test_node_requires_explicit_recorder` |
| ☐ | Occurrence identity comes from public framework metadata | Operation from the declared surface, occurrence from the framework's public task identity, attempt from the framework's public attempt counter — never from private internals | `test_sync_node_success_uses_public_task_identity` |
| ☐ | **Retry**: one occurrence, contiguous attempts | A framework-native retry produces one occurrence with attempts 1, 2, 3 — not three occurrences | `test_native_retry_maps_to_one_occurrence_and_three_attempts` |
| ☐ | **Loop**: distinct occurrences | Each loop visit is a new occurrence, so repeated identical work is not misread as replay | `test_native_loop_creates_distinct_occurrences` |
| ☐ | **Parallel**: distinct occurrences | Concurrent branches of the same operation carry distinct occurrence identities, with the attempt-base cache protected against races | `test_native_parallel_branches_have_distinct_occurrences` |
| ☐ | **Resume**: attempts stay contiguous | After a checkpoint resume, where the framework resets its attempt counter to 1, the adapter offsets from the validated cumulative recorder prefix so the Nornyx attempt continues monotonically | `test_interrupt_resume_offsets_reset_node_attempt` |
| ☐ | Interrupts are control flow, not failure | A framework bubble-up (interrupt, parent command) re-raises without recording `runtime_failed`, leaving an incomplete attempt; a genuine exception records `runtime_failed` and re-raises | The same resume test asserts no `runtime_failed` |
| ☐ | Retry after success is impossible | The resulting stream must satisfy `AN_EVT_ATTEMPT_AFTER_SUCCESS` and `AN_EVT_ATTEMPT_GAP`: a successful occurrence cannot be retried, and attempts are contiguous from 1 | The validated stream |

**Table F.7 — Occurrence conformance.** Get this wrong and evidence becomes unusable in one of two
ways: legitimate retries trip replay detection, or genuine duplicates pass unnoticed.

## F.8 Continuous integration obligations

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | Tests run against the **real** pinned framework | Not a mock. The repository's jobs install `crewai==1.15.4` and `langgraph==1.2.2` and assert the installed version before running | Job log showing the version assertion |
| ☐ | **Zero skips are enforced mechanically** | Framework tests use an import-skip guard, so an extras-free environment would skip them silently. The dedicated jobs parse the JUnit XML and fail closed if *any* focused test skipped | The XML gate step and its output |
| ☐ | The core is built from the same commit, never fetched | The adapter jobs build the core wheel from the candidate commit rather than installing a published version | Job log |
| ☐ | Candidate identity is verified | The checked-out revision is compared against the pull-request head | Job log |
| ☐ | Installed-wheel smoke tests run outside all source roots | The built wheel is installed into a fresh virtual environment with the framework extra and exercised for allow and deny from outside the source tree | Smoke output |
| ☐ | **Network isolation is proved, not assumed** | The wheel smoke patches socket connection to block network use and asserts zero attempts; separate tests assert that enforcement and type construction perform no network input or output | `test_no_network.py`; the socket-patch smoke step |
| ☐ | Framework telemetry is disabled | Telemetry and tracing environment variables are set off in every framework job, so no test run can emit externally | The job environment block |
| ☐ | The published artifact is checked | The distribution builds and passes a packaging metadata check | Build log |
| ☐ | Release publication is tag-bound and fails closed | Publication requires a tag matching the expected pattern **and** equal to the version recorded at the tagged commit; a mismatch fails rather than publishing. Publishing uses trusted publishing with no stored token | The release workflow and its gate |

**Table F.8 — Continuous-integration conformance.** The zero-skip gate is the row most often
missing in practice. A green build whose framework tests all skipped proves nothing, and skipping is
the default behaviour when an extra is absent.

## F.9 Static declaration conformance

Separate machinery, separate meaning. The `.nyx`-level adapter and connector declarations of
Chapter 25 are checked statically; a conformance report from that machinery says nothing about a
Python framework adapter, and nothing in the repository links the two.

| ✅ | Item | Requirement | Evidence to attach |
|---|---|---|---|
| ☐ | Declared adapters carry the safety constants | `execution_mode: contract_only` and `live_connector_execution: false` are schema constants; they cannot be varied | The adapter declaration |
| ☐ | Non-goals are complete | The declaration draws its non-goals from the closed enumeration — live connector execution, production deployment, unrestricted adapter execution, credential loading, network calls, automatic approvals | The declaration |
| ☐ | Referenced artifacts resolve | Connector, policy, eval, and evidence references name declared entries | Checker output |
| ☐ | The report's safety block is all-false | `connectors_enabled`, `adapters_executed`, `network_used`, `commands_executed`, `credentials_loaded`, `adapter_contracts_executed`, and `live_connector_execution_allowed` are false constants, with `default_execution_mode: "disabled"` | The generated conformance report |
| ☐ | Per-adapter execution is `not_executed` | Each entry records `execution: "not_executed"` as a constant | The report |
| ☐ | Connector protocols are limited | Only `mcp` and `a2a`, with `approval_required: true` as a constant | The connector conformance block |
| ☐ | The report is not cited as adapter evidence | Written claims keep the two "adapter" concepts separate | The claim register wording |

**Table F.9 — Static declaration conformance.** What this establishes is precise and narrow:
adapter contracts declare safe modes, referenced artifacts exist, non-goals are complete, and the
report itself proves nothing was executed.

## F.10 Assembling the claim

Work the checklist, then write the claim in the form the evidence supports. A defensible statement
names four things: the surfaces, the versions, the tier, and the qualifier.

> The CrewAI synchronous tool-invocation surface, wrapped through
> `crewai.tools.BaseTool._run` under `crewai==1.15.4` with adapter 0.2.0 against interface 1.2, is
> under cooperative Tier 2 governance for the identities and capabilities declared in contract
> revision `git:…`. Coverage is the synchronous path only; asynchronous tool execution, agent
> invocation, task invocation, delegation, and handoff are declared unsupported. Bypassing the
> governed tool bypasses enforcement, and may leave no trace. Evidence is contract-state binding,
> not runtime proof.

**Listing F.1 — A claim the checklist can support.** Illustrative wording; the surface, version,
coverage, and boundary facts are drawn from the adapter's own documentation and inventory.

Three statements the checklist can never support, no matter how many rows are ticked. It cannot
support a claim of independent or mandatory enforcement, because bypass remains possible by
construction. It cannot support a claim of complete coverage, because an inventory can only name
surfaces someone thought of. And it cannot support a claim that recorded events are true, because
the producer is self-declared: validation establishes that supplied records conform to the exact
contract revision, and no more.

If a stakeholder needs more than that, the answer is Tier 3, which requires an external enforcement
and attestation system — authenticated producer identity, cryptographically verified attestation,
protected evidence capture, deployment-policy binding, independently controlled logging, and
demonstrated coverage of the claimed surfaces. None of those is provided or verified by Nornyx
alone, and Chapter 26 works through what supplying them would involve.
