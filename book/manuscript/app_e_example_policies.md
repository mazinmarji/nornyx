---
appendix: E
title: "Appendix E — Example Policy Collection"
---

# Appendix E — Example Policy Collection

This appendix collects eleven complete contracts and manifests, each with a short account of what
it demonstrates and what it deliberately does not. Seven are bundled with the repository at the
audited revision `70d2b40ad792` and are cited by path; four are illustrative contracts written for
this book's Northstar Services case studies.

Every illustrative example was run through `nornyx check` in a temporary directory during
preparation, and the result — including the failures — is reported below. Where an example fails,
that is the teaching point, not an oversight.

A note on how to read these. The bundled examples show what the language does today; the
illustrative ones show how the book's threads would be expressed in it. Neither shows enforcement.
A passing contract is a Tier 1 statement about declarations, and Chapter 13 explains exactly how
far that reaches.

## E.1 The governed delivery control plane (bundled)

**Path:** `examples/governed_delivery_control_plane.nyx` — checked, exit 0.

This is the flagship contract, and the one the repository's own continuous integration validates on
every run. It exercises the full core: a constitution of five principles, an intent with success
criteria, one context with authority ranking and explicit taint, three skills, one policy of five
rules, four agents, one harness with a bounded repair loop and three gates, a trace declaration, an
eval, an evidence contract of seven artifacts, an approval, a budget, and an `experimental` block
carrying proposal-only self-healing flags.

Two blocks carry most of the teaching weight. The policy shows the shorthand rule form and the two
verbs:

```yaml
policies:
  - name: SafeEditPolicy
    rules:
      - deny secrets_to_llm
      - deny production_write_without_approval
      - require tests_if_code_changed
      - require evidence_if_harness_completed
      - require supply_chain_check_if_dependency_added
```

**Listing E.1 — The delivery policy.** From `examples/governed_delivery_control_plane.nyx:62-69`.

The harness shows that repair is bounded and that gates are declared separately from flow:

```yaml
    repair:
      - on: test_failure
        agent: Builder
        action: repair
        max_attempts: 3
    gate:
      - require: tests.pass
      - require: security.pass
      - require: human_approval_before_merge
```

**Listing E.2 — Bounded repair and gates.** From
`examples/governed_delivery_control_plane.nyx:107-116`. The `on:` key parses as a string only
because the parser restricts YAML's implicit boolean conversion — see Appendix A, section A.2.

What it does not demonstrate: any enforcement. Three of the five rules are `require` rules, which
are recorded as pending evidence and never evaluated as conditions.

## E.2 The organisation-policy reference pair (bundled)

**Paths:** `nornyx/examples/org_policies.nyx` and `nornyx/examples/governed_service.nyx` — both
checked, exit 0.

Two contracts that exist only to demonstrate one mechanism. The first holds the canonical policy in
exactly one place; the second references it rather than copying it.

```yaml
policies:            # org_policies.nyx
  - name: SafeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
      - deny nondeterministic_evaluation
      - require evidence_if_harness_completed
      - require human_approval_before_merge
```

```yaml
policies:            # governed_service.nyx
  - name: SafeDeliveryPolicy
    ref: org_policies.nyx#SafeDeliveryPolicy
```

**Listing E.3 — The canonical definition and its reference.** From
`nornyx/examples/org_policies.nyx:9-16` and `nornyx/examples/governed_service.nyx:11-13`.

The comment in the referencing contract states the value plainly: the rules resolve from one source
at load time, so the contract carries no copy and cannot drift from the organisation standard. The
resolution is offline and local, and compiles into inline `rules` before any downstream stage sees
the document — checker, generator, and drift gate all see an ordinary policy.

The boundary here is deliberate. A cross-*repository* policy reference was considered and declined,
on the grounds that it would reopen the frozen schema and sacrifice a contract's readability on its
face. The workspace manifest of section E.11 occupies that space instead.

