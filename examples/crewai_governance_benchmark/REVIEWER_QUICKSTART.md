# Reviewer quickstart

Everything below runs offline, needs no API key, and makes no network call once
installed. You should be able to go from a clean clone to a verified result
without asking anyone a question. If you cannot, that is a defect — please say so
in `EXTERNAL_REVIEW.md`.

## Prerequisites

| Requirement | Why |
|---|---|
| **Python 3.10–3.13** | `crewai==1.15.4` declares `>=3.10,<3.14`. **Python 3.14 will not work** — pip silently reports "no matching distribution" rather than a version error. |
| git | to clone the repository |
| ~1 GB disk | CrewAI pulls a large dependency tree |
| No API key | the benchmark uses a scripted offline model |

Check your interpreter first — this is the single most common failure:

```bash
python -V        # must be 3.10.x – 3.13.x
```

If your system Python is 3.14, install a supported one. With `uv`:

```bash
uv python install 3.13
uv venv --python 3.13 .venv
```

## Clean-environment installation

```bash
git clone https://github.com/mazinmarji/nornyx
cd nornyx

python -m venv .venv                 # or: uv venv --python 3.13 .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -e ".[dev]"                          # nornyx core + test tooling
pip install -e ./adapters/nornyx-agentic-adapters # the supported adapter package
pip install "crewai==1.15.4"                     # the single supported CrewAI version
```

**On package availability, stated plainly:** `nornyx` 1.8.0 *is* published on
PyPI. **`nornyx-agentic-adapters` is not published** — the `pip install
nornyx-agentic-adapters` line in that package's own README does not currently
resolve. It must be installed from this repository, which is what the command
above does. The benchmark records this in `environment.json` as
`adapters_package_published_on_pypi: false`.

The CrewAI pin is enforced at import time, not merely documented: any version
other than `1.15.4` raises `AdapterConfigurationError`.

Verify the toolchain before running anything:

```bash
python -c "
import importlib.metadata as m, nornyx, nornyx.agentic as a, nornyx_agentic_adapters as ad
print('nornyx  ', m.version('nornyx'), '| SPI', a.SPI_VERSION)
print('adapters', m.version('nornyx-agentic-adapters'))
print('crewai  ', m.version('crewai'))
from nornyx_agentic_adapters.crewai_adapter import METADATA
print('adapter imported OK:', METADATA.adapter_name)
"
```

## The one command

```bash
python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out
```

Runs in roughly 40–90 seconds on a typical laptop — most of it CrewAI import plus
the one-time contract load. Treat any timing figure here or in the reports as a
local observation, not a benchmark result. **It exits non-zero if any clause of
the benchmark contract fails, or if the complete evidence stream does not
validate** — a zero exit is itself a machine-checked claim, not a courtesy.

```bash
echo $?      # 0 = every contract check passed AND the full stream validated
```

The verdict is `GO` or `NO_GO`. There is no conditional verdict: a result that
normalizes a known defect reads as a pass to everyone who does not also read the
footnote.

## What you should get

```
benchmark_out/
├── benchmark.json              canonical machine-readable results
├── benchmark.md                full technical report
├── dashboard.html              self-contained static dashboard (open in a browser)
├── environment.json            exact versions actually installed
├── plain_results.json          Variant A per-scenario results + ledger timeline
├── governed_results.json       Variant B per-scenario results + ledger timeline
├── nornyx_runtime_events.json  the governed evidence stream
├── nornyx_evidence_report.json Nornyx's validation of that stream
├── validation_manifest.json    sha256 of every input, source file, and output
└── drift_probe/                the mutated contract copy used by scenario S12
```

## How to check the result yourself

Do not take the report's word for anything. Each check below reads the raw
artifacts.

### 1. Confirm prevented callables stayed at exactly zero

This is the load-bearing claim. A denial is only real if the business callable
never ran:

```bash
python - <<'PY'
import json
rows = json.load(open("benchmark_out/benchmark.json"))["scenarios"]
bad = []
for r in rows:
    g = r["governed"]
    if g["outcome"] in ("denied", "binding_refused", "load_refused"):
        if g["business_side_effects_completed"] or g["business_callable_attempts"]:
            bad.append(r["id"])
        print(f"{r['id']:<4} {g['diagnostic_code']:<28} "
              f"attempts={g['business_callable_attempts']} completed={g['business_side_effects_completed']}")
print("\nVIOLATIONS:", bad or "none")
PY
```

