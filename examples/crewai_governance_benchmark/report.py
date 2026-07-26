"""Rendering: terminal summary, benchmark.md, and a self-contained dashboard.

Every figure rendered here comes from the metrics computed in ``metrics.py``,
which in turn come from actual execution. No renderer invents, rounds up, or
restates a number that was not measured, and no claim appears here that the run
did not establish.
"""

from __future__ import annotations

import html
import json
from typing import Any

from crewai_governance_benchmark.scenarios import APPLICATION, BYPASS, SCENARIOS

# --------------------------------------------------------------------- claims
# The two panels are deliberately paired: nothing may be added to "changed"
# without the matching boundary being stated in "not solved".
WHAT_CHANGED = [
    (
        "External contract",
        "Authority lives in a versioned .nyx contract outside the application, not in "
        "prompt text, tool wiring, or agent role descriptions.",
    ),
    (
        "Explicit identity-to-capability authority",
        "Each CrewAI agent role resolves to a declared identity whose capabilities are "
        "enumerated. Having a tool attached grants nothing.",
    ),
    (
        "Revision binding",
        "Every decision and every emitted event binds the exact contract digest, network "
        "lock digest, and subject revision. A drifted contract refuses to load.",
    ),
    (
        "Human-approval constraints",
        "External crossings require a human approval record that is scoped to the action, "
        "unexpired at the decision instant, and bound to the governed revision. Models, "
        "tools, and execution surfaces can never approve.",
    ),
    (
        "Fail-closed execution boundary",
        "enforce() evaluates, records, and only then executes. A non-ALLOW decision raises "
        "before the business callable is reached — proved by a side-effect ledger that "
        "stays at zero, not by reading an exception message.",
    ),
    (
        "Deterministic evidence",
        "Each governed invocation emits typed runtime events bound to the contract and "
        "lock, replayable against the same artifacts by an independent checker.",
    ),
]

WHAT_WAS_NOT_SOLVED = [
    (
        "Bypass remains possible",
        "Enforcement is cooperative. A tool that never enters the adapter is never "
        "evaluated — demonstrated deliberately by the S15 negative control, which "
        "executes under governance exactly as it does in the baseline.",
    ),
    (
        "One wrapped surface only",
        "The supported CrewAI adapter wraps synchronous tool invocation. Asynchronous "
        "tool invocation, agent invocation, task invocation, CrewAI's own coworker "
        "delegation, and handoff are declared unsupported — not silently covered.",
    ),
    (
        "No runtime truth",
        "Validating evidence proves the records are well formed and bound to the exact "
        "contract and lock revision. It does not prove the emitter told the truth, that "
        "the action really happened, or that the reported payload is what ran.",
    ),
    (
        "No agent authentication",
        "Identity resolution maps a declared role string to a declared identity. It never "
        "establishes that the caller is who it claims to be.",
    ),
    (
        "No model or orchestration control",
        "Nornyx does not run the crew, choose tools, improve the model's answers, or "
        "observe anything CrewAI does outside a wrapped tool.",
    ),
    (
        "Does not replace application security",
        "The application's own validation still did the work in the S18 fairness control. "
        "Nornyx governs authority and evidence, not business correctness.",
    ),
]

ARCHITECTURE_UNGOVERNED = """```mermaid
flowchart LR
    LLM["DeterministicLLM<br/>(offline, scripted)"] --> EX["CrewAI ReAct executor<br/>Crew.kickoff()"]
    EX --> T["PlainTool._run"]
    T --> W["shared business callable"]
    W --> SE[("side-effect ledger")]
    W --> OUT["business output"]
```"""

ARCHITECTURE_GOVERNED = """```mermaid
flowchart LR
    LLM["DeterministicLLM<br/>(offline, scripted)"] --> EX["CrewAI ReAct executor<br/>Crew.kickoff()"]
    EX --> GT["GovernedInvocationTool._run<br/>(mints mission, catches denial)"]
    GT --> AD["adapter _GovernedTool._run"]
    AD --> EN["enforce()"]
    EN -->|1 evaluate| AZ["Authorizer.evaluate"]
    EN -->|2 record| ER["EvidenceRecorder"]
    EN -->|3 execute only on ALLOW| W["shared business callable"]
    AZ -.->|DENY / APPROVAL_REQUIRED| STOP["AdapterDenied<br/>callable never reached"]
    W --> SE[("side-effect ledger")]
    W --> OBS["post-action observation"]
    OBS --> ER
    ER --> EV["runtime events"]
```"""

