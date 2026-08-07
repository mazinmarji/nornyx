# Chapter 19 notes — "The Authorization Interface"

## Status

Draft complete. Raw word count 5,525 (whole body including fenced listings, tables, captions, and
end matter); 5,130 excluding fenced blocks and HTML figures. The raw figure sits 25 words above the
3,800–5,500 band after four trimming passes; the prose figure is comfortably inside it, and the
excess is carried by the four verbatim code/output listings the assignment required. For comparison,
`ch11_runtime_evidence.md` measures 5,529 raw by the same script. If a hard raw cap applies, the
cheapest further cut is Listing 19.1's Python (≈90 words), whose behavior is fully described by the
surrounding prose and its caption. Structure: 1 figure (19.1, HTML `seq`),
2 tables, 4 listings, 18 index spans. Callouts used: Opening scenario, Learning objectives,
Prerequisites, Key idea, Nornyx in practice, Misconception (×2), Assurance boundary, Design
checkpoint. No case-study callout: the book design assigns no thread to Chapter 19, and the
compatibility-shim study is presented as a section rather than as a thread scene so as not to
claim a thread another chapter owns.

Inline status badges are used per the Chapter-16-onward rule: **[implemented]** throughout, and
**[implemented but unpackaged]** for the M2-D shim in Section 19.7.

## Everything I verified directly against the repository

All paths relative to `/home/user/nornyx`. Every one of these was read (or executed), not taken
from the fact packs alone.

- `nornyx/agentic/authz.py` — read in full in four passes. Specifically confirmed:
  `SPI_VERSION = "1.2"` (line 66); `DecisionEffect` exactly three members (399–402);
  `AuthorizerLoadCode` exactly four members (405–409); `IdentityResolutionCode` two members;
  `DecisionCode` 23 members (417–440); the six request dataclasses and the `AuthorizationRequest`
  union (509–555); `ApprovalAssertion` field list including `issued_at`/`expires_at`/`evidence_refs`
  (495–506); `PHASE_INTENT` 10 members and `PHASE_OBSERVATION` 8 members (585–610);
  `AuthorizerState` frozen slots dataclass with `document`/`composition`/`lock_payload` properties
  and the assurance-scope docstring (641–711); `Authorizer.state` property docstring (773–785);
  `_shape_ok` (867–892); `evaluate` including the `REQUEST_MALFORMED` and `REVISION_MISMATCH`
  paths (895–919); `_capability` basis selection membership-vs-delegation (937–962);
  `_approval` check order (1012–1072); `_zone_crossing` `APPROVAL_REQUIRED` construction
  (1101–1118); `load_authorizer` stage-to-code mapping (1166–1210).
- `nornyx/agentic/__init__.py` — the full `__all__` export list (lines 75–124), used to confirm
  every name quoted in the chapter is a public export.
