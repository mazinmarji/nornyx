# Chapter 21 notes — "Diagnostics and Generated Artifacts"

## Status

Draft complete. Raw word count 5,126 (whole body including fenced blocks, captions, and end matter).
Structure: 2 figures (21.1 HTML `layers`, 21.2 HTML `flow` with a dashed bypass row), 2 listings,
0 tables, 15 index spans. Callouts used: Opening scenario, Learning objectives, Prerequisites,
Key idea, Misconception, Assurance boundary, Case study — Forge, Design checkpoint. Inline
**[implemented]** badges throughout.

The assigned Thread B scene is the `Case study — Forge` callout in Section 21.5, placed immediately
after the drift transcript so the fictional CI story lands on real observed behavior. It advances
the thread (the merge lane closes; the contributor's remaining options are a contract change or a
bounded exception) and forwards to Chapters 29 and 30 per the bible.

No table appears in this chapter. The style guide asks for 1–4; I judged that every candidate table
here — the artifact inventories, the diagnostic namespaces, the exit codes — reads better as prose
or a numbered list, since each is a *list of names* rather than a comparison across dimensions.
Flagging in case the editor wants the exit-code contract promoted to a table; it is the one item
with a natural two-column shape.

## Everything I verified directly against the repository

All paths relative to `/home/user/nornyx`.

- `nornyx/generator.py` — read for the artifact set and the determinism mechanisms: the `_write`
  helper forcing LF newlines, the sorted artifact-path and hash lists, the absence of any timestamp
  field, and the `nornyx.generation_manifest.v0.1` manifest with per-artifact sha256.
