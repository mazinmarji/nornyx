# Before/After and Positioning

## The product question

> Why add Nornyx instead of relying only on Git, ordinary YAML, CI scripts,
> Promptfoo-style evaluation, or framework-specific hooks?

Each of those tools is competent at its own job — this comparison does not
strawman them. The gap Nornyx fills is the **governance contract tying those
surfaces together**:

- **Git records changes** — but a diff does not say whether a delegation
  escalates scope or an approval is stale.
- **CI executes checks** — but each check script re-invents its own notion of
  identity, capability, and approval.
- **Promptfoo-style tools produce evaluation results** — but nothing binds a
  passing result to the exact contract revision a human approved.
- **Agent frameworks execute workflows** — but each framework's hooks speak
  its own dialect, so governance rules are re-implemented per framework.
- **Nornyx defines and validates the governance contract tying these
  surfaces together** — one declared model, deterministic generated
  controls, and revision-bound evidence validation.

## The same scenario, without Nornyx

A team running the customer-support network without Nornyx typically holds:
CrewAI agent configs and LangGraph node wiring (two identity dialects),
hand-written capability rules in each codebase, a prompt/eval config with
its own pass criteria, CI scripts asserting fragments of each, an approval
checklist in a wiki or PR template, ad-hoc runtime log formats per
framework, and no single object binding all of it to a revision. None of
that is wrong — it is fragmented: renaming one agent silently desynchronizes
five files, and no check notices that the approval predates the change.

## The same scenario, with Nornyx

- one authoritative contract:
  `examples/agentic_network_support/support_network.nyx`;
- deterministic generated controls (10 artifacts, byte-stable);
- shared identity and capability semantics across CrewAI and LangGraph via
  `framework_bindings`;
- revision-bound human approval with expiry and invalidation conditions;
- evidence normalization: one `nornyx.agentic_runtime_events.v1` stream from
  both frameworks;
- stale-control detection: `lock-check` fails on any semantic drift;
- fail-closed governance diagnostics with stable codes;
- one audit package assembled by the reference CI.

## Measured demonstration results (from `run_demo.py` + `agentic_network_ci.py`)

| Measure | Result |
| --- | --- |
| Framework implementations governed by one contract | 2 (CrewAI adapter path, LangGraph `StateGraph`) |
| Generated artifacts | 10 |
| Governed identities / capabilities / trust zones | 4 / 8 / 2 |
| Allowed scenarios (adapter level) | 10 |
| Deliberately blocked scenarios | 11 (5 adapter-level + 6 static) |
| AI-approval rejection | `AN_ADAPTER_APPROVAL_NON_HUMAN` (adapter) and `AN_APPROVAL_HUMAN_REQUIRED` (static) |
| Capability escalation rejection | `AN_ADAPTER_CAPABILITY_DENIED` / `AN_CAPABILITY_ESCALATION` |
| Sensitive-sharing rejection | `AN_ADAPTER_SENSITIVE_SHARING` / `AN_DELEGATION_SENSITIVE_SHARING` |
| Contract-drift / stale-lock detection | `AN_LOCK_SOURCE_STALE` |
| Runtime-evidence validation | pass (34 CrewAI-path events, 14 LangGraph events) |
| External eval evidence | imported Promptfoo-style report, 4/4 thresholds passed |
| Network attempts / external commands during validation | 0 / 0 (observed by tests) |

Exact per-run numbers are written to `demo_out/demo_summary.json`; no
performance, adoption, enterprise, or cost claims are made.

## Positioning language

Nornyx is a design-time governance compiler, deterministic control-artifact
generator, and revision-bound evidence validator for AI software and agentic
systems. It validates supplied local evidence, binds evidence to an exact
revision, rejects undeclared capabilities, generates deterministic
declarations, and provides optional reference enforcement hooks. It does not
operate the external runtime, and it is not a runtime control plane, policy
proxy, orchestrator, observability backend, Promptfoo/LangSmith replacement,
identity provider, secrets manager, MCP runtime, A2A runtime, or deployment
system.