ARCHITECTURE_BOUNDARIES = """```mermaid
flowchart TB
    subgraph design["Design time — Nornyx"]
        NYX["remediation_network.nyx"]
        GEN["generated control artifacts"]
        LOCK["nornyx.agentic_network.lock"]
        NYX --> GEN --> LOCK
    end
    subgraph spi["Load + evaluate — nornyx.agentic (SPI 1.0)"]
        AZ["Authorizer<br/>immutable, lock-verified"]
        REC["EvidenceRecorder"]
    end
    subgraph adapter["Cooperative boundary — nornyx-agentic-adapters"]
        ENF["enforce(): evaluate -> record -> execute"]
        GTOOL["make_governed_tool (sync _run only)"]
    end
    subgraph app["Application — CrewAI"]
        CREW["Agent / Task / Crew"]
        BIZ["business callables"]
        BYPASS["unwrapped tool (S15)"]
    end
    NYX --> AZ
    LOCK --> AZ
    AZ --> ENF
    REC --> ENF
    ENF --> GTOOL --> BIZ
    CREW --> GTOOL
    CREW --> BYPASS
    BYPASS -.->|never evaluated| BIZ
    REC --> EVID["nornyx.agentic_runtime_events.v1"]
```"""


def _cell(scenario, governed: int, prevented: bool) -> str:
    """The heat-map state for one row.

    Deliberately distinguishes "executed because it was allowed" from "executed
    although it should not have been": colouring every execution the same way
    would make a correct ALLOW look like a failure.
    """
    if prevented:
        return "prevented"
    if scenario.stage == BYPASS:
        return "bypassed"
    if scenario.stage == APPLICATION:
        return "refused by app"
    if governed > 0:
        return "allowed"
    return "not run"


# state -> css class used by the dashboard legend and cells
_STATE_CLASS = {
    "prevented": "block",   # governance stopped a prohibited action  (green)
    "allowed": "n",         # a valid action ran as intended          (accent)
    "bypassed": "exec",     # ran outside the governed boundary       (red)
    "refused by app": "mute",
    "not run": "mute",
}


def heat_rows(plain: dict, governed: dict, metrics: dict) -> list[dict[str, Any]]:
    """One heat-map row per scenario, computed from measured results."""
    prevented = set(
        metrics["prevention"]["runtime_stage_prevention_scenarios"]
        + metrics["prevention"]["binding_stage_prevention_scenarios"]
    )
    rows = []
    for s in SCENARIOS:
        p, g = plain[s.id], governed[s.id]
        rows.append(
            {
                "scenario": s.id,
                "title": s.title,
                "stage": s.stage,
                "category": s.category,
                "risk": s.risk,
                "baseline_executed": int(p["business_side_effects_completed"]),
                "governed_decision": g.get("diagnostic_code") or "—",
                "governed_executed": int(g["business_side_effects_completed"]),
                "governed_attempts": int(g["business_callable_attempts"]),
                "state": _cell(s, int(g["business_side_effects_completed"]), s.id in prevented),
                "counted_as_prevention": s.id in prevented,
            }
        )
    return rows