- `nornyx/agentic_artifacts.py` — read the forbidden-content machinery directly:
  `_FORBIDDEN_KEY_SEGMENTS` (I counted the set: 26 entries), `_FORBIDDEN_KEY_PAIRS` (4 pairs:
  `api key`, `key material`, `private key`, `access key`), `_KEY_SPLIT_RE`, `_IPV4_RE`,
  `_SCHEMA_ID_RE` (the single exempted pattern), `_forbidden_key`, and `_scan_forbidden` including
  both raise sites (`AN_ARTIFACT_FORBIDDEN_FIELD`, `AN_ARTIFACT_FORBIDDEN_VALUE`). Also read the
  comment justifying segment matching over substring matching ("avoids false positives on reviewed
  declaration fields such as `execution_mode` and `agent_key`"), which the chapter reproduces as an
  explanation.
- `nornyx/generation_drift.py` — `BASELINE_SCHEMA = "nornyx.generated_drift_baseline.v0.1"`,
  `DEFAULT_DRIFT_CASES` naming exactly the two example contracts and their baseline fixtures under
  `tests/fixtures/generated_drift/`.
- `nornyx/repo_drift.py` / `nornyx/cli.py` — the `nornyx.repo_drift_report.v0.1` schema and the
  `ok` / `changed` / `missing` / `stray` statuses; confirmed the CLI flag set via
  `nornyx drift --help` (`--out`, `--json` only).
- `nornyx/workspace.py` — the normalized rule-set comparison, the per-member/per-policy status
  vocabulary, the `nornyx.workspace_report.v0.1` schema, and the sync docstring sentence "sync edits
  existing policies, it does not invent new blocks or files" (quoted verbatim in Section 21.6).
  Flag set confirmed via `nornyx workspace-check --help` (`--manifest`, `--write`, `--quiet`,
  `--json`).
- `docs/GOVERNANCE_CLI_AND_API.md` — read the exit-code table (0/1/2 with its exact wording) and the
  diagnostic-namespace list (`PACK_*`, `RULE_*`, `GOVERNANCE_*`, `APPROVAL_*`, `EVIDENCE_*`,
  `SOD_*`, `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`, `AN_*`) and the deprecation-window sentence quoted
  in Section 21.4.
- `README.md` lines 16–19 and 50–60 — confirmed the seven-artifact shorthand appears twice and that
  neither instance mentions `trace.yaml`, `goals.yaml`, task packets, the goal ledger, or the
  manifest.
- `docs/agentic-network/05_PROTOCOL_DECLARATIONS.md` (via fact pack 02 §1) for "**declarations, not
  runtimes**" and the mandatory `execution_mode: contract_only` / `live_connector_execution: false`
  pair.
- `docs/agentic-network/07_NETWORK_LOCK.md` — the "A hostile local writer can regenerate a
  consistent lock…" sentence quoted in the Section 21.3 assurance boundary.

## Everything I executed

Working directories `/tmp/nyxwork/ch21` and `/tmp/nyxwork/ws`.

1. `nornyx generate governed_delivery_control_plane.nyx --out generated` → observed the full file
   list: `AGENTS.md`, `context.yaml`, `evals.yaml`, `evidence_contract.md`, `goals.yaml`,
   `harness.yaml`, `policy.yaml`, three `skills/<Name>/README.md`, `trace.yaml`, and
   `nornyx_generation_manifest.json` — **11 artifacts**, matching the manifest's
   `"artifact_count": 11`.
2. `nornyx generate nornyx_roadmap_goals.nyx --out gen_goals` → **22 artifacts**, including
   `goal_ledger.md` and eight `task_packets/GOAL-00N.md` files. This is the source of the "eleven to
   twenty-two" range in Section 21.2 and Review question 2.
3. Confirmed the generated `AGENTS.md` header line verbatim: "This file is generated. Edit the
   `.nyx` source instead."
4. **The full drift transcript in Listing 21.1 is verbatim observed output**, abridged only by
   removing repeated header lines in the third block. Sequence: generate → `drift` exit 0 →
   `sed -i '/deny secrets_to_llm/d' generated/policy.yaml` → `drift` reports
   `[CHANGED] policy.yaml`, exit 1 → regenerate → `drift` exit 0. The `--json` run in the same
   session reported all eleven artifacts with ten `ok` and one `changed`.
5. **Reproduced the documented AGENTS.md-only blind spot.** After the `policy.yaml` edit, a
   `diff` of the committed `AGENTS.md` against a freshly generated one produced no output at all.
   This is the live confirmation of the case study's "Bug 2," and it is what Figure 21.2's lower
   dashed flow depicts.
6. **Determinism**: two `nornyx agentic-network generate` runs of the support contract into separate
   directories, `diff -r` clean (exit 0).
7. **Fail-closed `--as-of`**: the same generate command with `--as-of 2026-08-03T00:00:00Z` exited 1
   with `AN_APPROVAL_EXPIRED`, four `EVIDENCE_STALE` lines, and `APPROVAL_EXPIRED`, and **created no
   output directory**. The three lines quoted in Section 21.3 are a verbatim subset (I dropped three
   of the four repeated `EVIDENCE_STALE` lines and said so implicitly by quoting one).
8. **Forbidden-content scan**: editing one delegation `purpose` in a copy of the support contract to
   contain `https://runbooks.internal/refunds` produced
   `AN_ARTIFACT_FORBIDDEN_VALUE: Generated declarations must not contain URLs or transport
   references.`, exit 1, no output directory. Verbatim.
9. **Workspace check**: built a two-member workspace with one drifted member. `workspace-check
   --json` → the Listing 21.2 output, exit 1. `--write` → status `synced`, member statuses `ok` and
   `synced`, the rule restored in the member file's existing indentation style, and a follow-up
   check exit 0. Listing 21.2 is verbatim observed JSON, reformatted for line width only.
10. **Context pack**: `nornyx context-build … --out ctx.json` produced
    `nornyx.context_pack.v0.1` with top-level keys `schema`, `repo`, `trust_models`, `rules`,
    `entries`, `count`. Confirmed the three `rules` strings verbatim, including "Authority rank is
    advisory metadata until a later enforcement goal." With two matching files present, entries
    carried `path`, `sha256`, `bytes`, `taint`, `channel`, `trust_level`, `authority_rank`,
    `authority_pattern`, `may_define_policy`, and a `provenance` object with `source_type`,
    `source_uri` (`repo://…`), `repo_root`, `sha256`, `bytes` — exactly the field list Section 21.7
    describes.
11. `nornyx agentic-network lock-check … --json` → `nornyx.agentic_network_lock_check.v1`,
    `status pass`, empty diagnostics (used only to confirm the schema name I reference indirectly).

## Claims I could NOT verify, and what I wrote instead

1. **The development baseline gate was not executed.** I read `nornyx/generation_drift.py` and the
   fixture directory but did not run the gate or its `--update` path. Section 21.5 describes it from
   the code; the *worked* transcript is the user-facing gate, which the assignment asked for.
2. **The "false sense of safety" bug history** is from `docs/CASE_STUDY_multi_repo_governance.md`
   via fact pack 04 §2.4. I did not read that document directly. I did reproduce the *behavior* it
   describes (item 5 above), so the chapter's claim rests on my own observation and attributes the
   history to "the repository's multi-repository case study" without quoting version numbers.
3. **The deprecation-window sentence** ("will not be removed without a changelog deprecation notice
   lasting at least two package minor releases and six months") is quoted from
   `docs/GOVERNANCE_CLI_AND_API.md`, which I read. What I could not verify is whether it has ever
   been *exercised*; the chapter uses it as a stated commitment, not as evidence of practice.
4. **The count "twenty-six transport, credential, or execution terms."** I counted
   `_FORBIDDEN_KEY_SEGMENTS` by hand from the source and matched fact pack 02 §2.4's enumeration.
   The chapter gives fourteen examples inline rather than the full list, so the count is the only
   load-bearing number.
5. **"A network with no delegations still gets a delegation bundle, empty."** Inferred from the
   fixed `ARTIFACT_NAMES` tuple and the observed `artifact_count: 10` on a contract that does
   declare one delegation. I did not generate from a delegation-free network. Stated as a property
   of the fixed set; if an editor wants it removed it is one sentence.
6. **The Forge case-study CI ordering** (drift gate before tests and before approvals) is a design
   choice I attribute to Northstar, not to the repository. The repository's reference pipeline does
   run its drift gate early (step 5 of fourteen, per fact pack 02 §1), which is consistent, but the
   chapter's ordering rationale is fiction-side.

## Deliberate framing choices worth an editor's eye

- Section 21.3 defends the bluntness of the forbidden-value scan as "the correct trade for this
  artifact class." This is authorial judgment; the repository states the rule but not the
  justification. It is flagged as reasoning, not quoted.
- I chose not to renumber the chapter's sections after inserting Figure 21.1 into Section 21.1; the
  drift-gate figure became 21.2 and every in-text reference was updated. Both figure ids
  (`fig-21-1`, `fig-21-2`) are unique and match their captions.
- Section 21.2's `Misconception` box attacks the project's own README. I kept it because the gap
  between seven and twenty-two artifacts is exactly the hazard the chapter teaches, and because
  naming it is more useful to a reader than a diplomatic omission. The tone is neutral and the
  README is not disparaged — the point is that prose inventories drift, which is the same argument
  the book makes about copied policies in Chapter 8.

## PROPOSED-REF additions

None. All further-reading keys (`reproducible-builds`, `merkle`, `slsa`, `sre-book`,
`nornyx-repo`) are from `05_bibliography.md`.