## E.3 Release guardrails (bundled)

**Path:** `nornyx/examples/release_guardrails.nyx` — checked, exit 0.

A small, complete contract for continuous integration and release governance. It is worth studying
because its policy is unusually requirement-heavy:

```yaml
policies:
  - name: ReleasePolicy
    rules:
      - require ci_passed_before_release
      - require changelog_updated
      - require rollback_plan_for_deploy
      - require human_approval_for_production
      - deny release_if_secrets_detected
```

**Listing E.4 — A requirement-dominated policy.** From
`nornyx/examples/release_guardrails.nyx:55-61`.

Only the last rule is executable as a pattern match, and only because it contains the token
`secret`. The other four are recorded as pending evidence. This example is therefore the clearest
available illustration of the gap between what a contract *asserts* and what the local decision
manifest *evaluates* — a gap the book's eight questions are designed to expose.

Its four gates (`ci.pass`, `changelog.updated`, `rollback_plan.present`,
`human_approval_before_production`) are likewise declarations that a pipeline must honour, not
checks the tool performs.

## E.4 Governed email triage (bundled)

**Path:** `examples/email_triage.nyx` — checked, exit 0.

The smallest complete service contract in the bundled set: a single-purpose classification service
with a constitution of three principles, one context, two skills, one policy, and an eval over a
declared dataset. It is the example to reach for when demonstrating the language to someone who has
not seen it, because it fits on two screens and still exercises intent, context, policy, agent,
eval, evidence, and approval.

Its constitution — no personally identifiable information to an external model, approval before
customer impact, evidence required for AI decisions — reads as three sentences of policy that the
rest of the document then has to make concrete. Watching where it succeeds and where it only
declares is a good first exercise in reading contracts critically.

## E.5 The governed customer-support network (bundled)

**Path:** `examples/agentic_network_support/support_network.nyx` — see the check results below.

The canonical agentic-network demonstration: four identities, eight capabilities, two trust zones,
three gates, one protocol target, one delegation, one handoff, and four relations, all under the
`agentic_network` profile. It is the largest bundled contract and the only one that exercises the
full declaration model of Appendix A, section A.10.

```yaml
  - name: escalate_high_value_refund
    actions: [escalate_refund]
    risk: high
    scope_type: context
    scope_refs: [SupportContext]
    delegable: false
    required_gate_refs: [gate.escalation_review]
    required_approval_refs: [agentic_network_authority]
    required_evidence_refs: [agentic_network_contract_review]
```

**Listing E.5 — A high-risk, non-delegable capability.** From
`examples/agentic_network_support/support_network.nyx:211-219`. Risk tier, gate, approval, and
evidence are declared together on the capability, so the obligation travels with the grant rather
than living in a separate table.

```yaml
    - id: zone.customer_channel
      classification: external_contract_only
      allowed_transition_targets: []
      share_allowlist: [customer_response, evidence_digest]
      never_share: [secrets, credentials, tokens, private_memory]
      ingress_gate_refs: [gate.customer_response]
      egress_gate_refs: []
```

**Listing E.6 — The external trust zone.** From
`examples/agentic_network_support/support_network.nyx:326-332`.

**A verified finding worth teaching.** Running `nornyx check` on this contract with no `--as-of`
fails, exit 1, with six diagnostics: `AN_APPROVAL_EXPIRED`, `APPROVAL_EXPIRED`, and four
`EVIDENCE_STALE`. Supplying the tutorial's instant —
`nornyx check examples/agentic_network_support/support_network.nyx --as-of 2026-07-17T00:00:00Z` —
passes, exit 0. The contract's approval declares `expires_at: "2026-07-24T00:00:00Z"`, and the
audit date is later than that. This is not a defect in the example; it is the expiry machinery
working. It also demonstrates why `--as-of` fails closed on a malformed value rather than falling
back to the live clock: an approval's validity is a governance fact, and silently substituting
"now" would make it unreproducible.

