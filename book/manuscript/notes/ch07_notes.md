# Chapter 7 — Author notes

Chapter: "Policy Semantics and Deterministic Evaluation" (Part II).
Snapshot basis: repository `/home/user/nornyx` at git HEAD `70d2b40`, distribution 1.11.0.

## Claims I could not verify (and what I wrote instead)

1. **Rule tokens in Listing 7.2.** `deny secrets_to_llm` and `require evidence_if_harness_completed`
   are verbatim canonical rules from `examples/governed_delivery_control_plane.nyx`.
   `deny destructive_actions` and `require human_approval_before_external_share` are **adapted**:
   they use the real rule *form* and, in the deny case, a real matched token (`destructive`), but
   the exact strings do not appear in the repository. The listing caption states which two are
   verbatim and which two are adapted. This is safe because the fact pack establishes that rule
   tokens are free-form strings and only the deny-side substring tokens are semantically load-bearing.

2. **The three-valued decision domain is not a `.nyx` policy-block feature.** This was the single
   biggest risk of overclaiming in the chapter. `DecisionEffect` (`ALLOW`, `DENY`,
   `APPROVAL_REQUIRED`) belongs to the runtime authorization engine in `nornyx/agentic/authz.py`,
   **not** to the `.nyx` `policies:` block, whose runtime produces per-step planning decisions with
   codes like `POLICY_RECORDED`. The §7.6 callout says this explicitly ("The richer three-valued
   decision domain of Section 7.2 appears in a different component") and tells the reader to keep
   the two layers distinct. Nothing in the chapter implies the `.nyx` rule atoms return
   approval-required.

3. **Exit codes.** I wrote that a malformed `--as-of` fails "with the diagnostic `AS_OF_INVALID` and
   a reserved exit code" rather than naming the number. The fact packs give exit 2 for parse and
   lock failures (`docs/GOVERNANCE_CLI_AND_API.md:42–53`), and I did not open `nornyx/cli.py` to
   confirm the `AS_OF_INVALID` path specifically, so I **softened to "a reserved exit code."** A
   later editor who verifies `nornyx/cli.py:133–171` can restore the number.

4. **Test-suite counts.** I deliberately cite no test numbers, file names, or pass counts in
   Chapter 7. The fact pack's "1523 passed, 55 skipped" comes from `manifest.json`'s recorded
   release run rather than an execution, and Chapter 15 owns testing claims anyway.

5. **Comparative claims about OPA/Rego, Cedar, and XACML** (Table 7.1) are drawn from the cited
   primary sources in the bibliography, are written dimension-by-dimension, and make no superiority
   claim in any direction. The row "Analyzability — limited in practice" for XACML is the weakest
   claim in the table; it is stated as a practical observation rather than a property of the
   standard, and it is the row I would most want a technical reviewer to check.

6. **Schneider's result.** I state that execution monitors enforce exactly the safety properties and
   that noninterference-style information-flow properties are not in that class in general. This is
   the standard reading of [@schneider-enforceable]. I applied it to Chapter 6's taint/never-share
   rules as a *conservative approximation* — my own framing, written as general-principles prose,
   not attributed to the paper.

## PROPOSED-REF additions

None. All citations (`opa`, `cedar`, `xacml`, `schneider-enforceable`, `saltzer-schroeder`,
`rbac-nist`, `abac-nist`) are already in `design/05_bibliography.md`.

## Repository paths I personally verified (read directly, not via fact pack)

- `/home/user/nornyx/nornyx/policy_runtime.py` — read `normalize_policy_rules` (lines ~83–108),
  `normalize_capabilities` (~111–137), `_matches_deny_rule` (~185–203), the pending-requirement
  construction in `_policy_decision` (~260–276), and the report constructor (~440–458). Every
  specific claim in the §7.6 honest-accounting callout was read here, not taken from the fact pack:
  that only `deny`/`deny:` and `require`/`require:` prefixes are recognized and any other rule
  string falls into `require`; that deny matching is substring-token based over `production`
  (matching `production|prod|deploy|release`), `secret` (`secret|token|credential`), `destructive`
  (`delete|destroy|drop|wipe|reset|remove`), `connector` (connector-kind steps), and
  `self_modification`; that require rules become `{"rule": …, "status": "pending_evidence"}`
  entries and are never executed; and that every report embeds
  `"default_capability_mode": "deny_unless_declared"` together with a `safety` block whose five
  flags (`tools_executed`, `connectors_enabled`, `models_called`, `agents_executed`,
  `arbitrary_commands_allowed`) are all `False`.
- `/home/user/nornyx/nornyx/agentic/authz.py` — read the module docstring (lines 1–26) and the
  `DecisionEffect` enum (~399–402). The determinism callout in §7.4 quotes the docstring's own
  boundary statements: "It reads no wall-clock time"; that `validation_as_of` governs load-time
  validation while `EvaluationContext.decision_at` governs *all* temporal action semantics
  (identity, membership, delegation, handoff, approval, revocation validity); and that the
  Authorizer is "deeply immutable," with retained document, composition, lock, and derived indexes
  "recursively frozen … detached from the caller's inputs," and "synchronous, deterministic,
  reusable." `DecisionEffect` confirmed to have exactly three members.
- `/home/user/nornyx/schemas/agent_identities_v1.schema.json`,
  `/home/user/nornyx/schemas/agentic_capabilities_v1.schema.json`,
  `/home/user/nornyx/schemas/agentic_network_v1.schema.json` — read for the closed-schema claim in
  §7.5: each record sets `additionalProperties: false`. (The top-level document schemas'
  `additionalProperties: false` and the checker's warning-level `UNKNOWN_TOP_LEVEL_BLOCK` are taken
  from fact pack 01 §2.3 / §3, which cites `schemas/nornyx_v1_0.schema.json:20` and
  `nornyx/checker.py:828–839`; I did not reopen those two files.)

## Deliberate scope decisions

- No inline status badges; prose status wording only, per the pre-Chapter-16 rule.
- Section count reduced to seven by folding closed schemas and testability into one section (7.5)
  with two `###` subsections, to stay inside the 4–7 numbered-section limit.
- Composition, precedence, and provenance are named once (the scalar-conflict case in §7.3) and
  handed to Chapter 8 rather than developed, to avoid duplicating the existing chapter.
- Approvals are treated only as a decision *outcome* here; what makes an approval a bound record
  (role, actor type, revision binding, expiry, invalidation) is left entirely to Chapter 9.
