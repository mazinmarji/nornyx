# Chapter 37 — Author notes

Chapter: "Enterprise Adoption and Platform Strategy" (Part VII). Telecom analogy #5.
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **All Northstar numbers are fiction** (nineteen-day latency, forty-one repositories,
   one engineer-week authoring load, ten-second median approval time). They appear only
   in scenario/case-study/friction prose, never as claims about the toolchain. The
   authoring-load figure is introduced as "Northstar's observed load" to keep it inside
   the fiction.
2. **Maturity ladder (Table 37.1)** is my synthesis; no repository maturity model exists.
   Stage capabilities are tied to real machinery with badges: checker/drift/lock/
   approvals/workspace-check **[implemented]**; hierarchy engine and Tier 3 bindings
   **[extension]**, consistent with Thread E's bible entry and ADR-0040.
3. **Telecom history** (profiles cutting option space, conformance regimes,
   circuit-switched fallback, staged migration) is written at the level of the cited
   sources [@3gpp-ims; @gsma-volte] from general knowledge; no dates, release numbers, or
   operator names are asserted. The "roughly a decade" duration is hedged. The economic
   contrast (interconnection revenue vs. unquantified governance return) is my argument,
   flagged as the analogy's limit per the style guide's requirement that each use states
   where it stops.
4. **Hyperscaler capabilities** (workload identity, egress control, org-policy layers,
   admission controllers) are described generically without naming any provider or
   product, sourced to [@nist-zta; @beyondcorp; @opa; @cedar; @istio; @envoy]. No claim
   that Nornyx integrates with any of them (projection layer is **[extension]**).
5. **"Editor diagnostics and local drift checks before the pipeline"** — grounded in the
   real CLI surface (`lsp-diagnostics`, `complete`, `symbols`, `drift`; fact pack 01 §5).
   I did not claim any specific editor integration exists beyond the CLI commands.
6. **Multi-tenancy sentence** — "its multi-tenancy is 'one contract, one lock, one
   evidence directory'" is my characterization of the absence of tenancy machinery
   (fact packs show none); phrased as what ships, with isolation architecture badged
   **[extension]**.

## Repository facts relied on (with sources)

- Exact pins `crewai==1.15.4`, `langgraph==1.2.2`; "intentionally narrow: they name the
  only version of each framework this package has been tested against" —
  `adapters/nornyx-agentic-adapters/pyproject.toml:26-28`, `README.md:177-180` (fact
  pack 03 §1.1). Used for the pinned-version cost-ledger line.
- Adapter distribution 0.2.0, Development Status Alpha (fact pack 03).
- Approvals as expiring, revision-bound records **[implemented]** (fact packs 01 §7,
  02 §7).
- Workspace manifest / `workspace-check` for the pilot-repository exit criterion (fact
  pack 04 §2).
- Deterministic generation → trustworthy artifact diffs (fact pack 01 §4.1).
- ADR-0040's per-surface tier scoping → ladder scored per workflow.

## PROPOSED-REF additions

None.

## Repository paths I personally verified (read directly)

- `docs/decisions/ADR-0040-governance-assurance-tiers.md` (full read — the "prohibited
  claims" per tier informed the "claim not yet permitted" column).
- `docs/USE_IN_YOUR_REPO.md` (adoption flow, drift gate, workspace manifest).
- `docs/13_RISK_REGISTER.md` (adoption-friction row exists in the project's own register).
- Fact-pack cross-checks for the adapter pins and Alpha classifier (not re-opened
  `adapters/…/pyproject.toml` myself; fact pack 03 cites lines 6–28).

## Deliberate scope decisions

- Six numbered sections; procurement kept as a numbered-list section because the eight
  questions are genuinely enumerable (style guide allows lists for enumerable items).
- Thread E case-study callout *closes* the thread's Part VII arc (two platform bindings
  chosen by consequence) without resolving the [extension] hierarchy engine as shipped,
  per the bible's continuity rule.
- The Assurance boundary box turns the eight questions on the adoption program itself —
  the chapter's instruments are honestly labeled a Tier 1-ish cooperative control.
- Build/buy/platform is decided per Figure 16.2 layer rather than re-drawing a new
  figure; Figure 37.1 is the chapter's platform-responsibility figure per the brief.
- Raw word count ~5.6k includes the ladder table, one listing, and two figures; prose-only count is within the 3,800-5,500 window.
