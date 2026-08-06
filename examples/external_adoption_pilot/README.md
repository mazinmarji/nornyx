# External adoption pilot

**What it shows:** the same agent action, run three ways, from packages you
install rather than a repository you clone.

```bash
python -m examples.external_adoption_pilot
python -m examples.external_adoption_pilot --json --out adoption-record.json
```

No API key. No network beyond the install. No repository checkout at run time.

## The comparison

One action — an agent tool that reads governed context — executed three ways
through CrewAI's own ReAct executor via `Crew.kickoff()`:

| Variant | Action runs? | Authorization | Evidence |
| --- | --- | --- | --- |
| `ungoverned` | **yes** | none evaluated | **none** |
| `governed_authorized` | **yes** | evaluated, allowed | decision + observation stream |
| `governed_unauthorized` | **no** | evaluated, denied | denial recorded |

The first variant is the baseline most teams actually have today: the tool
works, and nothing anywhere asked whether it should have. That is not a failure
state — it is the normal state, and it is why the third variant is meaningful.

The second variant is what keeps the third honest. **A control that only ever
blocks is not governance, it is an outage.** The pilot fails if the authorized
path is blocked, exactly as it fails if the unauthorized path executes.

## Why this is a control, not a demo

`GOVERNANCE_EXPECTATION_UNMET` exists so that "the pilot passed" means something
stronger than "nothing crashed". Every governance check is a *comparison across
variants*, not an absolute assertion:

- the ungoverned baseline must really execute — otherwise a denial proves
  nothing, since the action might simply not work;
- the authorized path must execute and produce a `capability_allowed` event;
- the unauthorized path must execute **zero** times, record `capability_denied`,
  and record no success observation;
- requests and denials must pair up exactly. CrewAI's executor may retry a
  failed tool call, so the count is framework-controlled — but every request
  must still have been answered.

## Failure taxonomy

An adoption pilot's first duty is to tell a first-time user *which half broke*.
"It didn't work" is not a bug report.

| Class | Means | Attributed to |
| --- | --- | --- |
| `REGISTRY_INSTALL_FAILED` | The pinned distributions could not be installed from PyPI, or installed and are not importable | the distributions |
| `INSTALLED_VERSION_MISMATCH` | Something installed, but not the version requested | the distributions |
| `FRAMEWORK_EXTRA_UNAVAILABLE` | The `[crewai]` extra did not deliver a usable framework at its declared pin | the distributions |
| `SOURCE_TREE_LEAKAGE_DETECTED` | Code or data resolved from outside `site-packages`, or from inside a checkout | the distributions |
| `SCENARIO_EXECUTION_FAILED` | A variant did not complete, so the comparison could not be made | the distributions |
| `GOVERNANCE_EXPECTATION_UNMET` | Everything ran and governance did not hold | the distributions |
| `PILOT_INPUT_INVALID` | Bad arguments, or a local environment that could not be prepared | the caller — **never** the packages |

Exactly one class is caller-side, and every failure carries a `remedy` field
saying what to do next. `FRAMEWORK_EXTRA_UNAVAILABLE` is separate from a plain
install failure because the base package can be perfectly healthy while the
extra is not, and the fix differs.

This is a *separate* taxonomy from `examples/pip_only_conformance`, not an
import of it — the pilot has to be copyable and runnable outside the repository,
and importing a sibling example would defeat that. Overlapping classes keep the
same names and meanings deliberately.

## Where the governance contract comes from

The pilot does **not** ship a `.nyx` contract. It resolves the one the adapter
already ships as package data:

```
nornyx_agentic_adapters/conformance/fixtures/conformance_network.nyx
```

Two reasons. A first run should need no contract of your own. And it means the
pilot proves that shipped contract is usable by a *consumer*, not only by the
kit's own tests.

The contract is composed, locked, and loaded through the public
`nornyx.agentic` facade — `compose_document_governance`,
`build_agentic_network_lock`, `Authorizer` — rather than through any adapter
internal, so what you read here is what you would write yourself.

It declares two identities with asymmetric capabilities, which is what makes an
A/B/C possible without editing anything: `identity.researcher.local` holds
`read_governed_context`; `identity.reviewer.local` does not hold
`propose_research_finding`.

**To substitute your own contract**, replace the resolution in `scenario.py`
(`FIXTURE_PACKAGE` / `FIXTURE_NAME`) with a path to your `.nyx`, and change the
identity and capability constants to match what it declares.

## Determinism

`decision_at` is pinned to a fixed instant inside the contract's validity
window — never `now()` — so two runs produce identical evidence and can be
diffed. The model is a local `BaseLLM` subclass returning fixed strings.

## The adoption record

`--json` (or `--out`) emits a machine-readable record: environment and
`site-packages`, resolved distribution versions, every import origin, the
contract's origin and subject revision, all three variants with execution
counts and event types, and a `governance_delta` summarising the comparison.

Two safety fields are reported with their **kind**, not merely their value:

| Field | Kind | Meaning |
| --- | --- | --- |
| `external_model_service_called` | **structural constant** | The pilot ships a scripted local model and calls no service. |
| `scripted_in_process_model_called` | **observed** | Measured per run. `true` here — CrewAI's executor really drives the scripted model, which is what makes the run native rather than a direct wrapper call. |

Reporting only the constant would read as evidence while measuring nothing.

## Running without a clone

`scripts/run_external_pilot_standalone.py` copies only this package to a
directory outside every checkout, strips the repository from the child's import
path, runs it there, and proves no repository path appears in the record.

Checkout detection is marker-based rather than parent-depth based: a fixed-depth
rule applied to a copied package would name an arbitrary ancestor as "the
repository", and since the clean environment is created under the system temp
root, that could forbid the very directory the installation lives in.

## Versions

`ADAPTER_VERSION` and `CREWAI_VERSION` are constants, not reads of repository
metadata — the subject is what an external adopter can install today. Advance
them deliberately after a publication.

The **core** `nornyx` version is recorded but not pinned. The adapter declares
`nornyx>=1.10,<2`, so a new core minor is a supported resolution; asserting an
exact core version would break this pilot the day 1.12.0 publishes, which is the
opposite of what an adoption check should do.

## Relationship to the CrewAI A/B benchmark

`examples/crewai_governance_benchmark` is the fuller A/B story, and this pilot
does **not** reuse it — because it cannot. That benchmark is repository source;
it is not shipped in any published distribution, so a pip-install-only consumer
has no way to obtain it. Reusing it would have required either publishing it as
a distribution (a version and release action, out of scope here) or having the
pilot clone the repository, which is the exact thing being disproved.

So this pilot reproduces the benchmark's *shape* — same ungoverned/governed
comparison, same fail-closed claim — using only what a consumer can install. The
benchmark remains the richer showcase for readers who do have a checkout.

## Assurance boundary

ADR-0040 **Tier 2, cooperative**, declared wrapped surfaces only. This pilot
demonstrates the tool-invocation surface under one contract. It does not
authenticate agents or approvers, does not prove recorded events truthful, does
not prevent bypass outside controlled paths, is not whole-application coverage,
and makes no Tier 3 claim.
