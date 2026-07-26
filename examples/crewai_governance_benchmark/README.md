# Nornyx governance A/B benchmark — CrewAI

A reproducible, offline benchmark that measures **what governance actually
changes** about an agentic application, and lets an external developer verify the
difference rather than take it on faith.

One customer-support and financial-remediation workflow is run twice:

- **Variant A** — an ordinary CrewAI application.
- **Variant B** — the *same* agents, tasks, model, inputs, business rules, and
  business callables, with each tool built by the supported Nornyx CrewAI adapter.

The intended variable is the presence of governance. Everything else is shared
code, not a copy.

```bash
python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out
```

Exits non-zero unless every clause of the benchmark contract holds **and** the
complete evidence stream validates. There is no partial pass: the verdict is
`GO` or `NO_GO`.

- **Just want to read the outcome?** → [`results/`](results/) has a recorded run,
  including a self-contained [`dashboard.html`](results/dashboard.html).
- **Want to run and verify it yourself?** → [`REVIEWER_QUICKSTART.md`](REVIEWER_QUICKSTART.md).

## What this is not

Not an LLM-quality benchmark — the model is scripted and identical in both arms.
Not a production-performance benchmark — the timing figures are a local
microbenchmark and say so. Not a marketing demo — the negative control, the
fairness control, the unsupported surfaces, and the three defects this benchmark
found in the audited packages (now fixed, and regression-tested) are all part of
the deliverable.

## Which Nornyx path this uses

The **supported** one, as of the audited revision:

| Layer | What is used |
|---|---|
| Core SPI | `nornyx.agentic` (ADR-0039, `SPI_VERSION == "1.0"`) — `load_authorizer`, `Authorizer.evaluate`, `EvidenceRecorder` |
| Adapter | `nornyx-agentic-adapters` 0.1.0 — `SurfaceBinding`, `enforce`, `crewai_adapter.make_governed_tool`, `resolve_identity` |
| Framework | `crewai==1.15.4` (the single version the adapter supports, enforced at import) |

It does **not** use the legacy, unpackaged reference kernel, which now lives
under its own import name at `integrations/nornyx_reference_adapters/` (it used
to claim the same name as the installed distribution — see
[`FINDINGS.md` F3](FINDINGS.md), resolved). The older
[`examples/crewai_nornyx_comparison`](../crewai_nornyx_comparison) example targets
Nornyx 1.7.0 and that legacy kernel; it is preserved unchanged and still has its
own tests. This benchmark is its successor on the supported stack, not a
replacement for its regression coverage.

`nornyx` is published on PyPI. **`nornyx-agentic-adapters` is not** — it is
installed from this repository, and `environment.json` records that fact.

## How prevention is proved

Not by catching an exception and calling it a block. Every business tool writes
to a side-effect ledger, and every governance decision is stamped on the *same*
monotonic clock, which makes three things checkable rather than asserted:

- **Did the work run?** A denied scenario must hold attempts and completions at
  exactly zero; an allowed scenario at exactly one.
- **Was the decision recorded first?** The k-th entry into a business callable
  must be preceded by a k-th recorded decision — so a reused authorization fails
  the check even though a naive "decision before first execution" test would pass.
- **Did a failure get recorded as a success?** An authorized action that then
  fails must produce zero completions and no `tool_invoked` observation.

## Scenario matrix

19 scenarios across five stages, which are reported separately and never summed.

| # | Scenario | Stage | Governed outcome |
|---|---|---|---|
| S01 | Valid low-risk action | runtime | `ALLOWED` |
| S02 | High-risk external action with valid human approval | runtime | `ALLOWED` |
| S03 | Undeclared capability | runtime | `CAPABILITY_UNKNOWN` |
| S04 | Known capability used by the wrong identity | runtime | `CAPABILITY_DENIED` |
| S05 | Unknown / unmapped runtime identity | binding | `IDENTITY_UNKNOWN` |
| S06 | High-risk action without approval | runtime | `CROSSING_APPROVAL_REQUIRED` |
| S07 | AI-generated (non-human) approval | runtime | `APPROVAL_NON_HUMAN` |
| S08 | Approval bound to the wrong action | runtime | `APPROVAL_ACTION_MISMATCH` |
| S09 | Expired approval | runtime | `APPROVAL_STALE` |
| S10 | Restricted-data sharing | runtime | `SENSITIVE_SHARING` |
| S11 | Undeclared trust-zone crossing | runtime | `ZONE_CROSSING_DENIED` |
| S12 | Contract / lock drift | load | `LOCK_STALE` |
| S13 | Malformed governance metadata | runtime | `REQUEST_MALFORMED` |
| S14 | Governed action that fails after authorization | runtime | `ALLOWED`, then fails; 0 completions |
| S15 | Deliberate unwrapped-tool bypass | **bypass** | `NOT_GOVERNED` — runs in both variants |
| S16 | Valid bounded delegation | runtime | `ALLOWED` via delegation |
| S17 | Runtime revision mismatch | runtime | `REVISION_MISMATCH` |
| S18 | Application business rule | **application** | refused by the app in both variants |
| S19 | Compliance role closes the case | runtime | `ALLOWED` |