Every denied row must show `attempts=0 completed=0`.

### 2. Compare the two variants on the same operation

```bash
python - <<'PY'
import json
m = json.load(open("benchmark_out/benchmark.json"))["metrics"]
for row in m["allowed_path"]["comparisons"]:
    print(row["scenario"], "equal:", row["business_output_equal"])
    print("   baseline:", row["baseline_business_output"])
    print("   governed:", row["governed_business_output"])
PY
```

Identical output on the allowed path is the evidence that governance did not
change what the application computes.

### 3. Read the raw side-effect ledger

`plain_results.json` and `governed_results.json` each carry a `ledger` timeline
on one monotonic clock. Every `attempt`/`success` entry is a business callable
actually running, and every `decision` entry is a governance decision:

```bash
python -c "
import json
t = json.load(open('benchmark_out/governed_results.json'))['ledger']
for e in t[:14]: print(e['seq'], e['scenario'], e['kind'], e['label'])
"
```

Decisions must appear before the attempts they authorize.

### 4. Verify evidence and digests

```bash
python - <<'PY'
import json
stream = json.load(open("benchmark_out/nornyx_runtime_events.json"))
report = json.load(open("benchmark_out/nornyx_evidence_report.json"))
digests = {(e["contract_digest"], e["network_lock_digest"]) for e in stream["events"]}
print("events:", len(stream["events"]))
print("distinct digest pairs:", digests)          # must be exactly one
print("validation status:", report["status"])
for d in report.get("diagnostics", []):
    print("  ", d["code"], d["path"])
PY
```

Then re-verify the digests independently against the contract itself:

```bash
B=examples/crewai_governance_benchmark/contract
nornyx agentic-network lock-check "$B/remediation_network.nyx" \
  --lock "$B/nornyx.agentic_network.lock" \
  --artifacts "$B/control_artifacts" \
  --as-of 2026-07-17T00:00:00Z
```

**Expect `status: pass` and an empty `diagnostics` list** — for the *complete*
event stream, with nothing filtered out. The benchmark has no allow-list of
tolerated diagnostic codes and never re-validates a reduced stream: any
diagnostic at all fails the `no_evidence_diagnostics` contract check, produces a
`NO_GO` verdict, and exits non-zero.

Earlier revisions of this benchmark did report `fail` here, because two defects
in the audited packages (F1 and F2) made a truthful stream unvalidatable. Both
are fixed and regression-tested; see `FINDINGS.md` for the reproductions.

### 5. Confirm nothing was tampered with

```bash
python - <<'PY'
import hashlib, json, pathlib
man = json.load(open("benchmark_out/validation_manifest.json"))
out = pathlib.Path("benchmark_out")
for entry in man["outputs"] + man["benchmark_sources"] + man["inputs"]:
    for base in (out, pathlib.Path("examples/crewai_governance_benchmark"),
                 pathlib.Path("examples/crewai_governance_benchmark/contract")):
        p = base / entry["path"]
        if p.is_file():
            got = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
            assert got == entry["digest"], f"MISMATCH {entry['path']}"
            break
print("all manifest digests match")
PY
```

### 5b. Compare your run against the committed snapshot

Only two digests are meant to match across machines, and the manifest says which
outputs they cover:

```bash
python - <<'PY'
import json
mine = json.load(open("benchmark_out/validation_manifest.json"))
theirs = json.load(open("examples/crewai_governance_benchmark/results/validation_manifest.json"))
for key in ("candidate_digest", "deterministic_outputs_digest"):
    print(f"{key}: {'MATCH' if mine[key] == theirs[key] else 'DIFFERENT'}")
    print("   yours: ", mine[key])
    print("   theirs:", theirs[key])
PY
```

`candidate_digest` folds every governance input and benchmark source file into
one value: if it differs, you are not running the same candidate, and no other
comparison means much. `deterministic_outputs_digest` covers only the
reproducible outputs — the evidence stream, its validation report, and the two
per-scenario result files.

