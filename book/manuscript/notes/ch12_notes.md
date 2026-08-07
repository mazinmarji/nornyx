# Chapter 12 — Author Notes

## Claims I could NOT verify (and what I wrote instead)

1. **Ledger case-study stream.** The two €50,000 records, the `adj.1` / `adj.2` occurrence identifiers,
   the mission `CASE-4471`, and the intervening `runtime_failed` record are fictional case-study
   material built on real schema semantics. Every field name used (`occurrence.operation_id`,
   `occurrence.occurrence_id`, `occurrence.attempt`, `mission_id`, `runtime_failed`) is real; the values
   are not repository data. Table 12.2's classifications follow directly from the verified rules.
2. **Live regeneration of the byte-identical generation result.** I did not re-run
   `nornyx agentic-network generate` in this authoring pass. Section 12.7 attributes the byte-identical
   result to the fact-pack audit explicitly ("The fact-pack audit verified the property rather than
   assuming it: two successive generations … produced byte-identical directories under `diff -r`"),
   rather than presenting it as something I observed. Same for the abridged lock in Listing 12.1, whose
   caption says it was "built during the fact-pack audit."
3. **`AS_OF_INVALID`.** Taken from fact pack 01 §3 and the CHANGELOG entry for 1.9.0, not read in code
   during this pass. It is stated only as the fail-closed outcome of a malformed or naive `--as-of`.
4. **`nornyx drift` status vocabulary (`ok`/`changed`/`missing`/`stray`).** Taken from fact pack 01 §4.2
   citing `nornyx/repo_drift.py`; not independently re-read here.
5. **Lock excerpt digests.** The digests in Listing 12.1 are the truncated values recorded in fact pack
   02 §11 from a live lock build; I abridged and elided further, and the caption says so. No digest in
   the chapter should be treated as reproducible without re-running the tool on the same inputs.

## PROPOSED-REF additions

None. Citations used: [@merkle], [@lamport-clocks], [@reproducible-builds], [@in-toto] — all canonical.

## Repository paths I personally verified

- `/home/user/nornyx/nornyx/agentic_evidence.py` — read three regions directly:
  - lines 380–425: the replay fingerprint. Confirmed `replay_transport_fields = {"event_id",
    "sequence"}` with `"timestamp"` added only when `explicit_occurrences` is true, the SHA-256 over the
    remaining fields with `sort_keys=True`, the `AN_EVT_REPLAY` diagnostic, and the in-code comment
    quoted in Section 12.5 ("A producer cannot evade exact replay detection merely by restamping a
    duplicate with a new timestamp"). Also confirmed `AN_EVT_DUPLICATE_ID` and
    `AN_EVT_DUPLICATE_SEQUENCE` in the same region.
  - lines 885–945: occurrence handling. Confirmed `AN_EVT_OCCURRENCE_OPERATION_MISMATCH`
    ("An occurrence id cannot move between logical operations in one mission"),
    `AN_EVT_ATTEMPT_ORDER_INVALID`, and `AN_EVT_ATTEMPT_AFTER_SUCCESS` whose message is
    "A successfully completed occurrence cannot be retried; repeated work requires a new occurrence id."
    — quoted in the Section 12.6 callout.
  - lines 1050–1070: `AN_EVT_ATTEMPT_GAP` with the message "attempts must be contiguous from 1."
  - lines 60–95: `_SUCCESS_TERMINALS` (includes `tool_invoked`, `handoff_completed`) and
    `_FAILURE_TERMINALS` (includes `runtime_failed`, `capability_denied`) — the sets named in the
    Section 12.6 callout.
- `/home/user/nornyx/docs/agentic-network/06_RUNTIME_EVIDENCE.md` — read in full. Source of the
  verbatim ordering-scope sentence ("local sequence consistency of the supplied stream"), the
  distributed-causality limitation, the four-level identity definitions, and the replay rule
  ("Identical semantic evidence inside one attempt is replay; identical work in a new occurrence or
  retry attempt is not").
- `/home/user/nornyx/docs/decisions/ADR-0040-governance-assurance-tiers.md` — read in full (used for the
  contract-state-binding framing behind Section 12.2's assurance-boundary callout).

Facts taken from the fact packs without independent re-verification (all carry repository paths there):
the nine lock-bound elements and the `AN_LOCK_*` verification codes (fact pack 02 §4, citing
`schemas/agentic_network_lock_v1.schema.json` and `nornyx/agentic_artifacts.py:685–774, 916–1028`);
`AN_LOCK_REVISION_MUTABLE` and the immutable-revision pattern (fact pack 02 §2.1, §4); the ordering and
pairing diagnostic codes `AN_EVT_SEQUENCE_GAP`, `AN_EVT_ORDER_INVALID`, `AN_EVT_DEPENDENCY_MISSING`,
`AN_EVT_TOOL_WITHOUT_ALLOWANCE`, `AN_EVT_ACCEPTANCE_WITHOUT_REQUEST`,
`AN_EVT_COMPLETION_WITHOUT_INITIATION`, `AN_EVT_GRANT_WITHOUT_REQUEST` (fact pack 02 §5.2);
`EvidenceRecorder.resume` semantics and the "differential chunks and multi-producer merging are not
supported" limit (fact pack 02 §5.4); canonical JSON, LF newlines, and timestamp-free generation
(fact pack 01 §4.1, §8).

## Note on the hostile-writer quotation

Section 12.2's assurance-boundary callout quotes `docs/agentic-network/07_NETWORK_LOCK.md` via fact
pack 02 §4 ("What the lock does NOT prove", recorded there as verbatim). I did not open that file
directly in this pass; the identical claim also appears in the lock schema description
(`schemas/agentic_network_lock_v1.schema.json:5`) per the same fact-pack section.
