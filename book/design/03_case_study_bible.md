# Case-Study Bible — Northstar Services (binding continuity reference)

All threads live inside one fictional enterprise so that policies, identities, and evidence can
compose in the capstone. Nothing here is drawn from a real organization. Where a thread uses
Nornyx, the artifacts must follow the real language/schema facts in `book/factpack/`; where a
thread needs machinery Nornyx does not provide (external gateways, IdP, hierarchy engine), the
text labels it [extension] and implements the *pattern*, not a fake Nornyx feature.

## The enterprise

**Northstar Services** — a mid-size financial-services and software company (≈4,000 staff;
regulated in the EU and US). Divisions: Customer Operations, Treasury, Engineering Platform,
Research & Insights, Risk & Audit. CTO sponsors an "AI delivery" program; the Risk & Audit chief
requires demonstrable controls before production use. Northstar's engineering conventions:
GitHub-style repos, CI on every PR, immutable release tags, central IdP for humans, a workspace
governance repo `northstar-governance` holding org policy.

## Thread A — "Atlas": controlled research assistant (commissioning case study 1)

Single agent in Research & Insights. May: search an approved source allowlist, retrieve and
summarize documents, file summaries to an internal store. May not: publish externally, purchase,
disclose confidential data, invoke unapproved tools. Canonical artifacts:
- Identity: namespace `northstar.research`, subject `atlas`, framework binding to a CrewAI tool
  wrapper. Capabilities: `research.search_approved`, `research.summarize`,
  `research.file_internal` (low risk, no gate); denied surface: `publish_external`,
  `purchase.*`, any tool not declared.
- Trust zones: `research-internal` (home), `public-web` (untrusted source zone, ingress-only
  content, never-share: `customer_data`, `credentials`, `strategy_docs`).
- Signature scenes: a denial (Atlas asked to post a summary to a public blog → deny, evidence
  recorded); an approval (one-off request to share a summary with a partner → human approval with
  revision binding); an audit review reconstructing the partner-share decision.

## Thread B — "Forge": enterprise software-development agent (case study 2)

Engineering Platform's AI development system on repo `northstar/payments-api`. May: read the
repository, propose changes on branches, run tests, open pull requests. Requires human approval
(named roles, maker–checker: proposer can never approve): merge to protected branches, production
deployment, release publication, secrets access, destructive changes (schema drops, force-push,
data deletion), security-sensitive paths (`auth/`, `crypto/`, CI workflows). Fail-closed: if the
policy artifacts drift or the lock fails verification, CI blocks the merge lane entirely.
Canonical artifacts: a `.nyx` delivery contract patterned on
`examples/governed_delivery_control_plane.nyx`; generated `AGENTS.md`/`policy.yaml`; drift gate in
CI; approval records bound to commit SHAs. Signature scenes: a compliant PR that merges; a
blocked self-approval; a stale approval invalidated by a force-pushed revision; a bypass attempt
committing directly to a generated artifact caught by `nornyx drift`.

## Thread C — "Ledger": multi-agent financial workflow (case study 3)

Treasury's payment-exception handling. Agents: `planner` (decomposes cases), `analyst` (computes
exposure; read-only data zone), `executor` (drafts payment adjustments; cannot submit),
`approval-liaison` (assembles approval packages; cannot decide), plus human treasury officer
(approver) and `audit-recorder` (evidence only). Zones: `treasury-plan`, `treasury-data`
(never-share: `account_credentials`, `full_pan`), `payment-exec` (gate on ingress),
`audit-store` (append-only). Delegation: planner may delegate bounded `analyze.exposure` to
analyst (depth 1, expiry); handoff of a case to executor transfers work, never authority.
Separation of duties: no identity holds both `payment.draft` and `payment.approve`; approval
escalates by amount tier. Signature scenes: delegation-depth violation denied; an
approval-escalation above €50k; an evidence chain from plan to executed adjustment; bypass risk
analysis (executor calling a bank API directly — outside cooperative coverage → motivates
gateway [extension]).

## Thread D — "Gateway": framework integration comparison (case study 4)

Engineering Platform evaluates governance of the same logical workflow (a support-refund tool
call) across paths: (1) framework-native ungoverned; (2) wrapped cooperative path — CrewAI
`BaseTool._run` wrapper and LangGraph sync `StateGraph` node wrapper [implemented; use real
adapter APIs and the repo's A/B benchmark evidence]; (3) bypass path — direct call under the
wrapper, demonstrating the cooperative boundary; (4) stronger external enforcement — same
contract projected to a mandatory gateway PEP [extension/guidance]. Decision table compares
coverage, evidence, failure behavior, and the assurance tier each path supports.

## Thread E — "Charter": enterprise governance hierarchy (case study 5)

Northstar's policy stack: org charter policy (Risk & Audit) → business-unit policies (Treasury,
Engineering) → application policies (payments-api, support network) → agent policies (Atlas,
Forge, Ledger agents) → mission-specific restrictions (a single engagement's extra constraints).
Composition rule under study: a lower layer may narrow but never widen a superior control, and
weakening must be *visible* (explicit exception with owner and expiry), never silent. What Nornyx
implements today: policy `ref` to a canonical workspace source, `nornyx workspace-check` across
repos, profile/module composition with provenance [implemented — per fact packs]. The full
five-level inheritance engine with conflict reporting is presented as [extension] with a worked
design. Signature scenes: a BU policy that tries to drop `deny secrets_to_llm` and how the
workspace check + review surface it; a mission waiver done properly (bounded exception with
expiry and approver).

## Continuity rules

- Names, capability strings, zone names, and amounts above are canonical; do not vary them.
- Currency: EUR. Times: UTC ISO-8601. Example SHAs: use `9f3c...` style shortened forms
  consistently (`9f3c1a7` for the Forge stale-approval scene).
- Each thread appears in its assigned chapters (see book design §case-study strategy); a chapter
  touching a thread uses a `> **Case study — <Thread>.**` callout and advances the thread rather
  than re-introducing it (one-sentence recap allowed).
- Capstone (Part VIII) composes all five; do not resolve Thread E's [extension] machinery as if
  it shipped.

## Post-editorial canonical identifiers (binding for future editions)

Decided during the final editorial passes; each identifier is unique to one scene:
- `9f3c1a7` — Forge stale-approval scene ONLY (Thread B).
- `4e7d21a` (full `4e7d21ad0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b`) — Atlas contract revision (ch11, ch36).
- `b5e91c4…` — capstone Ledger subject revision (ch39–41).
- `task-3c88a1e` — the LangGraph task identifier in ch24.
- `3b7a9d1…deadbeef` — Appendix E Ledger fragment revision.
- `git:feedfacefeed…` — support-network revision (ch09, ch12, ch13, ch35).
- Thread C network id: `network.treasury_exceptions` everywhere.
- Atlas approval name: `partner_disclosure_approval`. Ledger submission capability: `payment.submit`.
- Above €50,000 Ledger requires treasury officer AND risk officer; the capstone demonstration
  records a single `network_governance_owner` assertion and carries the dual-control gap as a
  register residual (ch40 states this explicitly).
