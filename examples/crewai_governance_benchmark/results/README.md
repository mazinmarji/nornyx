# Recorded benchmark results

A **snapshot of one real run**, committed so a reviewer can read the outcome
without installing CrewAI or executing anything.

**Start here → [`dashboard.html`](dashboard.html)** (download and open in a
browser; GitHub does not render committed HTML inline). It is fully
self-contained — no CDN, no script, no network reference of any kind — and
adapts to your light/dark theme.

| File | What it is |
|---|---|
| [`dashboard.html`](dashboard.html) | visual summary: headline tiles, plain-vs-governed bars, scenario heat map, the two claim panels, adapter coverage |
| [`benchmark.md`](benchmark.md) | full technical report with mermaid diagrams and per-scenario detail |
| [`benchmark.json`](benchmark.json) | canonical machine-readable results, metrics, and all 57 contract checks |
| [`plain_results.json`](plain_results.json) / [`governed_results.json`](governed_results.json) | per-scenario results plus the complete side-effect ledger timeline |
| [`nornyx_runtime_events.json`](nornyx_runtime_events.json) | the governed evidence stream (51 events) |
| [`nornyx_evidence_report.json`](nornyx_evidence_report.json) | Nornyx's own validation of that stream |
| [`validation_manifest.json`](validation_manifest.json) | sha256 of every governance input, benchmark source file, and output |
| [`environment.json`](environment.json) | exact installed versions for this run |

## What this run recorded

| | Plain CrewAI | Governed by Nornyx |
|---|---|---|
| Business side effects executed | 16 | 5 |
| Prohibited actions executed | 11 | **0** |
| Governance decisions recorded | 0 | 27 |
| Evidence events emitted | 0 | 51 |

19 scenarios · 4/4 valid actions allowed with identical output · 0 false denials ·
0 false allows · 11/11 prohibited callables prevented · 51/51 events bound to the
exact contract and lock digest · benchmark contract 57/57 checks passed ·
verdict **CONDITIONAL_GO**.

## Reading it honestly

- **Evidence validation is `fail`, on purpose and in the open.** Two mandatory
  scenarios each reproduce a real defect in the audited packages — see
  [`../FINDINGS.md`](../FINDINGS.md). Nothing upstream was patched to make this
  pass.
- **S15 executing under governance is the expected result.** It is the bypass
  negative control.
- **S18 being refused in both arms is the expected result.** That refusal is the
  application's own business rule, not Nornyx's.

## Verifying this snapshot

The digests in `validation_manifest.json` are of these exact bytes, so the files
here can be checked without rerunning anything:

```bash
cd examples/crewai_governance_benchmark/results
python - <<'PY'
import hashlib, json, pathlib
man = json.load(open("validation_manifest.json"))
for entry in man["outputs"]:
    p = pathlib.Path(entry["path"])
    if not p.is_file():
        print("not in this snapshot:", entry["path"]); continue
    got = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
    print(("OK   " if got == entry["digest"] else "BAD  ") + entry["path"])
PY
```

## Caveats about a snapshot

These files are a record, not a source of truth. They can go stale if the
benchmark changes, and `nornyx drift`-style checking is **not** applied to them.
Regenerate any time with:

```bash
python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out
```

`environment.json` and the manifest contain absolute paths from the machine that
produced the run (a local WSL2 checkout), and the timing figures are that
machine's local microbenchmark. Neither travels; both will differ on yours.