- `docs/agentic-network/12_AUTHORIZATION_SPI.md` — read in full; all three quoted sentences
  ("does not itself read, validate, compose, or verify files"; "performs no file read, governance
  composition, lock verification, network access, or framework import"; "changing or deleting the
  source files after `load_authorizer` returns cannot change the state") verified verbatim.
- `integrations/nornyx_reference_adapters/governance_kernel.py` — module docstring lines 1–27 read
  in full; the four quoted fragments ("a deprecated compatibility facade over the supported Nornyx
  agentic SPI"; the single-source-of-authority paragraph; "**non-authoritative read-only
  projections**"; "it ships in neither the core wheel nor `nornyx-agentic-adapters`") verified
  verbatim.
- `examples/agentic_network_support/support_network.nyx` — identities, capabilities, memberships,
  trust zones, and the `agentic_network_authority` approval declaration read directly to pick real
  identifiers for the worked examples.
- `README.md`, `docs/GOVERNANCE_CLI_AND_API.md` (exit-code table and diagnostic namespaces) —
  read for the claim-boundary framing in Section 19.7's design checkpoint.

## Everything I executed (all under /tmp, read-only with respect to the repository)

Working directory `/tmp/nyxwork/ch19`, with the support contract and its `governance_evidence/`
directory copied in.

1. `nornyx agentic-network generate support_network.nyx --as-of 2026-07-17T00:00:00Z --json`
   → `"artifact_count": 10` with the ten expected names.
2. `nornyx agentic-network lock support_network.nyx --as-of 2026-07-17T00:00:00Z --json`
   → `lock_digest sha256:fe71adc9e8641330f5c08e7871feab33842db31efd292aca2186e4baefce7a30`.
3. `authorize_demo.py` — Listings 19.2 and 19.3. **The output quoted in Listing 19.3 is verbatim
   observed output**, reflowed only to wrap the long denial reason across two lines.
   `contract_digest` `sha256:3cdf632c…d0ac8eda` matches the value recorded in fact pack 02 §11 for
   the same contract, which is a useful independent cross-check.
4. `state_demo.py` — the Listing 19.1 experiment. Observed: `state is stable: True`,
   `view is detached: True`, `view type: dict`, mutation of the view visible in the view,
   `decision unchanged: deny CAPABILITY_DENIED`, `fresh view clean: True`. The same script produced
   the zone-crossing result quoted in Section 19.5: effect `approval_required`, code
   `CROSSING_APPROVAL_REQUIRED`, reason "External trust-zone crossings require a human approval.",
   with a single `approval_requested` intent naming `agentic_network_authority`.
5. `approval_demo.py` — Listing 19.4. Seven variations run; output quoted verbatim, reflowed for
   column width. Also confirmed that a bare `Authorizer(...)` can be constructed from
   `a.state.document` / `.composition` / `.lock_payload` and yields identical digests, which is the
   concrete demonstration of Section 19.3's point.
6. `load_authorizer(..., validation_as_of="not-a-timestamp")` → `AuthorizerLoadError` with code
   `CONTRACT_INVALID` (see caveat 2 below).

## Claims I could NOT verify, and what I wrote instead

1. **The approval-engine ordering table row 0.** I list "the approval reference is a declared
   requirement → `REQUEST_MALFORMED`" as step 0 of Table 19.2. I read this at `authz.py:1019–1021`
   but did not exercise it, because every approval reference in the bundled contract is declared.
   The row is presented as part of the code-read ordering, not as observed output.
2. **The load taxonomy is exercised for one code only.** I observed `CONTRACT_INVALID` (via a
   malformed `validation_as_of`, which fails inside governance evaluation and is mapped there).
   `PROFILE_MISSING`, `LOCK_INVALID`, and `LOCK_STALE` are stated from the code and the docstring at
   `authz.py:1166–1210`, not from execution. Exercise 1 of the chapter asks the reader to produce
   `LOCK_STALE` themselves, which is deliberate — I did not want to assert an observed code I had
   not observed.
3. **"Twenty-two stable legacy `AN_ADAPTER_*` codes."** Taken from fact pack 02 §6.6, which reports
   a grep across `integrations/nornyx_reference_adapters/*.py`. I read the shim's docstring and the
   packaging exclusion myself but did not re-run the grep, so the *count* is fact-pack-sourced. The
   chapter states the number in a sentence that would remain true at 21 or 23 ("translates … into
   twenty-two stable legacy `AN_ADAPTER_*` strings"), so a later re-count would be a one-word fix.
4. **The published adapter distribution's `nornyx>=1.10,<2` floor.** Taken from fact packs 02 §6.6
   and 03 §8.2 (citing `adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md:10–16`). I did not
   open the adapter distribution's own metadata. Stated as a comparison, not as a version claim
   about the core package.
5. **"Compiled against it" for adapters and enterprise integrations (Section 19.2).** This is a
   general software-engineering statement about interface consumers, not a repository claim; no
   Nornyx-specific enterprise integrations are asserted to exist.
6. **The opening scenario's eleven-minute window** is fictional narrative in the Northstar universe,
   as are the three code paths. The *mechanism* it illustrates (three consumers each running the
   full interpretive pipeline) is the real motivation recorded for SPI 1.2 in the shim's docstring.

## Deliberate framing choices worth an editor's eye

- I describe the M2-D shim as "merged at the repository's current head" and label it
  **[implemented but unpackaged]** rather than assigning it to release 1.11.0. Fact pack 02 §13
  item 4 is explicit that it sits under `CHANGELOG.md` `[Unreleased]` and that package version
  1.11.0 predates it. The Section 19.7 design checkpoint makes this distinction the teaching point
  rather than a footnote.
- Section 19.6's transcript orders the seven variations by *field varied*, not by the engine's
  check order, so the reader can see that varying a later-checked field still produces the
  earlier-checked code where both fail. I considered ordering them to match Table 19.2 and decided
  the current arrangement teaches the ordering better.
- The `expired` row's explanation says "the composed requirement here carries a relative expiry of
  seven days." I confirmed this by inspecting the composed `approval_requirements` directly:
  `agentic_network_authority` resolves to `expires_after='P7D'`, `expires_at=None`. This resolves
  fact pack 02 §13 item 2's flagged ambiguity in favour of the documentation — the *composed*
  requirement does use `P7D`, even though the contract file declares an absolute `expires_at`.

## PROPOSED-REF additions

None. All five further-reading keys (`parnas-criteria`, `rfc2904`, `xacml`, `miller-ocap`,
`nornyx-repo`) and both inline citation groups are drawn from `05_bibliography.md`.
