# End-to-End Tutorial — Governed Customer Support Network

Everything below runs offline with fake data from the repository root. The
example lives in `examples/agentic_network_support/` and its contract is
`support_network.nyx`.

## 1. Validate the contract

```text
nornyx check examples/agentic_network_support/support_network.nyx --as-of 2026-07-17T00:00:00Z
```

This runs the stable checks plus the composed `agentic_network` governance:
schema-closed blocks, `agentic_network_foundation.v1`, and
`agentic_network_delegation.v1`.

The example's approval and evidence records carry fixed July 2026 dates (its
agent identities, memberships and delegations expire on 2026-12-01), so this
tutorial evaluates them at one fixed instant, `--as-of 2026-07-17T00:00:00Z`.
Run without `--as-of`, `nornyx check` uses the current time and fails with
expiry diagnostics such as `AN_APPROVAL_EXPIRED`, which is the expiry
machinery working, not a broken example. The same holds for
`examples/agentic_network.nyx`, whose approval and evidence expired on
2026-07-24 and whose identities and memberships expired on 2026-08-01. The dates are deliberately not refreshed:
the evidence records are fixed demonstration data bound by content hashes, and
a real contract's approvals and evidence must be renewed by their authorities,
not by editing dates.

## 2. Inspect the effective governance

```text
nornyx governance explain examples/agentic_network_support/support_network.nyx --as-of 2026-07-17T00:00:00Z --json
```

## 3. Generate deterministic controls

```text
nornyx agentic-network generate examples/agentic_network_support/support_network.nyx --out generated/agentic_network --as-of 2026-07-17T00:00:00Z
```

Ten canonical, timestamp-free JSON declarations are produced (see
[05_PROTOCOL_DECLARATIONS.md](05_PROTOCOL_DECLARATIONS.md) and
[07_NETWORK_LOCK.md](07_NETWORK_LOCK.md)). Rerunning produces byte-identical
output.

## 4. Write and verify the network lock

```text
nornyx agentic-network lock examples/agentic_network_support/support_network.nyx --artifacts generated/agentic_network --out nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z
nornyx agentic-network lock-check examples/agentic_network_support/support_network.nyx --lock nornyx.agentic_network.lock --artifacts generated/agentic_network --as-of 2026-07-17T00:00:00Z
```

Any later edit to a governed record makes `lock-check` fail with
`AN_LOCK_SOURCE_STALE` and the affected record/artifact mismatches.

## 5. Import external evaluation results

```text
nornyx eval-import promptfoo examples/agentic_network_support/eval/promptfoo_results.json --eval-name support_response_quality --subject-revision git:feedfacefeedfacefeedfacefeedfacefeedface --out dist/imported_eval_results.json
nornyx eval-run examples/agentic_network_support/support_network.nyx --results dist/imported_eval_results.json --repo examples/agentic_network_support --strict
```

Nornyx validates the declared thresholds and dataset integrity; it does not
execute Promptfoo (see [04_EXTERNAL_EVAL_EVIDENCE.md](04_EXTERNAL_EVAL_EVIDENCE.md)).

## 6. Run the governed demonstration

```text
python examples/agentic_network_support/run_demo.py --out demo_out
```

The demo drives the CrewAI-shaped and LangGraph adapters through allowed,
denied, delegated, handed-off, human-approved, and deliberately blocked
scenarios, then writes `crewai_events.json`, `langgraph_events.json`,
validation reports, and `demo_summary.json` with the measured outcomes.

## 7. Validate the emitted runtime evidence

```text
nornyx agentic-network evidence-validate examples/agentic_network_support/support_network.nyx --events demo_out/crewai_events.json --lock demo_out/nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z --strict
nornyx agentic-network evidence-validate examples/agentic_network_support/support_network.nyx --events demo_out/langgraph_events.json --lock demo_out/nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z --strict
```

## 8. Run the whole chain as CI

```text
python scripts/agentic_network_ci.py --out dist/agentic-network-ci
```

See [11_REFERENCE_CI.md](11_REFERENCE_CI.md). Add `--wheel` to build the
candidate wheel and run every Nornyx step from a clean installation of it.
