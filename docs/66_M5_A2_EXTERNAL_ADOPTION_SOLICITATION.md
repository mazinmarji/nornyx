# External Adoption Solicitation Pack (M5-A-2a)

This document is the reviewer-facing layer around the merged M5-A-1 external
adoption pilot (`examples/external_adoption_pilot`). It exists to make an
external result **easy to produce and easy to evaluate** — nothing here asserts
that any external result has been produced.

## Read this first: what is and is not established

First-party CI proves the reproducible artifact exists. First-party CI does
**not** prove external adoption. Those are different claims and this repository
keeps them apart deliberately.

| Signal | Current status |
| --- | --- |
| Reproducible artifact an external user can run | ✅ M5-A-1, CI-verified |
| An external user has run it | ❌ none recorded |
| An external user reported a result | ❌ none recorded |
| An external pilot reached a governed decision on their own contract | ❌ none recorded |

Three of those four rows are empty. The purpose of this pack is to make them
fillable — by someone who is not the maintainer — not to imply they are filled.

**The M5 promotion gate is not met.** See [M5 gate status](#m5-gate-status).

---

## 1. Five-minute external adoption path

No repository checkout. No API key. No live external model service. No
connector runtime. No approval step. The pilot ships a scripted local model and
drives CrewAI's real executor offline.

**Prerequisite:** Python 3.10–3.13.

### Step 1 — clean environment

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1
```

### Step 2 — install the published packages

```bash
pip install "nornyx-agentic-adapters[crewai]==0.3.0"
```

This is the entire dependency acquisition. Everything below runs from installed
packages.

### Step 3 — get the pilot

The pilot is example code, not part of the distribution. Download the
`examples/external_adoption_pilot/` directory from this repository — as a
release archive, a sparse checkout, or by copying the files — and place it
beside your working directory as `external_adoption_pilot/`.

> Downloading example files is not the same as cloning to run the product. The
> claim being tested is that the **product** runs from installed packages; the
> pilot is the measuring instrument, and it deliberately refuses to import
> anything from a repository at run time.

### Step 4 — run it

```bash
python -m external_adoption_pilot --json --out adoption-record.json
```

The pilot builds its **own** clean virtual environment, installs the published
adapter into it from PyPI, and runs the scenario there. Your outer environment
is only the launcher.

### Step 5 — read the governance delta

Expected shape:

| variant | executions | authorizations | decision events |
| --- | ---: | ---: | ---: |
| `ungoverned` | 1 | 0 | 0 |
| `governed_authorized` | 1 | 1 | 2 |
| `governed_unauthorized` | **0** | ≥1 | paired requests/denials |

The third row is the one to look at. CrewAI's executor may retry the denied
call; the wrapped action must still run **zero** times, and every
`capability_requested` must pair with a `capability_denied`.

### Step 6 — report it

Open an issue using
[`external-adoption-result`](../.github/ISSUE_TEMPLATE/external-adoption-result.yml)
(or `external-adoption-failure` if it did not pass) and attach
`adoption-record.json`. Redaction guidance is in the template.

---

## 2. External reviewer quickstart

Written for a technical reviewer, maintainer, governance reviewer, AI
engineering lead, or framework user who has thirty minutes and no reason to
trust the claims yet.

### What does this prove?

That a published package, installed from PyPI into an environment containing no
repository checkout, enforces an authorization decision on a real CrewAI tool
call — permitting an authorized capability, refusing an unauthorized one, and
emitting evidence for both.

### What does it not prove?

- It does not prove anyone outside the maintainer flow has run it.
- It does not authenticate agents or approvers. Identities are contract
  declarations, not verified principals.
- It does not prove recorded events are truthful. Evidence is self-reported by
  cooperating components (ADR-0040 Tier 2, cooperative).
- It does not prevent bypass. Code paths that never call the governed wrapper
  are ungoverned — the pilot's own `ungoverned` variant demonstrates exactly
  that, on purpose.
- It is not whole-application coverage. One tool-invocation surface, one
  contract.
- It makes no Tier 3 claim.

### What command do I run?

```bash
pip install "nornyx-agentic-adapters[crewai]==0.3.0"
python -m external_adoption_pilot --json --out adoption-record.json
```

### What output should I expect?

Exit code `0`, and a record whose `governance_delta` reads:

```json
{
  "action_reachable_ungoverned": 1,
  "action_permitted_when_authorized": 1,
  "action_prevented_when_unauthorized": true,
  "evidence_absent_ungoverned": true,
  "evidence_present_when_governed": true
}
```

If `action_prevented_when_unauthorized` is `false`, that is the most
significant possible result and should be reported first.

### What failure class should I report?

The pilot classifies its own failures and prints a `remedy`. Report the class
verbatim:

| Class | Attributed to |
| --- | --- |
| `REGISTRY_INSTALL_FAILED` | the published distributions |
| `INSTALLED_VERSION_MISMATCH` | the published distributions |
| `FRAMEWORK_EXTRA_UNAVAILABLE` | the published distributions |
| `SOURCE_TREE_LEAKAGE_DETECTED` | the published distributions |
| `SCENARIO_EXECUTION_FAILED` | the published distributions |
| `GOVERNANCE_EXPECTATION_UNMET` | the published distributions |
| `PILOT_INPUT_INVALID` | your invocation or local environment |

Only the last one points at the reporter. If you see any of the other six, the
report is about this project and needs no apology.

### How do I attach the adoption record?

`--out adoption-record.json` writes it. Paste it into the issue template or
attach the file. Read [redaction](#redaction) first.

### What counts as external adoption evidence?

A run performed by someone outside the maintainer flow, reported with enough
detail to be checked: environment, versions, whether a repository checkout was
present, and the record itself. A green CI badge in this repository is **not**
external adoption evidence, and is not counted as one.

---

## 3. Success criteria

Grouped so that what has been achieved cannot be read as what has not.

### Artifact availability — achieved (first-party)

- `nornyx-agentic-adapters` 0.3.0 resolves from PyPI as a wheel.
- The `[crewai]` extra installs its declared pin.
- Verified continuously by the `pip-only-example` CI job.

### Execution reproducibility — achieved (first-party)

- The pilot runs from installed packages with no repository checkout at run
  time, on Linux and Windows.
- Import origins and package resources resolve from the environment's
  `site-packages`, asserted positively rather than by absence.
- Verified continuously by the `external-adoption-pilot` CI job through its
  standalone, outside-the-checkout path.

### Governance behavior — achieved (first-party)

- Ungoverned baseline executes, so a denial is meaningful.
- Authorized capability executes and records `capability_allowed`.
- Unauthorized capability executes zero times, records `capability_denied`, and
  emits no success observation.
- Requests and denials pair exactly under framework-controlled retries.

### Audit record quality — achieved (first-party)

- Machine-readable record with environment, versions, import origins, contract
  origin and subject revision, per-variant counts, and a governance delta.
- `external_model_service_called` is labelled a structural constant;
  `scripted_in_process_model_called` is labelled observed. Reporting only the
  constant would read as evidence while measuring nothing.

### External signal — **not achieved**

- ❌ No run by anyone outside the maintainer flow has been recorded.
- ❌ No external report has been received.
- Criterion: at least one issue filed from `external-adoption-result` or
  `external-adoption-failure` by a non-maintainer, containing an adoption
  record and stating whether a repository checkout was present.

### Own-contract pilot — **not achieved**

- ❌ No external user has reached a governed decision against a contract they
  authored.
- Criterion: at least one issue filed from `external-contract-pilot` showing a
  decision on a non-bundled contract, with the capability allowed and the
  capability denied both named, and evidence emission stated.

The first four groups are satisfied by first-party CI. The last two cannot be
satisfied by this repository at all — only by someone outside it.

---

## 4. Reporting templates

| Template | Use when |
| --- | --- |
| [`external-adoption-result`](../.github/ISSUE_TEMPLATE/external-adoption-result.yml) | The pilot ran and reported a result — pass or a governance finding |
| [`external-adoption-failure`](../.github/ISSUE_TEMPLATE/external-adoption-failure.yml) | The pilot failed with a classified failure |
| [`external-contract-pilot`](../.github/ISSUE_TEMPLATE/external-contract-pilot.yml) | You ran governance against your own `.nyx` contract |

### Redaction

Do not send secrets, credentials, tokens, API keys, private prompts, internal
policy text, or proprietary contracts.

The adoption record is designed to be shareable: it contains versions, paths,
counts, and event type names. Before pasting, replace absolute paths that
disclose internal structure with `<redacted>` — the useful signal is whether a
path was inside `site-packages` or inside a checkout, not what the path was.

For an own-contract pilot, describe capability and identity names
*structurally* (`capability.<redacted-write-capability>`) if the real names are
sensitive. A structural description is still a usable report.

---

## 5. M5 gate status

- **M5-A-1 — complete.** Produced the reproducible first-party artifact:
  `examples/external_adoption_pilot`, merged and verified on `main`.
- **M5-A-2a — this document.** Creates the external solicitation and reporting
  machinery: the five-minute path, the reviewer quickstart, falsifiable success
  criteria, and three issue templates.
- **M5-A-2b — not started.** The migration guide from `AGENTS.md`, policy files,
  and eval configuration to `.nyx` is deliberately deferred.
- **M5 promotion — not met.** It remains unmet until at least one external user
  reports a result from outside the maintainer flow.

No amount of first-party CI can move that gate. That is the intended property,
not a gap in the tooling: a gate a project can satisfy by itself measures the
project's diligence, not its adoption.

Standards mapping (issue #47,
[`64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md`](64_STANDARDS_MAPPING_AND_ENTERPRISE_ASSURANCE.md))
is sequenced after this deliberately, so a mapping can reference observed
behavior rather than internal claims alone. It is not started here.

## Related

- [`examples/external_adoption_pilot/README.md`](../examples/external_adoption_pilot/README.md)
  — the pilot's own documentation, taxonomy, and assurance boundary
- [`examples/pip_only_conformance/README.md`](../examples/pip_only_conformance/README.md)
  — package provenance and no-checkout resource integrity
- [`49_NORNYX_5_MINUTE_ADOPTION.md`](49_NORNYX_5_MINUTE_ADOPTION.md) — the
  checkout-based path for evaluating Nornyx core
- [`03_ROADMAP_TO_v1_AND_BEYOND.md`](03_ROADMAP_TO_v1_AND_BEYOND.md) — M5 in
  the wider milestone sequence