Generation was also verified live: `nornyx agentic-network generate ... --as-of 2026-07-17T00:00:00Z`
reported `"artifact_count": 10` and wrote the nine declaration artifacts plus
`agentic_generation_manifest.json`.

## E.6 A governed-package registration (bundled)

**Path:** `examples/governed_package/register_existing.nyx` — `nornyx check` exit 0;
`nornyx package validate` printed "Nornyx governed package validation passed", exit 0.

The artifact-first path: describing, validating, and hash-locking a set of files that already
exists rather than generating one from scratch. Three blocks carry the safety posture:

```yaml
  approval_gates:
    - id: gate-register-review
      required_evidence:
        - inventory_report
        - review_record
      eligible_approver_roles:
        - reviewer
      denied_approver_types:
        - execution_surface
        - ai_tool
  installation_policy:
    installed: false
    executable_by_default: false
    requires_explicit_install: true
  safety_boundary:
    secrets_allowed: false
    production_data_allowed: false
    autonomous_execution_allowed: false
    external_writes_allowed: false
    deployment_allowed: false
    approval_required: true
```

**Listing E.7 — Inert-by-default declarations.** From
`examples/governed_package/register_existing.nyx:41-75`.

Every one of those flags is checked. Setting any of them permissively fails validation. The
companion negative fixture proves the point: `nornyx package validate
examples/governed_package/invalid_ai_tool_approver.nyx` exits 1 with a single diagnostic,
`INVALID_APPROVER_EXECUTION_SURFACE`, message "execution surfaces and AI tools cannot be eligible
approvers", path `governed_package.approval_gates[0]`.

The claim boundary is stated in the documentation and printed into the generated analysis report:
Nornyx may claim a package was inventoried, risk-surfaced, evidence-bound, hash-locked, and
approval-gated. It must not claim the package is safe.

## E.7 Architecture governance (bundled)

**Path:** `examples/architecture_governance.nyx` — checked, exit 0.

A 0.2 contract carrying an `ArchitectureAuthority` approval that denies all six non-human actor
types, an exact git revision binding, and hash-bound governance evidence records. Its companion
files include a real report envelope at `examples/architecture_reports/dependency_boundaries.json`
recording the tool `dependency-cruiser` 16.10.4, status pass, zero violations.

It is included here because it demonstrates the *import* pattern rather than the *execute* pattern:
the architecture tool runs in a pipeline, emits the neutral envelope, and Nornyx validates the
envelope's binding without ever invoking the tool. That division — Nornyx owns the envelope,
specialists run outside — recurs throughout the evidence design and is the single most
transferable idea in the repository for readers integrating their own scanners.

## E.8 Atlas: the controlled research assistant (illustrative)

**Checked:** written to a temporary directory and validated with `nornyx check`; exit 0, no
diagnostics.

Thread A of the case studies. Atlas belongs to Northstar's Research and Insights division and may
search an approved source allowlist, summarise, and file internally; it may not publish externally,
purchase, disclose confidential data, or invoke undeclared tools.

```yaml
contexts:
  - name: ResearchContext
    include:
      - "sources/allowlist/**/*.md"
      - "briefs/**/*.md"
    exclude:
      - "**/.env"
      - "customer_data/**"
    authority:
      - "policies/research_authority.md"
    taint:
      repo: trusted_repo_file
      authoritative_repo: authoritative_repo_file
      user_prompt: untrusted
      external_web: untrusted

policies:
  - name: AtlasResearchPolicy
    rules:
      - deny secrets_to_llm
      - deny production_write_without_approval
      - require evidence_if_harness_completed
      - require human_approval_before_external_share

approvals:
  - name: partner_disclosure_approval
    required_for:
      - external_share
      - publish_external
```

**Listing E.8 — Atlas, abridged.** Illustrative; validated with `nornyx check` under a temporary
directory, exit 0.

