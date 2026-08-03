# Chapter 17 — Author notes

Snapshot basis: `/home/user/nornyx` at `70d2b40`, distribution 1.11.0. All command transcripts in
the chapter were produced by running the installed `nornyx` CLI against files under
`/tmp/nyxbook/atlas/`.

## Claims I could NOT fully verify (and what I wrote instead)

1. **Whether `require` rules are consumed anywhere downstream.** I verified that
   `normalize_policy_rules` buckets them and that `_policy_decision` emits them as
   `{"rule": …, "status": "pending_evidence"}`; I did not trace a consumer that later discharges
   those obligations. The chapter therefore says they "become named pending-evidence obligations
   recorded against every governed step" and that whether they were met "is established by the
   evidence pipeline of Chapter 20, not by the policy evaluator" — a forward reference, not an
   assertion that Chapter 20's machinery consumes this particular report.

2. **The `capabilities` / `guardrails` extension-block path.** I did not construct a contract
   exercising `CAPABILITY_NOT_DECLARED`, `CAPABILITY_APPROVAL_REQUIRED`, or
   `GUARDRAIL_REQUIRED_FOR_EXTERNAL_USE` live. Those three code names and the
   `deny_unless_declared` default are taken from fact pack 01 §2.5 with its
   `nornyx/policy_runtime.py` line citations; I did observe `"default_capability_mode":
   "deny_unless_declared"` in a real report. The chapter states the semantics without a quoted
   transcript for that path.

3. **Structural-check internals of `nornyx/governance/structural.py`.** Fact pack 01 §16 warns that
   this 2,400-line module was only spot-checked. Chapter 17 makes no claim that depends on it; the
   sentence about governance modules promoting `approvals` entries into normalized, revision-bound,
   expiring records is stated at the level the module data and schemas support and is developed in
   Chapter 18, not here.

4. **"Twenty-three recognized relations."** I counted the entries of `GRAPH_RELATION_RULES` in
   `nornyx/checker.py` by reading the dict (23 keys) rather than by executing an introspection
   command. The count matches fact pack 01 §3.

## Verified-live corrections to my own drafting assumptions

- The deny matcher runs **only for flow steps of kind `agent`** (`_policy_decision` returns `None`
  unless `kind == "agent"`). I nearly wrote that deny rules apply to all steps; the chapter now
  states the asymmetry explicitly and flags it as easy to trip over.
- `nornyx check` on a contract whose `nornyx:` marker is unrecognized still **passes** (warning,
  exit 0) — used in Ch. 16, cross-referenced here.
- The unrecognized-rule-prefix behaviour (a rule that begins with neither verb lands in `require`)
  is real and silent; I made it a named hazard rather than a footnote.

## PROPOSED-REF additions

None. Citations used: `nornyx-repo`, `opa`, `cedar`, `greshake-injection`,
`schneider-enforceable` — all existing keys.

## Repository paths I personally read

- `examples/governed_delivery_control_plane.nyx` (read in full; source of Listings 17.1, 17.2, 17.3)
- `nornyx/checker.py` — lines 1–70 (`REQUIRED_TOP_LEVEL`, `NAMED_LIST_BLOCKS`,
  `CORE_TOP_LEVEL_BLOCKS`, `EXTENSION_TOP_LEVEL_BLOCKS`), lines 118–205 (`_graph_ref_targets`,
  `GRAPH_RELATION_RULES`, named-entry validation), lines 452–585 (contracts/auditability warnings),
  lines 163–215 of `nornyx/cli.py` for `cmd_check`'s exit-code logic
- `nornyx/policy_runtime.py` — lines 80–140 (`normalize_policy_rules`, `normalize_capabilities`)
  and lines 180–290 (`_matches_deny_rule`, `_policy_decision`, `_capability_decision`)
- `schemas/nornyx_v1_0.schema.json` (closed top level; `nornyx` version consts)
- `schemas/governance_evidence_v1.schema.json` (used for the Ch. 18 cross-reference)
- `docs/01_LANGUAGE_SPEC_v0_1.md` (YAML-compatibility rationale; the "do not define stable v0.1
  runtime behavior" sentence at line 44)
- `docs/05_SECURITY_MODEL.md` (read-only decision manifest; "records decisions but does not
  execute" — via fact pack citation)
- `docs/02_ARCHITECTURE.md` (processing path)
- `README.md` (the `ref` section and the bundled `org_policies.nyx`/`governed_service.nyx` pair)
- `examples/governance_foundations.nyx` (read; used in Ch. 18)

## Commands executed (all outputs under `/tmp/nyxbook/atlas/`)

- Wrote `atlas.nyx` (Listing 17.7) → `nornyx check atlas.nyx` → "Nornyx check passed", exit 0
- `nornyx policy-check atlas.nyx --harness ResearchHarness --out policy_report.json` → summary
  `{"allowed": 0, "planned": 5, "blocked": 0, "requires_human_approval": 0,
  "pending_evidence": 9}`; report schema `nornyx.policy_report.v0.1`; safety block observed
- `atlas_publish.nyx` (adds `action: publish_release_brief`) → `policy-check` → `"blocked": 1` and
  the `POLICY_DENY_MATCHED` decision quoted verbatim in Listing 17.8
- `atlas_broken.nyx` (renamed policy + renamed eval + invented `monitoring:` block) →
  `UNKNOWN_POLICY_REFERENCE`, `UNKNOWN_EVAL_REFERENCE`, `UNKNOWN_TOP_LEVEL_BLOCK`, exit 1
  (Listing 17.6, verbatim)
- `org_policies.nyx` + `atlas_ref.nyx` → `nornyx check` passed; `nornyx generate atlas_ref.nyx
  --out gen_ref` → inspected `gen_ref/policy.yaml` and confirmed the referenced rules are inlined
- `atlas_ref_remote.nyx` (https ref) → `PARSE_ERROR` "remote or device-backed ref sources are not
  allowed", exit 2 (Listing 17.5)
- `atlas_ref_missing.nyx` (nonexistent policy name) → `PARSE_ERROR` "policy 'NorthstarCharter' not
  found in org_policies.nyx", exit 2 (Listing 17.5)
- `atlas_graph.nyx` (typed graph block, Figure 17.2) → check passed;
  `atlas_graph_bad.nyx` (`has_skill` → `governs`) → `INVALID_GRAPH_RELATION_PAIR`, exit 1;
  `atlas_graph_unk.nyx` (`has_skill` → `supervises`) → `UNKNOWN_GRAPH_RELATION` warning, exit 0
- `nornyx explain atlas.nyx` (used to sanity-check block counts)

## Editorial notes

- Listing 17.7 is captioned as written-for-the-book but *verified runnable*, not as "Illustrative",
  because it was actually checked. Listings 17.1–17.3 cite the repository path and line ranges.
- Figure 17.2's edges are exactly the six relations in the verified `atlas_graph.nyx`, so every
  arrow in the figure is one the checker accepted.
- The chapter deliberately does not re-teach Chapter 5–7 material; contexts, capabilities, and
  default-deny are referenced by chapter number with at most a one-sentence recap.
