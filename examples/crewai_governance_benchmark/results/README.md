# Recorded benchmark results

A **snapshot of one real run**, committed so a reviewer can read the outcome
without installing CrewAI or executing anything. It is a record, not a live
claim: it is not continuously verified and can go stale the moment the candidate
changes.

**Start here → [`dashboard.html`](dashboard.html)** (download and open in a
browser; GitHub does not render committed HTML inline). It is fully
self-contained — no CDN, no script, no network reference of any kind — and
adapts to your light/dark theme.

| File | What it is |
|---|---|
| [`dashboard.html`](dashboard.html) | visual summary: headline tiles, plain-vs-governed bars, scenario heat map, the two claim panels, adapter coverage |
| [`benchmark.md`](benchmark.md) | full technical report with mermaid diagrams and per-scenario detail |
| [`benchmark.json`](benchmark.json) | canonical machine-readable results, metrics, and all contract checks |
| [`plain_results.json`](plain_results.json) / [`governed_results.json`](governed_results.json) | per-scenario results plus the complete side-effect ledger timeline |
| [`nornyx_runtime_events.json`](nornyx_runtime_events.json) | the governed evidence stream |
| [`nornyx_evidence_report.json`](nornyx_evidence_report.json) | Nornyx's own validation of that stream |
| [`validation_manifest.json`](validation_manifest.json) | sha256 of every governance input, benchmark source file, and output, plus the two cross-machine digests |
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
exact contract and lock digest · **full evidence stream validates with 0
diagnostics** · benchmark contract 58/58 checks passed · verdict **GO**.

## Reading it honestly

- **S15 executing under governance is the expected result.** It is the bypass
  negative control: enforcement is cooperative, and a tool that never enters the
  adapter is never evaluated.
- **S18 being refused in both arms is the expected result.** That refusal is the
  application's own business rule, not Nornyx's, so it is credited to neither.
- **Evidence validation proves structure and binding, not truth.** A validating
  stream shows the records are well formed and bound to the exact contract and
  lock revision. It does not prove any external side effect really happened.
- **Building this benchmark found three real defects** (F1, F2, F3 in
  [`../FINDINGS.md`](../FINDINGS.md)). All three are fixed and regression-tested;
  none of them ever changed an enforcement outcome, only whether the evidence
  could be validated.

## Verifying this snapshot

Two digests in `validation_manifest.json` are reproducible on any machine and are
the ones worth comparing against your own run:

```bash
python - <<'PY'
import json
man = json.load(open("examples/crewai_governance_benchmark/results/validation_manifest.json"))
print("candidate_digest            ", man["candidate_digest"])
print("deterministic_outputs_digest", man["deterministic_outputs_digest"])
PY
```

- `candidate_digest` folds every governance input and benchmark source file into
  one value, so it identifies the exact candidate this result came from. If it
  differs from yours, you are not running the same code and contract.
- `deterministic_outputs_digest` folds only the reproducible outputs: the evidence
  stream, its validation report, and the two per-scenario result files.

Both fold each file's `content_digest` (line endings normalized) and POSIX paths,
so a Windows and a Linux checkout of the same commit agree. The per-file `digest`
is byte-exact and is for the tamper check below, not for cross-machine comparison.

To check that the committed bytes here have not been edited since the run:

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

## What will differ on your machine

`benchmark.json`, `benchmark.md`, `dashboard.html`, and `environment.json` embed
installed versions, the host platform, and local wall-clock timings, so their
bytes legitimately differ between machines. They are marked
`"deterministic": false` in the manifest for exactly that reason.

Every timing figure in these files is a **local observation** from the machine
that produced the run — not a production latency measurement and not a throughput
claim. No artifact contains an absolute local path.

Regenerate any time with:

```bash
python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out
```
