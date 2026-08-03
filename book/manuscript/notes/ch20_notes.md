# Chapter 20 notes — "Evidence Architecture"

## Status

Draft complete. Raw word count 5,154 (whole body including fenced blocks, tables, captions, and end
matter). Structure: 2 figures (20.1 HTML `seq`, 20.2 DOT lifecycle), 1 table, 3 listings, 19 index
spans. Callouts used: Opening scenario, Learning objectives, Prerequisites, Key idea, Assurance
boundary, Case study — Atlas, Misconception. Inline **[implemented]** badges throughout.

The assigned Thread A evidence-package scene is the `Case study — Atlas` callout in Section 20.6,
placed after the lifecycle figure so the four package items map onto the figure's outputs. It hands
the thread forward to Chapter 36 as the bible requires and does not re-introduce Atlas.

## Everything I verified directly against the repository

All paths relative to `/home/user/nornyx`.

- `schemas/agentic_runtime_events_v1.schema.json` — loaded and inspected programmatically.
  Confirmed: top-level `oneOf` over `envelopeV10` / `envelopeV11Legacy` / `envelopeV11Explicit`;
  each envelope's `required` list (1.0 has no `occurrence_mode`; both 1.1 envelopes require it);
  `events` `maxItems: 10000` on all three; the `occurrence` definition requiring
  `operation_id`, `occurrence_id`, and `attempt` (integer 1–1,000,000) with
  `additionalProperties: false`.
- `nornyx/agentic_evidence.py` — read the constant block and the occurrence/replay/attempt logic
  directly. Confirmed: `REPORT_SCHEMA = "nornyx.agentic_evidence_report.v1"`;
  `MAX_EVENTS_BYTES = 8 MiB`; `_REQUIRED_FIELDS_BY_TYPE` (including `capability_allowed` →
  `capability_ref`, `policy_decision`; `data_shared` → `share_categories`, `target_ref`;
  `approval_granted` → `approval_ref`, `approver`); `_EXPECTED_DECISION`;
  `_SUCCESS_TERMINALS` (6 types) and `_FAILURE_TERMINALS` (5 types); the `LIMITATIONS` tuple
  verbatim; the replay fingerprint block including the comment "A producer cannot evade exact
  replay detection merely by restamping a duplicate with a new timestamp" and the
  `replay_transport_fields.add("timestamp")` under `explicit_occurrences`; the
  `AN_EVT_ATTEMPT_AFTER_SUCCESS`, `AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION`, and
  `AN_EVT_ATTEMPT_GAP` construction sites.
- `nornyx/agentic/authz.py` — the `EvidenceRecorder` in full (1214–1681): constructor producer-type
  restriction and revision refusal; `_schema_version` taken from the lock and `_occurrence_mode`
  defaulting to `legacy` for 1.1; `for_occurrences` raising unless the lock is 1.1; `resume` and
  its five preconditions (producer equality, schema-version equality, occurrence-mode handling,
  full `validate_runtime_events` pass, no timestamp later than the resumed `decision_at`) plus
  sequence-counter restoration; `max_recorded_attempt`; `stream`; `validate`.
- `docs/agentic-network/06_RUNTIME_EVIDENCE.md` — read in full. All quoted sentences verified
  verbatim: the eighteen-type list and "Anything else requires a reviewed schema revision"; the
  ordering paragraph and "local sequence consistency of the supplied stream"; "It does **not** solve
  distributed causality…"; "Identical semantic evidence inside one attempt is replay; identical work
  in a new occurrence or retry attempt is not"; the identity-model sentence with "Authorization
  allowances and transition state are attempt-scoped"; "Differential chunks and multi-producer
  merging are not supported"; "a legacy stream is never silently upgraded" (paraphrased in the
  chapter as a quoted fragment — see caveat 1).
- `docs/agentic-network/08_SECURITY_BOUNDARIES.md` — the residual-risk sentence about a cooperative
  producer falsely claiming a new occurrence.
- `nornyx/cli.py` — the `evidence-validate` handler and argument definitions; cross-checked against
  `nornyx agentic-network evidence-validate --help`, which lists exactly
  `--events` (required), `--lock`, `--as-of`, `--out`, `--strict`, `--json`.
- `docs/agentic-network/11_REFERENCE_CI.md` (via fact pack 02 §10) for the claim that the reference
  pipeline passes `--strict` on both of its evidence-validation steps.

## Everything I executed

Working directory `/tmp/nyxwork/ch19` (shared with Chapter 19's setup: support contract, generated
artifacts, and lock).

1. `evidence_demo.py` — Listings 20.1 and 20.2. Recorded three occurrences-worth of history through
   `EvidenceRecorder.for_occurrences`. Observed report: `status pass`, `event_count 9`,
   `mission_count 1`, `counts_by_type {"capability_allowed": 3, "capability_requested": 3,
   "runtime_failed": 1, "tool_invoked": 2}`, `diagnostics []`. The envelope and the nine-row
   event table in Listing 20.2 are verbatim observed output.