Two design choices are worth noting. First, retrieved web content lands in the `external_web`
channel, whose taint is `untrusted` and whose `may_define_policy` flag is false — which is the
language's expression of the rule that a retrieved document must never be able to redefine the
agent's authority. Second, the partner-share approval is declared as an approval requirement rather
than as a rule, because a rule can only deny or require; only an approval carries an accountable
human, a validity window, and a revision binding.

The honest limitation: at the core language level this contract's `authority` ranking is advisory
metadata. Chapter 6 develops what would have to be true for it to be enforcement.

## E.9 Forge: the enterprise development agent (illustrative)

**Checked:** `nornyx check` exit 0; `nornyx generate` wrote `AGENTS.md`, a `skills/` directory, six YAML block dumps, `evidence_contract.md`, and `nornyx_generation_manifest.json`;
`nornyx drift` reported status `pass`, exit 0; after a single character was changed in the
generated `policy.yaml`, `nornyx drift` reported status `drift`, exit 1.

Thread B. Forge works on `northstar/payments-api`: it may read, propose on branches, run tests, and
open pull requests; merges to protected branches, production deployment, release publication,
secrets access, and destructive changes all require named human approval.

```yaml
policies:
  - name: ForgeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - deny production_write_without_approval
      - deny destructive_schema_change
      - deny self_modification_without_approval
      - require tests_if_code_changed
      - require evidence_if_harness_completed
      - require supply_chain_check_if_dependency_added
      - require human_approval_before_merge

approvals:
  - name: MergeApproval
    required_for:
      - merge_protected_branch
      - production_deploy
      - release_publication
      - secrets_access
      - destructive_change
```

**Listing E.9 — Forge, abridged.** Illustrative; validated with `nornyx check`, then generated and
drift-gated under a temporary directory.

The four deny rules were chosen so that each lands in a different token category of the deny
matcher: `production`, `secret`, `destructive`, and `self_modification`. A rule outside those
categories — however sensible in prose — matches nothing.

The drift result is the load-bearing part of this example. Forge's real control is not the policy
text; it is that the generated artifacts are byte-stable and hash-compared, so a change made
directly to `policy.yaml` rather than to the contract is caught. That is the "bypass attempt
committing directly to a generated artifact" scene from the case bible, reproduced mechanically.

## E.10 Ledger: a treasury network fragment (illustrative)

**Checked — twice, with different results.** Without a declared profile, `nornyx check` exits 0
with two `UNKNOWN_TOP_LEVEL_BLOCK` warnings (`agent_identities`, `agentic_network`). With
`profile: agentic_network` added to the project block, the same file exits 1 with nineteen
diagnostics across fourteen distinct codes.

Thread C. Treasury's payment-exception handling, expressed as three zones, one identity, two
capabilities, one gate, and one bounded delegation.

```yaml
agentic_network:
  schema: nornyx.agentic_network.v1
  id: network.treasury_exceptions
  subject_revision: git:3b7a9d10000000000000000000000000deadbeef
  trust_zones:
    - id: treasury-data
      classification: internal
      allowed_transition_targets: []
      share_allowlist: [exposure_estimate]
      never_share: [account_credentials, full_pan]
      ingress_gate_refs: []
      egress_gate_refs: []
  delegations:
    - id: delegation.exposure_analysis
      delegator_ref: identity.ledger_planner
      delegate_ref: identity.ledger_analyst
      capability_ref: analyze.exposure
      actions: [analyze_exposure]
      scope_refs: [TreasuryContext]
      status: active
      max_depth: 1
      current_depth: 0
      onward_delegation: denied
```

**Listing E.10 — Ledger, abridged.** Illustrative — not drawn from the repository.

