# Chapter 34 notes — "Threat Modeling Governed Agentic Systems"

## Status

Draft complete. Prose word count 5,524 by the manuscript's counting method (front matter and fenced
blocks excluded — which removes both DOT figures entirely — HTML tags stripped, figcaptions and
table cells retained). Table 34.1 (six attacker rows) and Table 34.2 (eight mitigation rows, five
columns) together account for roughly 700 of the measured words; body paragraphs alone are well
inside the band. Five trimming passes were applied. If a hard cap on the measured number is required,
the cheapest remaining cut is Table 34.1's "Position and capability" column (≈120 words), which is
partly restated in the prose of Section 34.2.

Structure: 3 figures — 34.1 HTML `layers` (asset classes), 34.2 DOT threat tree (subverting the
contract), 34.3 DOT threat tree (subverting the record) — 2 tables, 1 listing, 12 index spans,
1 `Case study — Ledger` callout. The two DOT threat trees required by the task message are 34.2 and
34.3; both carry the mandatory `// fig=34-2` / `// fig=34-3` comment line and a bold caption
paragraph immediately after the fence.

Status badges: 36 inline badge uses (`**[implemented]**`, `**[extension]**`), per the Chapter-16-
onward convention. `**[guidance]**` is not used; every documented-target statement in this chapter is
either an implemented behavior or an architectural extension, and I preferred not to introduce a
badge where the distinction between "documented target" and "extension" would have been mine rather
than the repository's.

## Repository paths I personally read and verified during drafting

1. `nornyx/parser.py` — read the `NornyxSafeLoader` region in full. Sources for Section 34.3's
   duplicate-key branch (rejection at every nesting level via `ConstructorError`, including the
   unhashable-key path) and the type-coercion branch (implicit bool resolvers stripped and re-added
   for `true`/`false` only, with the docstring explaining the `- on: test_failure` bug). The
   chapter's framing of the `on:` fix as "began as a functional bug … but the security shape is
   general" is my gloss on the docstring, not a repository claim.
