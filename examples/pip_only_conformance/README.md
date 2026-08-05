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
| The artifact came from PyPI | Fresh venv; every `PIP_*` variable dropped and `PIP_CONFIG_FILE` pointed at the null device; `--index-url https://pypi.org/simple` passed explicitly |
| It was the published **wheel**, not a local build | `--only-binary nornyx-agentic-adapters`, plus the artifact type read back out of pip's installation report |
| Which exact file was consumed | `pip install --report` parsed for URL, host, filename and SHA-256 |
| The code executing is the installed code | Every import origin asserted under the environment's `site-packages` and outside every repository root |
| Bundled resources exist | Resolved through `importlib.resources`, the same call path the kit itself uses |
| Bundled resources are intact | Schema `$id` and closure checked; fixture composed, locked, and loaded as a real governance contract |
| The kit reaches a conformant result | `run_conformance` over the base suites, report validated against the bundled schema, run twice for determinism |
| The report is not merely self-reported | The probe's envelope is cross-checked against the process exit status |
| It works without a clone | `scripts/run_pip_only_example_standalone.py` copies only this package outside every checkout and runs it there |

## Failure taxonomy

Each class answers one question and no other. The point is attribution: a run
that can only say "it did not work" cannot separate a broken **distribution**
from a broken **invocation**.

| Class | Means | Attributed to |
| --- | --- | --- |
| `REGISTRY_INSTALL_FAILED` | The version could not be obtained from PyPI as a published wheel — install failed, timed out, could not launch, produced no report, or produced one whose provenance does not hold up — or it installed and is not importable | the distribution |
| `INSTALLED_VERSION_MISMATCH` | Something installed, but the resolved version is not the one requested, or `__version__` disagrees with the metadata | the distribution |
| `SOURCE_TREE_LEAKAGE_DETECTED` | Code or data resolved from outside `site-packages`, or from inside a repository root | the distribution |
| `PACKAGED_RESOURCE_MISSING` | A bundled resource could not be resolved through `importlib.resources` | the distribution |
| `PACKAGED_RESOURCE_INVALID` | A resource resolved, but its content failed semantic validation | the distribution |
| `CONFORMANCE_EXECUTION_FAILED` | The kit ran and did not reach a conformant result, its report failed schema validation, or the probe process and its own report disagree | the distribution |
| `EXAMPLE_INPUT_INVALID` | The fault is local to the caller: bad arguments, or an environment that could not be prepared | the caller — **never** the package |

Every one of the seven is forced through the public path by a fault-injection
test, so the taxonomy is a set of reachable outcomes rather than a list of
names. `EXAMPLE_INPUT_INVALID` covers *any* demonstrably local fault, not just
bad arguments — blaming the published distribution because a machine could not
create a virtual environment would be a false accusation, and attribution
correctness is the load-bearing property here.

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

## Provenance: which file, from where

Version metadata proves what a distribution *calls itself*. It does not prove
where the file came from, whether it was a wheel or an sdist built on the spot,
or which bytes were consumed. Those are separate claims, so they are made
separately.

The evidence is pip's own installation report (`pip install --report`), which
records the download URL and archive hash per resolved requirement. The audit
record carries `provenance.host`, `filename`, `artifact_type`, `version`,
`sha256`, plus the derived `from_pypi` and `is_wheel`.

Three isolation measures make "from PyPI" a checked fact rather than an
assumption:

- **Every `PIP_*` variable is dropped**, not filtered. `PIP_INDEX_URL` and
  `PIP_EXTRA_INDEX_URL` can silently redirect resolution to a mirror or a
  private index — which would make "installed from PyPI" false while everything
  still appeared to work.
- **`PIP_CONFIG_FILE` is pointed at the null device**, because a user- or
  site-level `pip.conf` carries the same redirection.
- **`--index-url` is passed explicitly** rather than relying on the default.

An sdist is rejected even when its version is correct: an sdist is built
locally, so it is not the artifact consumers actually receive.

## Process truth

An envelope is a claim; the exit code is the operating system's account of the
same run. The runner requires them to agree — `pass` with a nonzero exit, or
`fail` with a zero exit, becomes `CONFORMANCE_EXECUTION_FAILED` rather than
being taken at face value. A probe that crashed after printing `pass` must not
read as a passing run, and a failing run that exits `0` would slip through any
exit-code-based gate.

Timeouts, launch failures, and environment-creation failures are converted into
classified failures too; none of them escape as a raw exception.

## Running without a clone

The claim is that this works without cloning `nornyx`, and running it from the
repository does not test that — the launcher itself came from the checkout.

`scripts/run_pip_only_example_standalone.py` performs the acquisition the claim
implies: it copies **only** this package to a directory outside every checkout,
strips the repository from the child's import path, runs it there, and then
proves from the emitted record that no path inside the repository appears
anywhere in it.

Checkout detection is marker-based rather than parent-depth based, for a
concrete reason: a fixed-depth rule applied to a copied package would name an
arbitrary ancestor directory as "the repository" — and since the clean venv is
created under the system temp root, that could forbid the very directory the
installation lives in. When there is genuinely no checkout above the package,
the example correctly reports no repository roots.

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
