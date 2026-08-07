# Chapter 16 — Author notes

Snapshot basis: `/home/user/nornyx` at git HEAD `70d2b40ad79293209b43bdaa375f20badf63bdd7`,
distribution 1.11.0. `nornyx` CLI verified runnable (`nornyx --version` → `nornyx 1.11.0`).

## Claims I could NOT fully verify (and what I wrote instead)

1. **First publication to the Python Package Index.** `CHANGELOG.md` is internally inconsistent:
   the `[1.6.1]` entry says "The `v1.6.0` GitHub release predates this fix and was never published
   to PyPI; PyPI publication first occurs at 1.6.1", while the `[1.6.2]` entry says "The `v1.6.1`
   GitHub release predates this fix and was never published to PyPI; PyPI publication first occurs
   at 1.6.2." I followed the later (corrective) statement and the fact pack, writing that the first
   publication occurred at 1.6.2 and that 1.6.0 and 1.6.1 were never published. I avoided asserting
   anything about the *current* state of the public index, which cannot be verified from the
   repository (`manifest.json` records `package_publication: 1.10.0` while the changelog dates
   1.11.0 to 2026-08-01 with tagging and publication "performed separately").

2. **Whether the independent audit was performed by a party external to the project.** The
   changelog says "The independent audit of candidate `35ee6935…` returned `NO-GO`" and names the
   findings AUD-001…AUD-022, but does not identify the reviewer or state their organizational
   relationship. I wrote "an independent audit … returned NO-GO" (the repository's own wording) and
   deliberately framed Section 16.6's lesson as being about the *disclosure practice* and about
   what the reader should ask a supplier, not about the auditor's independence, which I cannot
   attest. The text explicitly states that none of this makes the software correct.

3. **Test counts.** I did not run the test suite and made no claim about numbers of passing tests.
   The chapter's badge definition says **[implemented]** means "code with tests in the repository",
   which is supported by the fact packs' per-behaviour test map, not by an execution I performed.

4. **`x-nornyx-safety-boundary` and non-goal enforcement.** I asserted that MCP/A2A protocol
   targets pin `execution_mode`/`live_connector_execution` as schema constants; this is verified
   (see verified paths below). I did **not** assert that the full non-goal list is structurally
   enforced — most of it is documentation — and the text says only that "several are enforced
   structurally … rather than by convention."

## PROPOSED-REF additions

None. All citations used (`c4model`, `nornyx-repo`, `opa`, `cedar`, `istio`, `envoy`,
`nist-ssdf`, `slsa`) are existing keys in `05_bibliography.md`.

## Repository paths I personally read or executed against

Read:
- `README.md` (positioning, non-goals, scope-and-safety paragraph, provisional-brand sentence)
- `pyproject.toml` (version 1.11.0, MIT licence, `requires-python >=3.10`, dependency list)
- `nornyx/__init__.py` (`__version__ = "1.11.0"`)
- `manifest.json` (version, `language_version: "1.0.0"`, safety boundaries, publication field)
- `LICENSE` (MIT, "Copyright (c) 2026 Mazin Marji and Nornyx Contributors")
- `docs/VERSIONING.md` (the full version-axes table used in Table 16.1; the seven synchronized
  locations; the schema-`$id`-permanence and lock-selects-events-version rules)
- `docs/48_NORNYX_POSITIONING.md` (the verbatim non-goals list)
- `docs/02_ARCHITECTURE.md` (processing path; the "names may include `runtime` … but they do not
  turn Nornyx into an autonomous execution engine" sentence)
- `docs/13_RISK_REGISTER.md` line 15 (name legal conflict / Medium / trademark clearance)
- `docs/agentic-network/00_OVERVIEW.md` (the "not a runtime control plane …" non-goal list and the
  "Honest limits" section)
- `schemas/nornyx_v1_0.schema.json` lines 1–35 (`x-nornyx-version-note`, `x-nornyx-safety-boundary`,
  `additionalProperties: false`, the `nornyx` const set `0.1`/`0.2`)
- `schemas/agentic_network_v1.schema.json` (protocol-target `execution_mode` /
  `live_connector_execution` constants — read via the fact pack's line citations and confirmed by
  the closed-schema behaviour observed in Ch. 18's runs)
- `CHANGELOG.md` — release-heading index and the `[1.0.0]`, `[1.6.0]`, `[1.6.1]`, `[1.6.2]` entries
  in full
- `nornyx/checker.py` lines 1–70 (top-level block sets used for the Ch. 17 cross-reference)

Executed (outputs to `/tmp/nyxbook`):
- `nornyx --version` → `nornyx 1.11.0`
- `nornyx check examples/governed_delivery_control_plane.nyx` → passed, exit 0
- `nornyx check` on a copy with `nornyx: "1.0"` → `UNKNOWN_VERSION` **warning**, exit 0
  (this is Listing 16.1, quoted verbatim)
- `nornyx schema --version 1.0`
- `python3 -c "import nornyx.agentic as a; print(a.SPI_VERSION)"` → `1.2`

## Editorial notes

- The status-badge box is a `> **Key idea.**` callout (an approved label); the style guide has no
  dedicated "badge" callout label, so I did not invent one.
- Figure 16.1 uses `peripheries=2` for Nornyx and the approver (authoritative) and `style=dashed`
  for the framework, model provider, and deployment systems (out of coverage), per the visual
  language. Figure 16.3 uses the `arr deny` modifier for the no-go point.
- Thread D is nominally introduced in Ch. 22–25 per the case bible; the Ch. 16 scene is written as
  a *precursor* (a claim-register entry, not the framework comparison) and recaps the thread in one
  sentence rather than re-introducing it.