The diagnostics the profiled version produced are the lesson. They were, by count:
`AN_EVIDENCE_UNKNOWN` (three), `RULE_PATH_MISSING`, `GOVERNANCE_REQUIRED_BLOCK_MISSING`,
`AN_APPROVAL_UNKNOWN` (two each), and one each of `APPROVAL_DECLARATION_REQUIRED`,
`AN_REVISION_REQUIRED`, `AN_DELEGATOR_UNKNOWN`, `AN_DELEGATION_GATE_REQUIRED`,
`AN_DELEGATION_EVIDENCE_REQUIRED`, `AN_DELEGATION_APPROVAL_REQUIRED`,
`AN_CONTRACT_REVIEW_MISSING`, `AN_AUTHORIZATION_EXPIRED`, `AN_APPROVAL_RECORD_MISSING`, and
`AN_APPROVAL_DECLARATION_MISSING`.

Read that list as a specification. The fragment declares a delegation across trust zones without a
governing gate, without the required human approval, without contract-review evidence, and with a
delegator identity that is referenced but never declared. Every one of those is a real governance
hole, and every one of them is invisible until the profile is selected. Declaring the profile is
what converts a set of tolerated unknown blocks into a set of obligations — and the same file that
"passed" a moment earlier now names fourteen distinct problems.

Two of the diagnostics also show the composition layer at work rather than the network checker:
`GOVERNANCE_REQUIRED_BLOCK_MISSING` and `RULE_PATH_MISSING` come from the composed profile's own
required blocks and closed rules.

## E.11 Charter: an organisation workspace manifest (illustrative)

**Checked:** two member contracts written under a temporary directory; `nornyx workspace-check
--manifest nornyx.workspace.yaml --json` reported status `drift`, exit 1, naming the divergent
member and the exact missing rule.

Thread E. Northstar's governance repository holds the organisation standard once; member
repositories declare the same policy by name.

```yaml
workspace: NorthstarGovernance
policies:
  SafeDeliveryPolicy:
    - deny secrets_to_llm
    - require tests_if_code_changed
    - require human_approval_before_merge
members:
  - path: payments-api/nornyx.nyx
  - path: support-network/nornyx.nyx
```

**Listing E.11 — A workspace manifest.** Illustrative, following the shape documented at
`docs/USE_IN_YOUR_REPO.md:101-111`.

With `payments-api` declaring all three rules and `support-network` declaring only two, the report
recorded the second member's policy as `drift` with `missing: ["require
human_approval_before_merge"]` and `extra: []`. Comparison is on normalised rule *sets*, so
reordering is not drift and a missing rule is.

This layer exists because of a real failure documented in the repository's own multi-repository
case study: two repositories each passed their own drift gate while the shared policy silently
diverged, because no organisation-level check existed. A second finding from the same study is
worth carrying into any adoption plan — the gate the documentation originally recommended diffed
only `AGENTS.md`, which does not render policy rules, so a `policy.yaml` change passed green. The
full-output `nornyx drift` gate of section E.9 is the fix.

Two behaviours to design around. `--write` sync mode returns exit 0 with status `synced`, because
it repaired the divergence; a pipeline that runs it in write mode is a fixer, not a gate. And sync
deliberately does not invent missing policy blocks or missing files — those stay reported as drift
for a human.

## E.12 Choosing among these examples

For a first contract, start from `nornyx init --profile minimal --name <project>` and compare the
result with section E.4. For a delivery pipeline, section E.1 plus the drift gate of E.9. For
cross-repository consistency, sections E.2 and E.11 together — the reference mechanism inside a
repository, the workspace manifest across them. For a multi-agent system, section E.5, and expect
to spend most of your time on the material section E.10 shows missing: gates, approvals, evidence
references, and an immutable subject revision. For third-party artifacts, section E.6.

One closing caution. Six of the eleven examples above pass every check the toolchain applies, and
none of them thereby demonstrates that any agent behaved correctly. Chapters 13 and 14 give the
vocabulary for saying what a passing contract does and does not license you to claim; Appendix G
turns that vocabulary into a review checklist.