2. `nornyx/path_security.py` — read in full. Source for Section 34.3's path branch: the URI-scheme
   rejector with its drive-letter exception, the `\\` UNC prefix, the `\??\`, `\Device\`,
   `\GLOBAL??\` NT device prefixes, the Windows device component regex including superscript digits,
   extension and alternate-data-stream suffix handling, and the docstring's own statement that the
   check is "deliberately lexical and host-independent. A Linux runner must reject a Windows UNC or
   device path just as a Windows runner does" — which is the basis for the chapter's
   "host-independence is the interesting decision" sentence.
3. `nornyx/agentic_artifacts.py` — read the forbidden-content region. Listing 34.1 is verbatim
   (`_FORBIDDEN_KEY_SEGMENTS`, `_FORBIDDEN_KEY_PAIRS`, `_KEY_SPLIT_RE`, `_IPV4_RE`), reflowed onto
   fewer lines for print width but with no member added, removed, or renamed. The caption's
   explanation of segment matching ("avoids false positives on reviewed declaration fields such as
   `execution_mode` and `agent_key`") is a close paraphrase of the source comment directly above the
   frozenset.
4. `nornyx/governance/agentic_delegation.py` — read the normalization-collision function. Confirms
   `AN_NORMALIZATION_COLLISION` and the "Identifiers X and Y collide after Unicode normalization"
   message. The specific normalization form (NFKC with case folding) is from fact pack 02 §2.5; I
   read the diagnostic site but not the `_normalized` helper.
5. `docs/agentic-network/08_SECURITY_BOUNDARIES.md` — read in full. This is the closest in-repo
   analogue to Table 34.2 and I used it as a cross-check rather than a template: its twelve threat
   rows and five residual-risk bullets all appear somewhere in this chapter, and the residual-risk
   wording in Sections 34.4 and 34.5 ("bypassing the adapter bypasses the hook"; "the lock binds
   bytes, not producers"; "omission and fabrication are outside Nornyx's proof surface") is drawn
   from it.
6. `.github/workflows/ci.yml`, `adapters/.../coverage.py`, `adapters/.../tests/test_crewai_adapter.py`,
   `examples/crewai_governance_benchmark/README.md`, `docs/agentic-network/11_REFERENCE_CI.md` —
   read for Chapters 14 and 15; they support this chapter's coverage-matrix, adapter-bypass, and
   evidence-pipeline references.

## Claims taken from the fact packs rather than verified by me directly

1. **Lock verification diagnostics** — `AN_LOCK_SOURCE_STALE`, `AN_LOCK_ARTIFACT_MISMATCH`,
   `AN_LOCK_ARTIFACT_UNEXPECTED`, `AN_LOCK_REVISION_MUTABLE`, and the list of fields the lock binds
   — fact pack 02 §4, citing `nornyx/agentic_artifacts.py:685-774,916-1028` and
   `schemas/agentic_network_lock_v1.schema.json`. Also the schema-description sentence that the lock
   "proves reviewed-content binding only" and the "a hostile local writer can regenerate a consistent
   lock" limitation (fact pack 02 §4, `docs/agentic-network/07_NETWORK_LOCK.md`).
2. **Approval engine ordering and codes** — `APPROVAL_REVISION_MISMATCH`, `APPROVAL_ACTION_MISMATCH`,
   `APPROVAL_NON_HUMAN`, `APPROVAL_ROLE_INVALID`, `APPROVAL_STALE` — fact pack 02 §7, citing
   `nornyx/agentic/authz.py:1012-1072`. The four-layer non-human denial (engine, static check,
   evidence, adapter) and the union-back-in behavior of `CORE_DENIED_ACTOR_TYPES` come from fact
   pack 01 §7.2 and fact pack 02 §7 / traceability row 30.
3. **Replay fingerprint and ordering model** — content fingerprint over the event minus transport
   fields, timestamp additionally excluded in explicit occurrence mode, `AN_EVT_REPLAY`,
   `AN_EVT_SEQUENCE_GAP`, `AN_EVT_ATTEMPT_AFTER_SUCCESS` — fact pack 02 §5.2, citing
   `nornyx/agentic_evidence.py:391-419,800-1060`. The quoted justification ("A producer cannot evade
   exact replay detection merely by restamping a duplicate with a new timestamp") is a source
   comment reproduced in fact pack 02; I attributed it to "the source comment" and paraphrased.
4. **The validator's embedded limitations** ("validated evidence proves conformance of supplied
   records only"; "hash validity proves content binding, not event truth") — fact pack 02 §5.2,
   `nornyx/agentic_evidence.py:88-92`.
5. **Package scanner detector families and behaviors** — file inventory with hashes, secret
   pattern families plus credential-named files, hook path/content detection, MCP server detection
   with broad-path severity escalation, endpoint classification, **twenty-three** dangerous-command
   patterns, lifecycle-script detection, six claim-versus-evidence checks, `sanitize_excerpt`
   redaction to `REDACTED_SECRET_LIKE_VALUE` with `raw_secret_stored: false`, exactly two import-only
   evidence adapters (syft, gitleaks), and the declared non-goal "Does not claim that a package is
   safe" with the permitted-claim sentence — all from fact pack 04 §§1.3, 1.4, 1.6, 1.8, citing
   `nornyx/package_scanner.py` and `docs/governed-package-profile.md`. The count "twenty-three" was
   independently confirmed during drafting: `len(nornyx.package_scanner.DANGEROUS_COMMAND_PATTERNS)`
   returns 23 (read-only import, no side effects).
6. **Symlink containment in the governance loader** ("an explicit trust_root can narrow containment
   but cannot hide a higher ancestor") — fact pack 01 §8, citing
   `docs/GOVERNANCE_CLI_AND_API.md:31-36`.
7. **Closed block schemas (`additionalProperties: false`) across the agentic-network schema set** —
   fact pack 02 §§2.1–2.4.
8. **"No cross-repository policy reference" as a deliberate non-goal made to preserve face-auditable
   contracts** — fact pack 04 §2.4, citing `docs/CASE_STUDY_multi_repo_governance.md:58-61`.
9. **ADR-0040's deliberate avoidance of the word "guarantee"** — fact pack 04 §10(d). Paraphrased,
   and attributed to "the repository's own decision record" without an ADR number, because fact
   pack 04 §12(1) warns that ADR numbers collide across two directories.
10. **"Identity resolution is binding, not authentication"** — fact pack 03 §7, citing the
    benchmark's `REVIEWER_QUICKSTART.md:313-323`. Quoted as a short phrase and attributed to "the
    benchmark's reviewer documentation".

## Claims I could NOT verify, and what I wrote instead

1. **The number of detector families in the package scanner.** Fact pack 04 §1.3 enumerates nine
   numbered items but describes six finding *buckets* in `scan_package` plus claim-vs-evidence. I
   originally wrote "seven detector families" in Table 34.2, then changed it to "the declared finding
   categories" because the count would have been mine rather than the repository's.
2. *(Resolved during drafting.)* The twenty-three dangerous-command pattern count was the one
   numeric claim I initially took on trust; it is now confirmed directly against
   `nornyx.package_scanner.DANGEROUS_COMMAND_PATTERNS` (length 23).
3. **Whether the repository has a claim register in the sense Section 34.1 uses.** It does not, as a
   named artifact. The claim register is presented throughout as a discipline the reader adopts
   (Chapters 39–40 build one), never as a Nornyx feature, and it carries no badge.
4. **Whether any coverage-inventory-widening attack has occurred.** No source. Section 34.1's
   argument is analytic ("no code change and no test failure") and is supported only by the existence
   of a test that checks the inventory never claims unnamed surfaces (fact pack 03 §4).
5. **The evidence-producer co-location finding in the Ledger case study** (audit-recorder and
   executor in one process group). Entirely fictional, inside the Northstar universe. It is
   consistent with the bible's Thread C roster (`audit-recorder` is evidence-only, `executor` cannot
   submit) and with the bible's stated Thread C bypass scene (executor calling a bank API directly,
   motivating the gateway extension). No repository claim is attached to either finding.
6. **The overclaim harm path in Section 34.7.** Fictional and internal to the case study. The
   general mechanism (an inflated claim causing a control project to be descoped) is an argument,
   not a reported incident, and the text does not present it as one.
7. **Any assertion that the described mitigations satisfy a standard or regulation.** None is made.
   `nist-scrm`, `owasp-llm`, and `owasp-agentic` are cited as catalogues and frameworks; Chapter 35
   owns the mappings, and no sentence here implies certification, compliance, or legal sufficiency.
8. **Independent-observer / Tier 3 architectures.** Consistently badged `**[extension]**` in
   Sections 34.2, 34.4, 34.5 and Table 34.2. No repository capability is implied.

## PROPOSED-REF

None. Further-reading keys used: `owasp-agentic`, `owasp-llm`, `nist-scrm`, `greshake-injection`,
`in-toto`. Inline citations: `nist-scrm` (twice), `owasp-agentic`, `greshake-injection`,
`owasp-llm`. All from `05_bibliography.md`. The task message's four required keys
(`owasp-llm`, `owasp-agentic`, `nist-scrm`, `greshake-injection`) all appear inline as well as in
Further reading.

Note: the Further-reading section originally listed six entries, one over the style guide's 2–5
range; `nist-ai-rmf` was removed to comply. If the editor prefers the risk-framework pointer to
survive, drop `in-toto` instead and reinstate `nist-ai-rmf`.

## Continuity and cross-reference checks

- Thread C (Ledger) advanced per the bible: the chapter runs a threat workshop over the four Treasury
  agents, uses the canonical zone name `payment-exec` and the canonical identity names `executor`
  and `audit-recorder`, and reopens the gateway extension that Chapter 31's bypass-risk analysis
  motivates. It does not resolve the extension.
- Forward/backward references: Chapters 6, 9, 12, 13, 14, 15, 27 (prerequisites and recaps), 31
  (Ledger bypass risk), 33 (incident reconstruction), 35 (standards mapping, explicitly deferred to),
  39–40 (claim register). Each is a clause, not a re-teach.
- Terminology: "evidence" never "proof" for supplied records; "cooperative enforcement" and
  "independent (mandatory) enforcement" used per the canonical list; "residual risk" and "claim
  register" used consistently.
- DOT node styling follows `04_visual_language.md`: `style=dashed` for attack steps and residual-risk
  leaves, `peripheries=2` for the tree root and for the three residual-risk nodes (marking them as
  authoritative statements of limitation). No colors or fonts are set.

## Editorial flags

- Figure 34.3 is wide (three sub-trees, twelve leaves, twelve mitigation/residual nodes). If it does
  not render legibly at page width, the clean split is into two figures — approvals as one, locks
  plus replay as the other — which would take the chapter to four figures, still inside the range.
- Section 34.7 is an argument rather than a report, and it is the section most likely to attract
  review pushback ("overclaiming is not a vulnerability"). The four-step harm path is deliberately
  concrete so the claim can be attacked on its mechanics rather than on its framing. I would not
  soften it, but a reviewer disagreement should be resolved before Part VII is finalized, since
  Chapter 38 and the capstone both build on this framing.