# ------------------------------------------------------------------- terminal
def terminal_summary(metrics: dict, rows: list[dict], env: dict) -> str:
    a = metrics["allowed_path"]
    p = metrics["prevention"]
    e = metrics["evidence"]
    b = metrics["boundary"]
    se = metrics["side_effects"]
    x = metrics["execution_integrity"]

    lines = [
        "",
        "=" * 78,
        "  NORNYX GOVERNANCE A/B BENCHMARK — CrewAI",
        "=" * 78,
        f"  nornyx {env['nornyx_version']} (SPI {env['nornyx_agentic_spi_version']})"
        f" · adapters {env['adapters_version']} · crewai {env['crewai_version']}"
        f" · python {env['python_version']}",
        f"  decision instant pinned at {env['as_of']}",
        "",
        "  PLAIN CrewAI                          GOVERNED by Nornyx",
        "  " + "-" * 74,
        f"  business side effects : {se['baseline_total']:<12}"
        f"  business side effects : {se['governed_total']}",
        f"  prohibited executed   : {p['prohibited_callables_executed_in_baseline']:<12}"
        f"  prohibited prevented  : {p['prohibited_callables_prevented_by_nornyx']}",
        f"  governance decisions  : {'0 (none)':<12}"
        f"  governance decisions  : {x['total_decisions_recorded']} recorded pre-execution",
        f"  evidence events       : {'0 (none)':<12}"
        f"  evidence events       : {e['events_emitted']}",
        "",
        "  RESULTS",
        "  " + "-" * 74,
        f"  scenarios                          {metrics['totals']['scenarios']}",
        f"  valid actions allowed              {a['valid_actions_allowed']}/{a['valid_actions_total']}",
        f"  allowed-path output equivalence    {'yes' if a['business_output_equivalence'] else 'NO'}",
        f"  false denials of valid actions     {a['false_denials_of_valid_actions']}",
        f"  false allows on governed path      {p['false_allows_on_governed_path']}",
        f"  runtime-stage preventions          {p['runtime_stage_preventions']}",
        f"  binding-stage preventions          {p['binding_stage_preventions']}",
        "  prevention by category             "
        + (", ".join(f"{k}={v}" for k, v in p["runtime_prevention_by_category"].items()) or "—"),
        f"  bypass control executed in both    {'yes' if b['bypass_visible_and_uncounted'] else 'NO'}",
        f"  app rule refused in both (S18)     {'yes' if b['application_rule_refused_in_both'] else 'NO'}",
        "",
        "  EVIDENCE",
        "  " + "-" * 74,
        f"  events bound to contract digest    {e['events_bound_to_contract_digest']}/{e['events_emitted']}",
        f"  events bound to lock digest        {e['events_bound_to_lock_digest']}/{e['events_emitted']}",
        f"  post-success observations          {x['post_success_observations_recorded']}"
        f" (governed-surface completions: {x['completed_side_effects_on_governed_surfaces']})",
        f"  full-stream validation             {e['validation_status'].upper()}",
    ]
    for d in e["diagnostics"]:
        lines.append(f"    ! {d['code']} at {d['path']}")
    lines += [
        "",
        "  SCENARIO HEAT MAP  (baseline -> governed)",
        "  " + "-" * 74,
    ]
    for r in rows:
        mark = {"prevented": "BLOCKED ", "allowed": "allowed ", "bypassed": "BYPASS  ",
                "refused by app": "app-rule", "not run": "not run "}[r["state"]]
        lines.append(
            f"  {r['scenario']:<4} {r['title'][:38]:<38} "
            f"{r['baseline_executed']} -> {r['governed_executed']}  {mark} {r['governed_decision']}"
        )
    lines += ["", "=" * 78, ""]
    return "\n".join(lines)


