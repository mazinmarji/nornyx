# Pip-only registry-backed distribution conformance

Installs a **published** `nornyx-agentic-adapters` from PyPI into a clean
environment, resolves its bundled conformance schema and contract fixture
through `importlib.resources` from the installed wheel, runs the conformance
kit, and emits an independently auditable record of where every artifact
actually came from.

No repository checkout is used, imported, or required at run time.

```bash
python -m examples.pip_only_conformance            # human-readable summary
python -m examples.pip_only_conformance --json     # full audit record
python -m examples.pip_only_conformance --version 0.3.0
```

## Why this is not an installation smoke test

A smoke test answers *did `pip` exit 0*. This answers two harder questions:

1. **Is the artifact on the index the one we think we published?** Exact
   version, resolved from distribution metadata and from `__version__`, which
   must agree.
2. **Is its package data really there, and really intact?** The conformance kit
   resolves a JSON schema and a `.nyx` contract fixture through
   `importlib.resources`. Package data is exactly what a wheel silently drops
   when it is not declared in `[tool.setuptools.package-data]` — and that defect
   is invisible in an editable install and in the repository test run. It
   surfaces only from an installed distribution, which is what this example is.

So this run can fail for a genuine distribution defect, and it names which one.

## What it proves, precisely

| Claim | How |
| --- | --- |
| The artifact came from the index | Fresh venv, `pip install nornyx-agentic-adapters==<version>`, `--no-cache-dir`, `PYTHONPATH` scrubbed |
| The code executing is the installed code | Every import origin asserted under the environment's `site-packages` and outside every repository root |
| Bundled resources exist | Resolved through `importlib.resources`, the same call path the kit itself uses |
| Bundled resources are intact | Schema `$id` and closure checked; fixture composed, locked, and loaded as a real governance contract |
| The kit reaches a conformant result | `run_conformance` over the base suites, report validated against the bundled schema, run twice for determinism |

## Failure taxonomy

Each class answers one question and no other. The point is attribution: a run
that can only say "it did not work" cannot separate a broken **distribution**
from a broken **invocation**.

| Class | Means | Attributed to |
| --- | --- | --- |
| `REGISTRY_INSTALL_FAILED` | The named version could not be installed from the index, or installed but is not importable | the distribution |
| `INSTALLED_VERSION_MISMATCH` | Something installed, but the resolved version is not the one requested, or `__version__` disagrees with the metadata | the distribution |
| `SOURCE_TREE_LEAKAGE_DETECTED` | Code or data resolved from outside `site-packages`, or from inside a repository root | the distribution |
| `PACKAGED_RESOURCE_MISSING` | A bundled resource could not be resolved through `importlib.resources` | the distribution |
| `PACKAGED_RESOURCE_INVALID` | A resource resolved, but its content failed semantic validation | the distribution |
| `CONFORMANCE_EXECUTION_FAILED` | The kit ran and did not reach a conformant result, or its report failed schema validation | the distribution |
| `EXAMPLE_INPUT_INVALID` | The example was invoked wrongly | the caller — **never** the package |

### `MISSING` and `INVALID` are deliberately separate

"Present" and "correct" are different claims. Collapsing them would let a
truncated, stale, or wrong-identity resource pass as healthy. `MISSING` means
resolution failed. `INVALID` means resolution succeeded and then:

- the report schema declared an `$id` other than
  `nornyx.agentic_runtime_conformance.v1`, or
- the schema left an object definition open (`additionalProperties` not `false`),
  so it could not reject a malformed report, or
- the contract fixture did not compose, lock, and load as a governance contract.

The fixture check builds an `Authorizer` rather than reading bytes. Reading
bytes would prove the file shipped; building an authorizer proves it shipped
*intact*.

### `SOURCE_TREE_LEAKAGE_DETECTED` rests on positive evidence

The check asserts on **observed import origins** — `__file__` for the package
and the kit, plus the resolved path of every bundled resource. Each must lie
under the active environment's `site-packages` and outside every repository
root, which the runner passes in explicitly.

It is written this way on purpose. Confirming that no checkout is present would
prove nothing about where an import actually resolved; an editable install or a
stray `PYTHONPATH` can put repository paths on `sys.path` in ways an absence
check would bless.

## The audit record

`--json` emits the full record: distribution name and version, environment and
`site-packages`, every import origin, every resource origin, the fixture's
subject revision, the conformance outcome and case count, and the safety block.

Two fields are reported with their **kind**, not merely their value:

| Field | Kind | Meaning |
| --- | --- | --- |
| `external_model_service_called` | **structural constant** | A design property of the kit: it contacts no external model service or endpoint. |
| `scripted_in_process_model_called` | **observed** | Measured per run. A native CrewAI run reports `true` — the kit ships a scripted offline model that CrewAI's executor calls. |

Emitting only the constant would read as evidence while measuring nothing. That
is the exact defect the M2-E review caught and corrected before 0.3.0 shipped,
and this example is built not to reintroduce it.

**On the base pip-only path, `scripted_in_process_model_called=false` is the
legitimate observed value** — no framework extra is installed, so no suite
instantiates a model. That `false` is a measurement, not a default.

## Version pinning

`DEFAULT_VERSION` is a constant, not a read of the repository's own
`adapters/nornyx-agentic-adapters/pyproject.toml`.

The subject here is the artifact **on the index**, and those two values diverge
for the entire window between a release-preparation merge and the actual
publication. Reading the repository version would turn every release PR into a
spurious `REGISTRY_INSTALL_FAILED`. Advance the constant deliberately, after a
publication, as its own reviewed change.

## Assurance boundary

Unchanged from the kit itself: ADR-0040 **Tier 2, cooperative**, declared
wrapped surfaces only. This example verifies distribution and resource
integrity plus a conformant base-suite run. It does not authenticate agents or
approvers, does not prove recorded events truthful, does not prevent bypass
outside controlled paths, is not whole-application coverage, and makes no
Tier 3 claim.

## Network

The install step needs the index; that is the entire point. Everything after it
is offline. The repository's unit tests for this example run without network —
they cover the taxonomy, containment logic, schema-closure checks, and envelope
classification. The live registry run is exercised by the `pip-only-example` CI
job and by invoking the module directly.