2. `reject_demo.py` — Listing 20.3. Both diagnostics are verbatim:
   `AN_EVT_REPLAY  Event content replays an earlier event.` and
   `AN_EVT_ATTEMPT_AFTER_SUCCESS  A successfully completed occurrence cannot be retried; repeated
   work requires a new occurrence id.` The replay case duplicates a non-terminal
   `capability_allowed` event under a new `event_id`, `sequence`, and `timestamp`; an earlier
   attempt that duplicated a terminal `tool_invoked` produced two diagnostics
   (`AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION` as well), so I chose the non-terminal duplicate to
   isolate the replay rule cleanly. Worth knowing for the instructor guide.
3. `nornyx agentic-network evidence-validate support_network.nyx --events events.json
   --as-of 2026-07-17T00:00:00Z --out report.json --json` → exit 0, `status pass`. Inspected the
   written report: it carries `schema`, `status`, the four binding digests, `events_schema`,
   `events_schema_version`, `event_count`, `mission_count`, `counts_by_type`, `limitations` (the
   three sentences), and `safety` with all five flags false. The Atlas case-study callout describes
   exactly this report shape.
4. Strict-mode comparison on a tampered stream: without `--strict`,
   `{"status": "fail", "diagnostic_count": 1}` and **exit 0**; with `--strict`, identical output and
   **exit 1**. This is the observation behind Section 20.7's paragraph on the flag.
5. Resume: `EvidenceRecorder.resume` on the validated 9-event stream returned a recorder holding
   9 events, `max_recorded_attempt(... occurrence_id="task.1")` returned `2`, one further recorded
   decision produced an 11-event cumulative stream with last sequence 11 that validated `pass`.
   Also observed the two refusals quoted conceptually in Section 20.6:
   `"resumed context.decision_at must not precede prior event timestamps"` and
   `"prior_stream producer does not match the resumed recorder"`.

## Claims I could NOT verify, and what I wrote instead

1. **"A legacy stream is never silently upgraded."** I present this as a quoted rule. The exact
   sentence appears in fact pack 02 §5.3; in `docs/agentic-network/06_RUNTIME_EVIDENCE.md` I
   verified the surrounding mode descriptions and the lock-arbitration rule, and in
   `authz.py` I verified the code paths that make it true (constructor mode selection,
   `for_occurrences` raising on a non-1.1 lock, `resume` requiring mode equality). If an editor
   wants the quotation marks removed pending a line-exact citation, the sentence stands unchanged
   as a paraphrase.
2. **Historical 1.0 locks "are reconstructed and verified against their own declared version."**
   From fact pack 02 §4 item 5, citing the private `_build_agentic_network_lock(...,
   runtime_events_schema_version=...)` path and CHANGELOG 1.10.0. I did not read that function or
   construct a 1.0 lock. Stated once, in a subordinate clause, and nothing in the chapter depends
   on it.
3. **The `input_digest` / `output_digest` claim that "these digests are not semantically verified
   against any actual payload."** This is Chapter 11's citation of
   `docs/decisions/ADR-0040-governance-assurance-tiers.md`; I did not re-read that ADR. I phrase it
   as "those digests prove binding rather than content," which follows from the embedded
   `LIMITATIONS` sentence I did verify.
4. **The Atlas package's `capability_denied` ending.** Fictional continuity with Chapter 11's
   Thread A scene, which established the four-record March stream. The *report fields* the callout
   lists are the real fields I observed in item 3 above; only the narrative content is fictional.
5. **`AN_EVT_ARTIFACT_MISSING` / `AN_EVT_ARTIFACT_HASH_MISMATCH` behavior** is stated from
   `nornyx/agentic_evidence.py` (lines 746–781, read) and fact pack 02 §5.2. I did not execute a
   containment-escape case; Exercise 3 asks the reader to.
6. **"Ten of the eighteen are the decision-phase intents … the other eight are post-action
   observations."** Verified by comparing the schema's 18-value enum against `PHASE_INTENT` (10)
   and `PHASE_OBSERVATION` (8) in `authz.py`; the two sets are disjoint and their union is the
   enum. I did this comparison by hand rather than programmatically.

## Deliberate framing choices worth an editor's eye

- Section 20.7 criticizes the `--strict` default as "a fail-open default in the tool's *exit code*."
  This is my analysis, not a repository statement. I kept it because the chapter's honesty posture
  demands it and because the repository's own reference pipeline compensates by always passing the
  flag — which I do cite. If the editor considers this too evaluative for Part IV, the sentence can
  be cut without disturbing the surrounding argument.
- Figure 20.1 is a sequence rather than a state diagram because the assignment asked for a runtime
  sequence figure; the occurrence/attempt state machine is arguably clearer as a state diagram and
  could be added later without displacing this one.
- I did not re-teach Chapter 12's identity hierarchy; Section 20.1 recaps it in one sentence and
  moves immediately to the schema consequence, per the no-re-teaching rule.

## PROPOSED-REF additions

None. All further-reading keys (`lamport-clocks`, `merkle`, `in-toto`, `otel`, `nornyx-repo`) are
from `05_bibliography.md`.
