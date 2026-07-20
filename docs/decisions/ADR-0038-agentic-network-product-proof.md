# ADR-0038 — End-to-End Product Proof and External-Evaluation Boundaries (AN-006)

- Status: Proposed (implementation authorized by the owner's AN-completion goal;
  human review remains the final closure authority)
- Date: 2026-07-19
- Decision owner: human repository owner

## Context

AN-002..AN-005 prove engineering correctness. The program also requires a
reproducible, product-facing demonstration answering why Nornyx adds value
alongside Git, CI scripts, Promptfoo-style evaluation, and agent frameworks —
without overclaiming and without executing external tools.

## Decision

### Canonical demonstration

`examples/agentic_network_support/` — the **Governed Customer Support
Network**: identities `SupportCoordinator`, `PolicyAdvisor`, `RefundAgent`,
`EscalationAgent`, plus the human role `HumanApprover` (a role, never an agent
identity). Capabilities cover reading sanitized requests, classification,
policy retrieval, bounded refund proposal, high-value escalation, customer-safe
response, sanitized-context sharing, and human-approval requests. Fake data
only. The demo proves: non-human identities cannot approve; low-risk actions
allowed; high-risk refund requires human approval; capability escalation
rejected; cross-zone sharing of private memory/credentials rejected; valid
delegation accepted; invalid onward delegation rejected; handoff transfers
responsibility not authority; external prompt-evaluation evidence consumed;
one contract governs both CrewAI and LangGraph adapters; both emit conformant
evidence; Nornyx validates the evidence against the exact lock and revision.

### External evaluation evidence

Nornyx does not execute Promptfoo. A bounded local importer
(`nornyx/eval_import.py`, CLI `nornyx eval-import promptfoo <report> --out`)
converts a Promptfoo-style results JSON into the results format already
consumed by `nornyx eval-run --results`, validating the input shape,
recording producer and version, binding the normalized evidence to the report
artifact's sha256 and to the declared subject revision, and rejecting
malformed or mismatched reports. Threshold evaluation reuses `eval_runtime`
unchanged. Promptfoo is not a dependency. Nornyx does not replace Promptfoo,
LangSmith, or observability platforms.

### Reference CI

`scripts/agentic_network_ci.py` — a documented executable script, safe to run
offline after dependencies are installed, performing: wheel build/install
smoke, contract check, profile/module resolve, deterministic control
generation, generated-artifact drift verification, network-lock verify,
external eval-result import + threshold validation, CrewAI demonstration,
LangGraph demonstration, runtime-event validation, human-approval and
revision-binding validation, audit-package assembly, nonzero exit on any
violation. No external system is modified.

### Before/after and measurable proof

`docs/agentic-network/` documents the same scenario without Nornyx
(fragmented per-framework config, ad-hoc YAML, per-tool evidence, checklist
approvals) and with Nornyx (one contract, deterministic controls, shared
semantics, revision-bound approval, evidence normalization, stale-control
detection, fail-closed diagnostics, audit package), with the boundary
statement: Git records changes; CI executes checks; Promptfoo-style tools
produce evaluation results; agent frameworks execute workflows; Nornyx
defines and validates the governance contract tying these surfaces together.
Measured results (counts, hashes, pass/fail outcomes, network/process
observation) are recorded from actual runs; no invented statistics.

### Positioning language

“Nornyx is a design-time governance compiler, deterministic control-artifact
generator, and revision-bound evidence validator for AI software and agentic
systems.” Nornyx is not described as a runtime control plane, policy proxy,
orchestrator, observability backend, Promptfoo/LangSmith replacement,
identity provider, secrets manager, MCP runtime, A2A runtime, or deployment
system.

## Rejected alternatives

- Executing Promptfoo from Nornyx — rejected: subprocess execution is
  prohibited in core.
- A GitHub Actions-only workflow — rejected as the primary vehicle: a local
  executable script is verifiable offline in this environment; a CI YAML can
  mirror it later without changing behavior.
- Synthetic “enterprise” claims — rejected: only measured evidence.

## Compatibility effect

Additive examples, docs, one importer module, and one CLI command
(`eval-import`). No existing behavior changes.

## Security boundaries

Fake data only; no personal data, credentials, live integrations, or
endpoints; importer reads bounded local JSON only.

## Public API / CLI / packaging effect

CLI adds `eval-import`; the example ships in the repo (and the packaged
example set only if size-appropriate; decision: repo-only, because packaged
examples remain the frozen `.nyx` demo set). No stable public export.

## Determinism requirements

Demo scripts and the CI script produce deterministic artifacts and reports;
recorded hashes must be reproducible on rerun.

## Human authority

The demo's approval evidence is an explicit human-produced record bound to
the exact revision; the AI-approval path must be demonstrably rejected.

## Non-goals

Benchmarking frameworks, measuring model quality, replacing evaluation or
observability tools, production rollout guidance.

## Test obligations

Every documented command executes; example passes validation; importer
positive/negative matrix; CI script end-to-end offline; measurable-proof
numbers generated from runs; documentation accuracy checks.

## Migration implications

None.

## Residual risks

The demonstration proves the governance chain on synthetic runs; it cannot
prove that a production runtime would emit honest evidence — stated in docs.