# ------------------------------------------------------------------- markdown
def render_markdown(
    metrics: dict,
    rows: list[dict],
    env: dict,
    adapter: dict,
    verdict: dict,
    candidate_digest: str = "",
) -> str:
    a, p, e, b = (
        metrics["allowed_path"],
        metrics["prevention"],
        metrics["evidence"],
        metrics["boundary"],
    )
    x = metrics["execution_integrity"]
    out: list[str] = []
    w = out.append

    w("# Nornyx Governance A/B Benchmark — CrewAI\n")
    w(
        "One customer-support and financial-remediation workflow, run twice: once as an "
        "ordinary CrewAI application, and once with the same agents, tasks, model, inputs, "
        "business rules, and business callables governed by Nornyx through the supported "
        "CrewAI adapter. The intended variable is the presence of governance.\n"
    )
    w(
        "> This is a governance-effectiveness benchmark. It is not an LLM-quality\n"
        "> benchmark and not a production-performance benchmark.\n"
    )

    w("## Verdict\n")
    w(f"**{verdict['verdict']}** — {verdict['summary']}\n")
    if verdict["blocking"]:
        w("Blocking findings:\n")
        for item in verdict["blocking"]:
            w(f"- {item}")
        w("")

    w("## Environment\n")
    w("| Component | Value |")
    w("|---|---|")
    for key in (
        "python_version",
        "nornyx_version",
        "nornyx_agentic_spi_version",
        "adapters_version",
        "crewai_version",
        "as_of",
    ):
        w(f"| `{key}` | `{env[key]}` |")
    w(f"| adapters published on PyPI | **{env['adapters_package_published_on_pypi']}** |")
    w(f"| adapters install source | {env['adapters_install_source']} |")
    if candidate_digest:
        w(f"| candidate digest | `{candidate_digest}` |")
    w("")
    w(
        "`nornyx` is published on PyPI. **`nornyx-agentic-adapters` is not**: it is installed "
        "from this repository. Nothing in this benchmark implies otherwise.\n"
    )
    w(
        "The candidate digest folds every governance input and benchmark source file into one "
        "value. It is identical on every machine, so it — not the timing figures or the "
        "platform string — is what identifies the exact candidate a result came from.\n"
    )

    w("## Headline results\n")
    w("| Metric | Plain CrewAI | Governed by Nornyx |")
    w("|---|---|---|")
    w(
        f"| Business side effects executed | {metrics['side_effects']['baseline_total']} "
        f"| {metrics['side_effects']['governed_total']} |"
    )
    w(
        f"| Prohibited callables executed | "
        f"{p['prohibited_callables_executed_in_baseline']} | "
        f"{p['prohibited_callables_executed_in_baseline'] - p['prohibited_callables_prevented_by_nornyx']} |"
    )
    w(f"| Governance decisions recorded | 0 | {x['total_decisions_recorded']} |")
    w(f"| Evidence events emitted | 0 | {e['events_emitted']} |")
    w("")
    w("| Measurement | Value |")
    w("|---|---|")
    w(f"| Scenarios | {metrics['totals']['scenarios']} |")
    w(f"| Valid actions allowed | {a['valid_actions_allowed']} / {a['valid_actions_total']} |")
    w(f"| Allowed-path business-output equivalence | {a['business_output_equivalence']} |")
    w(f"| False denials of valid actions | {a['false_denials_of_valid_actions']} |")
    w(f"| False allows on the governed path | {p['false_allows_on_governed_path']} |")
    w(f"| Runtime-stage preventions | {p['runtime_stage_preventions']} |")
    w(f"| Binding-stage preventions | {p['binding_stage_preventions']} |")
    w(
        "| Runtime prevention by category | "
        + (", ".join(f"`{k}`={v}" for k, v in p["runtime_prevention_by_category"].items()) or "—")
        + " |"
    )
    w(f"| Scenarios with decision recorded before execution | {x['scenarios_with_decision_before_execution']} / {x['scenarios_with_ordering_checkable']} |")
    w(f"| Post-success observations vs governed-surface completions | {x['post_success_observations_recorded']} vs {x['completed_side_effects_on_governed_surfaces']} |")
    w(f"| Events bound to contract digest | {e['events_bound_to_contract_digest']} / {e['events_emitted']} |")
    w(f"| Events bound to lock digest | {e['events_bound_to_lock_digest']} / {e['events_emitted']} |")
    w(f"| Evidence validation (full stream) | **{e['validation_status']}** |")
    w(f"| Evidence diagnostics | {len(e['diagnostics'])} |")
    w(f"| Bypass control executed in both variants | {b['bypass_executed_in_baseline'] and b['bypass_executed_under_governance']} |")
    w("")

    w("## Architecture\n")
    w("### Ungoverned path (Variant A)\n")
    w(ARCHITECTURE_UNGOVERNED + "\n")
    w("### Governed path (Variant B) — evaluate → record → execute\n")
    w(ARCHITECTURE_GOVERNED + "\n")
    w("### Boundaries\n")
    w(ARCHITECTURE_BOUNDARIES + "\n")

    w("## Scenario heat map\n")
    w("`baseline` and `governed` are counts of the business callable actually completing.\n")
    w("| # | Scenario | Stage | Category | Risk | Baseline | Governed | Result | Diagnostic |")
    w("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        state = "**prevented**" if r["state"] == "prevented" else r["state"]
        w(
            f"| {r['scenario']} | {r['title']} | `{r['stage']}` | `{r['category']}` | {r['risk']} "
            f"| {r['baseline_executed']} | {r['governed_executed']} | {state} | `{r['governed_decision']}` |"
        )
    w("")

    w("## Scenario detail\n")
    for s in SCENARIOS:
        r = next(row for row in rows if row["scenario"] == s.id)
        w(f"### {s.id} — {s.title}\n")
        w(f"- **Stage / category / risk**: `{s.stage}` / `{s.category}` / {s.risk}")
        w(f"- **CrewAI role**: `{s.role}` · **capability**: `{s.capability_ref or '—'}`")
        w(f"- **Baseline**: {r['baseline_executed']} completed side effect(s)")
        w(
            f"- **Governed**: {r['governed_executed']} completed side effect(s), "
            f"{r['governed_attempts']} callable entr(y/ies), diagnostic `{r['governed_decision']}`"
        )
        w(f"- **What it shows**: {s.interpretation}")
        w(f"- **Caveat**: {s.caveat}\n")

    w("## What Nornyx changed\n")
    for title, body in WHAT_CHANGED:
        w(f"- **{title}.** {body}")
    w("")
    w("## What Nornyx did not solve\n")
    for title, body in WHAT_WAS_NOT_SOLVED:
        w(f"- **{title}.** {body}")
    w("")

    w("## Adapter coverage — declared, not assumed\n")
    w("| Surface | Framework | Status | Reason |")
    w("|---|---|---|---|")
    for s in adapter["surfaces"]:
        w(f"| `{s['surface']}` | {s['framework']} | **{s['status']}** | {s['reason']} |")
    w("")
    w(
        "This table is the adapter's own `COVERAGE_INVENTORY`, printed verbatim. Anything "
        "not marked `wrapped` is outside the enforcement boundary of this benchmark.\n"
    )

    if e["diagnostics"]:
        w("## Evidence diagnostics — the full stream did not validate\n")
        w(
            "The complete event stream does not validate. Every diagnostic the validator "
            "reported is listed here in full; nothing is filtered, excluded, or re-validated "
            "against a reduced stream, and the verdict is `NO_GO`:\n"
        )
        for d in e["diagnostics"]:
            w(f"- `{d['code']}` at `{d['path']}` — {d['message']}")
        w("")
        w("See `FINDINGS.md` for reproductions and root causes.\n")

    w("## Timing (local microbenchmark only)\n")
    t = metrics["timing_local_microbenchmark_only"]
    w("| Measurement | Value | Unit |")
    w("|---|---|---|")
    for key, value in sorted(t.items()):
        if key == "disclaimer":
            continue
        unit = "ms" if key.endswith("milliseconds") else "s"
        w(f"| `{key}` | {value:.4f} | {unit} |")
    w("")
    w(
        "The two variant totals are not a like-for-like per-call comparison: the governed "
        "total includes loading and lock-verifying the contract once, running the drift "
        "probe, and constructing an evidence stream. `authorizer_load_seconds` is that "
        "one-time control-plane cost and `mean_evaluate_milliseconds` is the per-decision "
        "cost, which is what a per-call overhead question is actually asking about.\n"
    )
    w(f"> {t['disclaimer']}\n")

    w("## Reproducing\n")
    w("```bash")
    w("python examples/crewai_governance_benchmark/benchmark.py --out benchmark_out")
    w("```")
    w(
        "\nThe command exits non-zero unless every clause of the benchmark contract in "
        "`scenarios.py` holds **and** the full evidence stream validates. See "
        "`REVIEWER_QUICKSTART.md`.\n"
    )
    w(
        "Any committed copy of this report is a **snapshot of one run**, not a continuously "
        "verified claim. It can go stale the moment the candidate changes. Compare the "
        "candidate digest above, and rerun the benchmark rather than trusting the file.\n"
    )
    return "\n".join(out)


# ------------------------------------------------------------------ dashboard
_CSS = """
:root{--bg:#f7f8fa;--panel:#fff;--ink:#14171f;--muted:#5b6472;--line:#e2e6ec;
--ok:#1a7f4b;--okbg:#e6f5ec;--bad:#b3261e;--badbg:#fdeceb;--warn:#8a5a00;--warnbg:#fdf3e0;
--accent:#2b4bd8;--accentbg:#eaeeff}
@media (prefers-color-scheme:dark){:root{--bg:#0e1116;--panel:#161a22;--ink:#e6e9ef;
--muted:#9aa4b2;--line:#252b36;--ok:#5fd39b;--okbg:#12291f;--bad:#ff8a80;--badbg:#2a1615;
--warn:#f0c36d;--warnbg:#2a2114;--accent:#8ea4ff;--accentbg:#171d33}}
:root[data-theme="dark"]{--bg:#0e1116;--panel:#161a22;--ink:#e6e9ef;--muted:#9aa4b2;
--line:#252b36;--ok:#5fd39b;--okbg:#12291f;--bad:#ff8a80;--badbg:#2a1615;--warn:#f0c36d;
--warnbg:#2a2114;--accent:#8ea4ff;--accentbg:#171d33}
:root[data-theme="light"]{--bg:#f7f8fa;--panel:#fff;--ink:#14171f;--muted:#5b6472;
--line:#e2e6ec;--ok:#1a7f4b;--okbg:#e6f5ec;--bad:#b3261e;--badbg:#fdeceb;--warn:#8a5a00;
--warnbg:#fdf3e0;--accent:#2b4bd8;--accentbg:#eaeeff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 18px 64px}
header h1{font-size:clamp(22px,3.4vw,32px);margin:0 0 6px;letter-spacing:-.02em}
header p{margin:0;color:var(--muted);max-width:76ch}
.meta{margin:14px 0 0;display:flex;flex-wrap:wrap;gap:6px}
.chip{font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--panel);
border:1px solid var(--line);border-radius:999px;padding:6px 10px;color:var(--muted)}
section{margin-top:34px}
h2{font-size:17px;margin:0 0 12px;letter-spacing:-.01em}
h2 .sub{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.card .v{font-size:26px;font-weight:650;margin-top:6px;letter-spacing:-.02em}
.card .n{font-size:12px;color:var(--muted);margin-top:4px}
.v.ok{color:var(--ok)}.v.bad{color:var(--bad)}.v.warn{color:var(--warn)}
.ab{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.ab .col{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.ab .col h3{margin:0 0 10px;font-size:14px}
.ab .row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;
border-top:1px solid var(--line);font-size:14px}
.ab .row:first-of-type{border-top:0}
.ab .row b{font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);
border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:760px;font-size:13px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
position:sticky;top:0;background:var(--panel)}
tr:last-child td{border-bottom:0}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.tag{display:inline-block;border-radius:6px;padding:2px 7px;font-size:11px;font-weight:600;
white-space:nowrap}
.tag.block{background:var(--okbg);color:var(--ok)}
.tag.exec{background:var(--badbg);color:var(--bad)}
.tag.none{background:var(--warnbg);color:var(--warn)}
.tag.n{background:var(--accentbg);color:var(--accent)}
.tag.mute{background:var(--bg);color:var(--muted);border:1px solid var(--line)}
.panels{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.panel.good{border-left:3px solid var(--ok)}
.panel.limit{border-left:3px solid var(--warn)}
.panel h3{margin:0 0 10px;font-size:14px}
.panel li{margin:0 0 9px;font-size:13.5px}
.panel li b{display:block}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:10px;padding:13px 16px;font-size:13.5px;color:var(--muted)}
.note b{color:var(--ink)}
.svg-label{fill:var(--ink);font-size:12px;font-weight:600}
.svg-value{fill:var(--muted);font-size:11px}
.svg-arm{fill:var(--muted);font-size:10px}
.svg-base{fill:var(--bad);opacity:.85}
.svg-gov{fill:var(--ok);opacity:.85}
footer{margin-top:40px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);
padding-top:14px}
@media (max-width:600px){.wrap{padding:18px 12px 48px}.card .v{font-size:22px}}
"""


def _svg_comparison(pairs: list[tuple[str, int, int]]) -> str:
    """Inline SVG grouped bars comparing baseline vs governed.

    Deliberately has no ``xmlns``: inline SVG inside HTML is parsed into the SVG
    namespace automatically, and omitting it keeps the page free of any URL at
    all, which is what makes the "no external reference" check meaningful rather
    than cosmetic. Sizing is by ``viewBox`` + ``width="100%"`` so it scales with
    the container instead of assuming a viewport.
    """
    row_h, gap, label_w, pad = 26, 16, 210, 8
    bar_w = 620
    height = pad * 2 + len(pairs) * (row_h * 2 + gap)
    peak = max((max(a, b) for _, a, b in pairs), default=1) or 1
    out = [
        f'<svg viewBox="0 0 {label_w + bar_w + 60} {height}" width="100%" '
        f'height="{height}" role="img" aria-label="baseline versus governed comparison">'
    ]
    y = pad
    for label, baseline, governed in pairs:
        for value, cls, name in (
            (baseline, "svg-base", "plain"),
            (governed, "svg-gov", "governed"),
        ):
            width = max(2, round(bar_w * (value / peak)))
            out.append(
                f'<text x="0" y="{y + 14}" class="svg-label">{html.escape(label if name == "plain" else "")}</text>'
                f'<rect x="{label_w}" y="{y + 2}" width="{width}" height="{row_h - 8}" rx="4" class="{cls}"/>'
                f'<text x="{label_w + width + 8}" y="{y + 15}" class="svg-value">{value} <tspan class="svg-arm">{name}</tspan></text>'
            )
            y += row_h
        y += gap
    out.append("</svg>")
    return "".join(out)


def _tile(label: str, value: Any, note: str = "", tone: str = "") -> str:
    cls = f" {tone}" if tone else ""
    return (
        f'<div class="card"><div class="k">{html.escape(label)}</div>'
        f'<div class="v{cls}">{html.escape(str(value))}</div>'
        f'<div class="n">{html.escape(note)}</div></div>'
    )


def render_dashboard(
    metrics: dict,
    rows: list[dict],
    env: dict,
    adapter: dict,
    verdict: dict,
    candidate_digest: str = "",
) -> str:
    a, p, e = (
        metrics["allowed_path"],
        metrics["prevention"],
        metrics["evidence"],
    )
    x, se = metrics["execution_integrity"], metrics["side_effects"]
    esc = html.escape

    tiles = "".join(
        [
            _tile(
                "Prohibited actions prevented",
                f"{p['prohibited_callables_prevented_by_nornyx']}/"
                f"{p['prohibited_callables_executed_in_baseline']}",
                "executed in baseline → blocked under governance",
                "ok" if p["prohibited_callables_prevented_by_nornyx"] else "bad",
            ),
            _tile(
                "False denials",
                a["false_denials_of_valid_actions"],
                "valid actions wrongly refused",
                "ok" if a["false_denials_of_valid_actions"] == 0 else "bad",
            ),
            _tile(
                "False allows",
                p["false_allows_on_governed_path"],
                "prohibited actions that still ran",
                "ok" if p["false_allows_on_governed_path"] == 0 else "bad",
            ),
            _tile(
                "Output equivalence",
                "yes" if a["business_output_equivalence"] else "no",
                "identical business output on the allowed path",
                "ok" if a["business_output_equivalence"] else "bad",
            ),
            _tile(
                "Evidence events",
                e["events_emitted"],
                f"{e['events_bound_to_contract_digest']} bound to contract, "
                f"{e['events_bound_to_lock_digest']} to lock",
                "ok" if e["all_events_bound_to_contract_digest"] else "warn",
            ),
            _tile(
                "Evidence validation",
                e["validation_status"],
                f"full stream, {len(e['diagnostics'])} diagnostic(s)",
                "ok" if e["validation_status"] == "pass" else "bad",
            ),
        ]
    )

    heat = "".join(
        f"<tr><td class=mono>{esc(r['scenario'])}</td><td>{esc(r['title'])}</td>"
        f"<td><span class='tag n'>{esc(r['stage'])}</span></td>"
        f"<td class=mono>{esc(r['category'])}</td>"
        f"<td style='text-align:right'>{r['baseline_executed']}</td>"
        f"<td style='text-align:right'>{r['governed_executed']}</td>"
        f"<td><span class='tag {_STATE_CLASS[r['state']]}'>"
        f"{esc(r['state'])}</span></td>"
        f"<td class=mono>{esc(r['governed_decision'])}</td></tr>"
        for r in rows
    )

    changed = "".join(f"<li><b>{esc(t)}</b>{esc(d)}</li>" for t, d in WHAT_CHANGED)
    limits = "".join(f"<li><b>{esc(t)}</b>{esc(d)}</li>" for t, d in WHAT_WAS_NOT_SOLVED)

    coverage = "".join(
        f"<tr><td class=mono>{esc(s['surface'])}</td>"
        f"<td><span class='tag {'block' if s['status']=='wrapped' else 'none'}'>{esc(s['status'])}</span></td>"
        f"<td>{esc(s['reason'])}</td></tr>"
        for s in adapter["surfaces"]
    )

    diagnostics = ""
    if e["diagnostics"]:
        items = "".join(
            f"<li><b>{esc(d['code'])}</b><span class=mono>{esc(d['path'])}</span> — {esc(d['message'])}</li>"
            for d in e["diagnostics"]
        )
        diagnostics = (
            "<section><h2>Evidence diagnostics"
            "<span class=sub>the full stream did not validate — reported in full,"
            " nothing filtered</span></h2>"
            f"<div class='panel limit'><ul>{items}</ul></div></section>"
        )

    ab = f"""
    <div class="ab">
      <div class="col"><h3>Plain CrewAI</h3>
        <div class="row"><span>Business side effects</span><b>{se['baseline_total']}</b></div>
        <div class="row"><span>Prohibited actions executed</span><b>{p['prohibited_callables_executed_in_baseline']}</b></div>
        <div class="row"><span>Governance decisions</span><b>0</b></div>
        <div class="row"><span>Evidence events</span><b>0</b></div>
        <div class="row"><span>Revision binding</span><b>none</b></div>
      </div>
      <div class="col"><h3>Governed by Nornyx</h3>
        <div class="row"><span>Business side effects</span><b>{se['governed_total']}</b></div>
        <div class="row"><span>Prohibited actions executed</span><b>{p['prohibited_callables_executed_in_baseline'] - p['prohibited_callables_prevented_by_nornyx']}</b></div>
        <div class="row"><span>Decisions recorded pre-execution</span><b>{x['total_decisions_recorded']}</b></div>
        <div class="row"><span>Evidence events</span><b>{e['events_emitted']}</b></div>
        <div class="row"><span>Revision binding</span><b class=mono>{esc(e['contract_digest'][:19])}…</b></div>
      </div>
    </div>"""

    chart = _svg_comparison([
        ("All business side effects", se["baseline_total"], se["governed_total"]),
        (
            "Prohibited actions executed",
            p["prohibited_callables_executed_in_baseline"],
            p["prohibited_callables_executed_in_baseline"]
            - p["prohibited_callables_prevented_by_nornyx"],
        ),
        ("Evidence events emitted", 0, e["events_emitted"]),
    ])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nornyx Governance A/B Benchmark — CrewAI</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Nornyx Governance A/B Benchmark</h1>
  <p>One customer-support and financial-remediation workflow run twice — as an ordinary
  CrewAI application, and with the same agents, tasks, model, inputs, business rules and
  business callables governed by Nornyx through the supported CrewAI adapter. Every figure
  below is computed from an actual offline run.</p>
  <div class="meta">
    <span class="chip">nornyx {esc(str(env['nornyx_version']))}</span>
    <span class="chip">SPI {esc(str(env['nornyx_agentic_spi_version']))}</span>
    <span class="chip">adapters {esc(str(env['adapters_version']))}</span>
    <span class="chip">crewai {esc(str(env['crewai_version']))}</span>
    <span class="chip">python {esc(str(env['python_version']))}</span>
    <span class="chip">as-of {esc(str(env['as_of']))}</span>
    <span class="chip">candidate {esc(str(candidate_digest))}</span>
  </div>
</header>

<section><h2>Verdict<span class="sub">independent-auditor assessment</span></h2>
<div class="note"><b>{esc(verdict['verdict'])}</b> — {esc(verdict['summary'])}</div></section>

<section><h2>Headline<span class="sub">measured, not asserted</span></h2>
<div class="grid">{tiles}</div></section>

<section><h2>Plain versus governed
<span class="sub">bars are measured counts; red = plain, green = governed</span></h2>
{ab}
<div class="card" style="margin-top:12px">{chart}</div></section>

<section><h2>Scenario heat map
<span class="sub">counts are completions of the business callable</span></h2>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Scenario</th><th>Stage</th><th>Category</th>
<th style="text-align:right">Baseline</th><th style="text-align:right">Governed</th>
<th>Result</th><th>Diagnostic</th></tr></thead>
<tbody>{heat}</tbody></table></div></section>

<section><h2>What Nornyx changed — and what it did not</h2>
<div class="panels">
  <div class="panel good"><h3>What Nornyx changed</h3><ul>{changed}</ul></div>
  <div class="panel limit"><h3>What Nornyx did not solve</h3><ul>{limits}</ul></div>
</div></section>

<section><h2>Adapter coverage
<span class="sub">the adapter's own declared inventory, verbatim</span></h2>
<div class="scroll"><table>
<thead><tr><th>Surface</th><th>Status</th><th>Reason</th></tr></thead>
<tbody>{coverage}</tbody></table></div>
<p class="note" style="margin-top:12px">Anything not marked <b>wrapped</b> is outside the
enforcement boundary. The <span class="mono">S15</span> bypass control executes in both
variants and is never counted as prevented.</p></section>

{diagnostics}

<footer>
Offline, deterministic, no API key and no network. The evaluation instant is pinned to
{esc(str(env['as_of']))} because the SPI reads no wall clock.
<b>nornyx-agentic-adapters is not published on PyPI</b>; it is installed from the repository.
Timing figures elsewhere in this report are a local microbenchmark, not a production
latency claim. Any committed copy of this page is a snapshot of one run, not a
continuously verified claim — compare the candidate digest and rerun the benchmark.
</footer>
</div>
</body>
</html>"""


def render_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