Both folds hash normalized content and POSIX paths, so a Windows checkout and a
Linux checkout of the same commit produce the same values. (The per-file
`digest` field is byte-exact and is for the tamper check in §5 above; it is
line-ending sensitive and is not the value to compare across machines.)

`benchmark.json`, `benchmark.md`, `dashboard.html`, and `environment.json` embed
installed versions, the host platform, and local wall-clock timings, so their
bytes will differ from the committed copies. They are marked
`"deterministic": false` in the manifest for exactly that reason — a manifest
that claimed they were reproducible would be claiming something false.

### 6. Confirm the benchmark cannot reach the network

The run is wrapped in an offline guard. Prove the guard actually bites:

```bash
python -c "
import sys; sys.path.insert(0,'examples')
from crewai_governance_benchmark import config
import socket
with config.no_external_io():
    try: socket.getaddrinfo('example.com', 443)
    except AssertionError as e: print('blocked as expected:', e)
"
```

## Rerunning individual scenarios

```bash
python examples/crewai_governance_benchmark/benchmark.py --out /tmp/one --scenario S03
python examples/crewai_governance_benchmark/benchmark.py --out /tmp/two --scenario S06 --scenario S16
```

This prints the baseline and governed record for those scenarios only — expected
outcome, actual outcome, attempts, completions, diagnostic, and output — and
then **asserts the same per-scenario contract clauses the full run does**
(expected side effects, expected diagnostic code, exactly-once on ALLOW). It
exits non-zero if any selected scenario differs from its expected result, so a
focused spot-check is a real check rather than a printout.

## Running the tests

```bash
python -m pytest tests/test_crewai_governance_benchmark.py -q -rs
```

46 tests, **zero skips**. They execute the benchmark once and assert against its
real artifacts, including that the full evidence stream validates with no
diagnostics, that the benchmark uses no private Nornyx API, that no artifact
contains an absolute local path, that the dashboard is self-contained, that no
report contains an absolute claim, and that the manifest digests match the files
on disk.

The `crewai-governance-benchmark` CI job runs the benchmark and this suite
against the exact PR head with `crewai==1.15.4` and the candidate adapter
installed, and fails if any test skips, if none run, or if the benchmark exits
non-zero.

## Things worth knowing before you judge the result

- **The evaluation instant is pinned** to `2026-07-17T00:00:00Z`. That is not a
  convenience: `nornyx.agentic` reads no wall clock by design, so a reproducible
  benchmark must fix `decision_at`. It also means `nornyx check` on the contract
  requires `--as-of 2026-07-17T00:00:00Z`; without it the contract's approval and
  evidence records read as expired.
- **CrewAI retries a failing tool three times** internally, with no public knob.
  Scenario S14 measures this and shows each retry receives its own independent
  authorization rather than reusing the first.
- **S15 is supposed to succeed under governance.** It is a negative control: an
  unwrapped tool that proves enforcement is cooperative, not total.
- **S18 is supposed to be refused by the application, not by Nornyx.** It exists
  so the benchmark cannot take credit for a control the baseline already had.
- **Enforcement is cooperative.** The supported CrewAI adapter wraps synchronous
  tool invocation only. Asynchronous tool invocation, agent invocation, task
  invocation, CrewAI's own coworker delegation, and handoff are declared
  `unsupported` in the adapter's coverage inventory — not silently covered.
- **Identity resolution is binding, not authentication.** It maps a declared role
  string to a declared identity; it never establishes that the caller is who it
  claims to be.
- **Validating evidence proves structure and binding, not truth.** It shows the
  records are well formed and bound to the exact contract and lock revision. It
  does not prove the emitter told the truth or that any external side effect
  really happened.
- **`results/` is a snapshot, not a live claim.** Rerun the benchmark; compare
  `candidate_digest` first.

## Reporting an unexpected result

Please include:

1. `benchmark_out/environment.json` (exact installed versions)
2. `benchmark_out/validation_manifest.json`
3. the full terminal output including the exit code
4. which specific contract check or scenario differed, and what you expected

Open an issue at <https://github.com/mazinmarji/nornyx/issues>. If the difference
is in a contract check, the failing check name and its `detail` string are printed
directly and are the most useful thing to paste.
