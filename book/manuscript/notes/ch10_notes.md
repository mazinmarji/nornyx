# Chapter 10 — Author notes

Chapter: "Enforcement Models and Fail-Closed Design" (Part II).

## Repository paths personally verified (read directly, not only via fact packs)

- `/home/user/nornyx/adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/enforcement.py`
  — the whole file. Listing 10.2 is the real `enforce()` body with the docstring elided; the two
  quoted phrases ("the one place a wrapped adapter action is ever invoked"; "any unexpected
  internal error propagates … before `action` is reached, so it also fails closed") are verbatim
  from its module docstring and function docstring. Also verified that `on_decision` runs after
  recording and before any branch, on DENY as well as ALLOW.
- `/home/user/nornyx/adapters/nornyx-agentic-adapters/docs/COMPATIBILITY.md` (line 72) — "changing
  `enforce()`'s evaluate → record → execute ordering guarantee" listed as a breaking change.
- `/home/user/nornyx/adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`
  (lines ~118–183) — the coverage inventory: six declared surfaces, exactly one
  (`tool_invocation`) `WRAPPED`, the other five `UNSUPPORTED` including `async_tool_invocation`.
- `/home/user/nornyx/nornyx/agentic/authz.py` — `load_authorizer` (lines ~1166–1210) and its
  docstring: the four-code fail-closed load taxonomy `CONTRACT_INVALID` / `PROFILE_MISSING` /
  `LOCK_INVALID` / `LOCK_STALE`, and the fact that no partially-initialized `Authorizer` is
  returned on any failure path.

Fact-pack-sourced claims used without independent re-reading: the bypass sentence from the adapter
README ("Bypassing the adapter — calling the underlying action directly instead of through the
governed tool — bypasses enforcement entirely") and the existence of the corresponding bypass test
`test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely` — both in fact pack 03
§2.3. The chapter quotes the sentence and refers to "a test that exercises exactly that bypass"
without naming the test.

## Claims I could NOT verify, and what I wrote instead

1. **Nornyx gateway / mesh / sandbox behavior.** The repository implements no gateway, proxy,
   sandbox, IAM, or mesh enforcement point. Sections 10.2–10.3 therefore describe these as general
   architectural models sourced from the bibliography ([@envoy], [@istio], [@nist-zta],
   [@beyondcorp], [@xacml], [@rfc2904]), with no Nornyx attribution anywhere in the comparison
   table. The only Nornyx-attributed row-behavior is the in-process cooperative wrapper.
2. **Bounded fallback configuration (Listing 10.1).** No such schema or feature exists in the
   repository. The listing is captioned "Illustrative — not drawn from the repository" and its
   field names are invented for teaching, not presented as an API. `PT15M` uses ISO-8601 duration
   form for consistency with the real `expires_after: PT24H` in `module_human_approval.yaml`, but
   the surrounding structure is not a Nornyx artifact.
3. **Fail-open incident narrative (Section 10.4).** The forty-minute outage and its consequences
   are a constructed Northstar scenario, not a recorded event; it is written in the case-study
   voice and makes no repository claim.
4. **Assurance tiers.** Tier vocabulary is deliberately avoided as a claim mechanism here (tiers
   are Chapter 13). The chapter refers forward rather than asserting a tier for any model.
5. **Telecom analogy.** The IMS control-plane/media-plane separation is cited to [@3gpp-ims] and
   [@gsma-volte] at the level of architectural fact (signaling and media travel separate paths;
   media-plane elements are deployed when media control is required). No specific interface,
   node name, or standards clause is quoted, since I did not consult the specifications directly.
   The three stated limits of the analogy are the author's, marked as such in the prose.
6. **Chapter cross-references.** Forward references to Chapters 11, 13, 14, 20, and 36 follow
   `01_book_design.md`; backward references to Chapters 3, 4, 7, and 9 assume the material those
   chapters are assigned. Only Chapters 1, 8, 9, and 10 exist in the manuscript at this time.

## PROPOSED-REF additions

None. All citations ([@xacml], [@rfc2904], [@envoy], [@istio], [@nist-zta], [@beyondcorp],
[@schneider-enforceable], [@saltzer-schroeder], [@parnas-criteria], [@sre-book], [@opa],
[@cedar], [@3gpp-ims], [@gsma-volte]) are existing keys in `05_bibliography.md`.

## Continuity decisions

- Thread A (Atlas) receives its first denial scene at the conceptual level, using the canonical
  capability strings from the case bible (`research.search_approved`, `research.summarize`,
  `research.file_internal`) and the canonical namespace `northstar.research`. The scene
  deliberately ends by *limiting* the claim (the wrapper covers the wrapped publishing tool, not
  a raw HTTP client), which sets up the Thread D bypass work in Chapters 22–25 and the gateway
  extension material in Chapter 26.
- This is the second of the five sanctioned uses of the telecom analogy (Chapters 2, 10, 26, 32,
  37), and it states where it breaks, per the style guide.
- No inline status badges (Chapter 10 precedes Chapter 16); Nornyx status is prose-only.