**S15 and S18 are controls, not wins.** S15 executes under governance on purpose —
enforcement is cooperative, and a tool that never enters the adapter is never
evaluated. S18 is refused by the application's own rule in both arms, so the
benchmark cannot credit Nornyx for a control the baseline already had. Neither
counts toward any prevention metric.

## Outputs

| File | What it is |
|---|---|
| `benchmark.json` | canonical machine-readable results, metrics, and contract checks |
| `benchmark.md` | full technical report with mermaid diagrams and the heat map |
| `dashboard.html` | self-contained static dashboard (no CDN, no script, no network) |
| `environment.json` | exact installed versions and install provenance |
| `plain_results.json` / `governed_results.json` | per-scenario results plus the full ledger timeline |
| `nornyx_runtime_events.json` | the governed evidence stream |
| `nornyx_evidence_report.json` | Nornyx's validation of that stream |
| `validation_manifest.json` | sha256 of every governance input, benchmark source file, and output, plus the candidate digest |

## Findings

Building this benchmark surfaced three real defects in the audited packages. All
three are **fixed in this repository**, each with its own regression test, and
the reproductions are kept in [`FINDINGS.md`](FINDINGS.md) so the fixes stay
auditable:

- **F1** — a correctly refused **non-human approval** emitted an event the
  evidence validator rejected, so exercising the product's headline guarantee
  made the stream unvalidatable.
- **F2** — a **delegated capability**'s `tool_invoked` event omitted the
  authorizing delegation, so delegation and validatable evidence were mutually
  exclusive on the supported CrewAI path.
- **F3** — the legacy `integrations/` tree **claimed the supported adapter's
  import name**, so the two could not coexist in one Python process.

None of them ever affected an enforcement result — every decision in every run
was correct and every prevented callable stayed at zero side effects. What they
blocked was a clean *evidence* claim. With the fixes in place the full event
stream validates with zero diagnostics and the verdict is `GO`.

## Reading a committed result

`results/` is a **snapshot of one run**, not a continuously verified claim. Two
digests in `validation_manifest.json` are reproducible on any machine and are the
ones worth comparing:

- `candidate_digest` — folds every governance input and benchmark source file
  into one value, so it identifies the exact candidate a result came from. It is
  also recorded in `benchmark.json`, `benchmark.md`, and `dashboard.html`.
- `deterministic_outputs_digest` — folds only the outputs that are byte-stable
  across machines (the evidence stream, its validation report, and the two
  per-scenario result files).

`benchmark.json`, `benchmark.md`, `dashboard.html`, and `environment.json` embed
installed versions, the host platform, and local wall-clock timings, so their
bytes legitimately differ between machines and they are marked
`"deterministic": false` in the manifest. No artifact contains an absolute local
path. Rerun the benchmark rather than trusting the snapshot.

## Layout

```
examples/crewai_governance_benchmark/
├── README.md                  this file
├── REVIEWER_QUICKSTART.md     run it and check the result yourself
├── EXTERNAL_REVIEW.md         reviewer questions
├── FINDINGS.md                defects found against the audited revision
├── benchmark.py               entrypoint; asserts the contract, exits non-zero
├── config.py                  offline kill switches, pinned instant, environment capture
├── business.py                the shared business layer (both variants)
├── ledger.py                  side-effect ledger on one monotonic clock
├── deterministic_llm.py       scripted offline BaseLLM
├── runtime.py                 shared Agent/Task/Crew construction
├── scenarios.py               the scenario matrix (declarative data only)
├── variant_plain.py           Variant A
├── variant_governed.py        Variant B
├── metrics.py                 metric derivation from execution
├── report.py                  terminal / markdown / dashboard renderers
├── manifest.py                validation manifest
├── results/                   a recorded run: dashboard.html, reports, evidence, manifest
└── contract/
    ├── remediation_network.nyx        the governed agent-network contract
    ├── nornyx.agentic_network.lock    its verified lock
    ├── control_artifacts/              deterministic generated control artifacts
    ├── governance_evidence/           evidence records referenced by the contract
    └── eval/                          eval fixtures referenced by the contract
```

Tests: `tests/test_crewai_governance_benchmark.py`.
