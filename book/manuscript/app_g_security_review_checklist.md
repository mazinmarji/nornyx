---
appendix: G
title: "Appendix G — Security Review Checklist"
---

# Appendix G — Security Review Checklist

This appendix is a working checklist for reviewing a governed agentic system. It is organised
around the threat material of Chapters 14 and 34 and closes with the eight questions introduced in
Chapter 3, restated as a claims review.

It is deliberately not a compliance instrument. Nothing here maps to a certification, and passing
every item establishes no legal or regulatory sufficiency. What it does establish is that a
reviewer has looked at each place where a governance claim is commonly weaker than it appears.

Each section names the chapters that develop its material, so that a reviewer who cannot answer an
item knows where to read. Items marked **(residual)** are conditions you should expect to accept
and document rather than eliminate; a review that reports them as resolved is wrong.

## G.1 Contract hygiene

*Chapters 17, 21, 28.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | `nornyx check` passes with exit 0, and the warnings were read, not just the exit code | Warnings never fail a build. `UNKNOWN_TOP_LEVEL_BLOCK`, `UNKNOWN_VERSION`, and `PACK_NOT_RESOLVED` are all warnings, and each can mean an entire governance layer is silently inactive |
| ☐ | Every `UNKNOWN_TOP_LEVEL_BLOCK` warning is explained | The most common cause is a governance block declared without the profile that would validate it — the file looks governed and is not |
| ☐ | The declared profile and modules are the intended ones | `PACK_NOT_RESOLVED` degrades to a warning for `project.profile`, so a typo yields an ungoverned contract that still passes |
| ☐ | No policy rule was silently reclassified | An unrecognised rule prefix is bucketed into `require`, and `require` rules are never evaluated. Read the normalised deny and require sets, not the source lines |
| ☐ | Deny rules use tokens the matcher recognises | Only `production`, `secret`, `destructive`, `connector`, and `self_modification` categories match anything |
| ☐ | Requirement rules are backed by something outside the contract | A `require` rule records a pending evidence obligation; if no pipeline step honours it, it is a comment |
| ☐ | Every `ref` resolves to the intended canonical source | References resolve at load time and compile into inline rules; after resolution the referencing contract is indistinguishable from one that copied them |
| ☐ | The contract is formatted and diffs are reviewed semantically | A reordered list is not a semantic change; a changed rule is. Review the generated `policy.yaml` diff alongside the source diff |
| ☐ | Generated artifacts are regenerated and drift-gated in the pipeline | `nornyx drift` compares the **entire** artifact set by digest. A gate that diffs only `AGENTS.md` passes a changed `policy.yaml` — a real defect found in the repository's own recommended gate |
| ☐ | Cross-repository policy consistency is checked | Both repositories' own drift gates can stay green while a shared policy diverges; `nornyx workspace-check` is what catches it |
| ☐ | `workspace-check --write` is not being used as a gate | Sync mode exits 0 with status `synced` because it repaired the divergence on disk |

## G.2 Authority and taint review

*Chapters 5, 6, 34.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | Every context declares `include` and `exclude` deliberately | An over-broad include pulls untrusted content into a trusted channel |
| ☐ | Secret-bearing paths are excluded | `**/.env`, credential directories, and key material should never enter the governed input surface |
| ☐ | The `authority` list is ordered intentionally | Position determines rank; a permissive pattern placed first outranks the specific ones after it |
| ☐ | Only genuinely authoritative sources are in the authority channel | The `authoritative_repo` channel is the only one whose `may_define_policy` flag is true |
| ☐ | Retrieved and user-supplied content lands in an untrusted channel | `user_prompt` and `external_web` default to taint `untrusted` and cannot define policy |
| ☐ | **(residual)** Authority rank is treated as metadata, not enforcement | The context pack itself records that "authority rank is advisory metadata until a later enforcement goal" |
| ☐ | Prompt-injection exposure is analysed as authority confusion, not as content filtering | The question is not whether a retrieved document contains hostile text but whether it can reach a decision the system treats as authoritative |
| ☐ | Trust zone classifications match reality | Seven classifications exist; `external_contract_only` and `contract_only` mean something different from `internal` |
| ☐ | Every zone's `never_share` list is present and complete | The schema requires it non-empty; a minimal list satisfies the schema without satisfying the intent |
| ☐ | `allowed_transition_targets` is a whitelist you would defend | An empty list means nothing may leave by declaration; a permissive list is easy to write and hard to notice |
| ☐ | Capability scope references name real, narrow contexts | Capability scope is always a declared context; a capability scoped to an over-broad context is over-granted |
| ☐ | Delegation depth and onward delegation are bounded | `max_depth` is 1–8 and `onward_delegation` is either `denied` or `allowed_with_policy`; the default you want is almost always `denied` |
| ☐ | Handoffs transfer work, not authority | A handoff that would let the recipient act beyond what it holds is an escalation, caught statically as `AN_HANDOFF_AUTHORITY_ESCALATION` |
| ☐ | Duty separation is declared where it matters | No identity should hold both the drafting and the approving capability for the same action class |

## G.3 Approval design

*Chapters 9, 19, 36.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | Every approval denies all six non-human actor types | `ai_tool`, `execution_surface`, `autonomous_agent`, `model`, `connector`, `generated_output`. These are intrinsically unable to hold approval authority and cannot be redeclared as human |
| ☐ | `accountable_authority` names a human role | A non-human authority normalises as `APPROVAL_NON_HUMAN_AUTHORITY` |
| ☐ | Eligible and required roles are named, not implied | An approval with no eligible roles is an approval anyone can satisfy |
| ☐ | The approval is bound to an exact revision | `revision_binding` with `exact: true` and an immutable content-addressed revision. A force-push that changes the revision must invalidate the approval, and does |
| ☐ | Invalidation conditions are declared | Revision change, identity change, capability change, trust-zone change, membership change — the conditions under which a still-unexpired approval stops applying |
| ☐ | The approval expires | Either an absolute `expires_at` or a relative `expires_after`. The engine takes the earliest of the assertion expiry, the absolute expiry, and issue time plus the relative window |
| ☐ | Expiry windows are proportionate | A twenty-four-hour window is the built-in human-approval module's choice; a year-long window is an approval in name only |
| ☐ | Required evidence is named and is actually produced | Missing evidence references deny with `APPROVAL_EVIDENCE_MISSING` |
| ☐ | The action list covers exactly the actions gated | An approval that does not cover the requested action denies with `APPROVAL_ACTION_MISMATCH`; one that covers too much is over-broad |
| ☐ | Maker–checker holds: the proposer cannot approve | Caught as `SOD_SELF_APPROVAL`; the evidence producer must not be the sole approver either |
| ☐ | Approval fatigue is considered | An approval requirement fired on every change trains reviewers to click through. Count the expected approvals per week and ask whether an informed decision is possible at that rate |
| ☐ | Exceptions are bounded, owned, and closed | Risk tier, accountable owner, approving authority, compensating controls, validity window, renewal policy, closure evidence. Renewal is either prohibited or manual reapproval — never automatic |
| ☐ | **(residual)** Approvals bind identities, not authenticated humans | Nornyx does not authenticate approvers. The binding is to a declared role and revision; who actually held the credential is established outside the system |

## G.4 Lock verification

*Chapters 12, 18, 29.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | A profiles lock exists and is verified in the pipeline | Governance commands verify `nornyx.profiles.lock` when present and never rewrite it. Absent, pack resolution is unpinned |
| ☐ | Profile-lock failures are handled as exit 2 | `PACK_LOCK_MISMATCH` and its siblings exit 2, not 1; a pipeline testing only for 1 mishandles them |
| ☐ | A network lock exists for every agentic-network contract | The lock binds contract digest, network identity and immutable revision, pack identities and hashes, block schemas, structural checks, runtime-events schema version, protocol declarations, per-record digests, approval and evidence requirements, and artifact hashes |
| ☐ | `lock-check` runs in the pipeline, not only locally | `AN_LOCK_SOURCE_STALE` is the ordinary "the contract changed" signal and should block, not warn |
| ☐ | Artifact hashes are checked against what is on disk | `AN_LOCK_ARTIFACT_MISMATCH`, `_MISSING`, and `_UNEXPECTED` catch a hand-edited or extra artifact |
| ☐ | The subject revision is immutable | Only `git:` hex or `sha256:` forms are representable; a mutable revision cannot bind anything |
| ☐ | Lock regeneration is a reviewed event | **(residual)** A hostile local writer can regenerate a consistent lock. The repository documentation is explicit: detecting unauthorised regeneration is a repository control — git history and human review — not a lock property |
| ☐ | Locks are time-free and reproducible | The profiles lock omits time fields so identical inputs produce byte-identical locks; a lock that changes without an input change is a signal |
| ☐ | **(residual)** The lock binds bytes, not producers | It never attests runtime behaviour, who produced the bytes, or that the content is true |

## G.5 Evidence validation

*Chapters 11, 12, 20, 36.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | Evidence validation runs with `--strict` in the pipeline | Without `--strict`, a failing validation still exits 0 |
| ☐ | The stream's schema version matches the lock | A 1.0 stream is never silently upgraded; a mismatch is `AN_EVT_SCHEMA_LOCK_MISMATCH` |
| ☐ | Every event binds network identity, contract digest, lock digest, and subject revision | These four are required per event, not per envelope, precisely so that a mixed stream cannot pass |
| ☐ | Sequences are contiguous and timestamps non-decreasing per mission | Gaps and reordering are `AN_EVT_SEQUENCE_GAP` and `AN_EVT_ORDER_INVALID`. **(residual)** This proves local sequence consistency of the supplied stream, not distributed causality |
| ☐ | Paired transitions are complete | A tool invocation without an allowance, an acceptance without a request, a completion without an initiation, a grant without a request |
| ☐ | Replay detection is understood before it is trusted | The fingerprint excludes transport fields — event identifier and sequence always, timestamp additionally in explicit occurrence mode — so a restamped duplicate is still caught, while identical work in a new occurrence is correctly not replay |
| ☐ | Occurrence semantics are correct for the workload | Retry inside one occurrence, loop visits and parallel branches as distinct occurrences, resume offsetting the attempt counter. Retry after success is refused |
| ☐ | Approval events name human approvers | `AN_EVT_APPROVAL_NON_HUMAN` applies to grants only, so a *refused* non-human approval is legitimately recordable — a distinction worth checking rather than assuming |
| ☐ | Evidence artifacts are contained and hash-bound | Paths resolve relative to the events file's own directory and may not escape it, including by symlink; contents must match their declared digests |
| ☐ | Evidence freshness is evaluated at a pinned instant | Supply `--as-of` for reproducible results; a malformed value fails closed rather than falling back to the live clock |
| ☐ | The retention and privacy position is stated | Evidence streams can carry operational detail; someone must own how long they are kept and who may read them |
| ☐ | **(residual)** The proof boundary is written into the report and into your claims | Validated evidence proves conformance of supplied records only; hash validity proves content binding, not event truth; a producer can omit or fabricate events; Nornyx does not observe, operate, or monitor the runtime |

## G.6 Coverage and bypass review

*Chapters 13, 14, 22–25.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | A coverage inventory exists for every integration | Without one, the enforcement claim names no surfaces and cannot be reviewed |
| ☐ | Wrapped, unsupported, and unwrapped surfaces are distinguished | `UNWRAPPED` means caller-owned; someone must own it |
| ☐ | Unsupported surfaces fail closed rather than executing ungoverned | The async tool path is the model: the inherited method raises, the action never runs, nothing is recorded |
| ☐ | Every caller-owned surface has a named owner | Graph topology is the standing example — the caller must wrap each governed node explicitly |
| ☐ | A bypass test exists and is read as information, not embarrassment | Calling the underlying callable directly skips enforcement entirely, and a test asserts it |
| ☐ | **(residual)** A total bypass may leave no trace | ADR-0040 states this plainly. Any monitoring plan that assumes a bypass is visible in the evidence stream is unsound |
| ☐ | The claim is scoped to the wrapped surfaces | No wrapped subset upgrades a whole application to Tier 2 |
| ☐ | Framework version pins are enforced at import, not merely declared | A framework upgrade can move the wrapped surface |
| ☐ | Negative controls exist alongside positive ones | At least one allow control and one deny control on a declared wrapped surface, which is the Tier 2 deny-path eligibility requirement |
| ☐ | Failure of the enforcement point is analysed | An unexpected error in evaluation or recording must propagate before the action runs — verify this rather than assuming it |
| ☐ | Injected dependencies, not re-derived state | An adapter that re-reads or re-composes the contract creates a second interpretation that can disagree with the first |

## G.7 Package and third-party intake

*Chapters 27, 34.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | Third-party artifacts are scanned before use, never executed | The scanner is local, deterministic, and prints `"package_payload_executed": false`; hooks are not activated and declared servers are not started |
| ☐ | Findings across all seven categories are reviewed | Hooks, protocol server definitions, secret-like patterns, endpoints, dangerous commands, scripts, and claim-versus-evidence mismatches |
| ☐ | Claim mismatches are treated as high-signal | A package claiming "docs only" while carrying executable surfaces, or "no network" while carrying endpoints, is a critical finding by construction |
| ☐ | Scan-conditional evidence requirements are satisfied | Hooks require a hook risk review, protocol definitions require a review, secret patterns require secret-scan evidence, critical claim mismatches require a claim review |
| ☐ | Installation and safety flags are inert | Not installed, not executable by default, explicit install required; secrets, production data, autonomous execution, external writes, and deployment all disallowed |
| ☐ | No execution surface or AI tool appears as an approver | Rejected as `INVALID_APPROVER_EXECUTION_SURFACE`; the doctrine sentence is "execution surfaces are tools, not accountable approvers" |
| ☐ | Registered artifacts are hash-locked and the lock verifies | Registration binds source, report, artifact, scanner-report, and manifest hashes |
| ☐ | Imported external evidence is understood as imported | Only two importers exist. Imported records mark that an external scanner ran; they do not mean the payload was executed by Nornyx, nor that the external tool ran honestly |
| ☐ | Radar output is treated as advisory | It carries `proposal_only: true`, and its confidence figures are fixed constants rather than a calibrated model |
| ☐ | **(residual)** No safety claim is made about the package | The permitted claim is inventoried, risk-surfaced, evidence-bound, hash-locked, and approval-gated |
| ☐ | Declared protocol targets are contract-only | `mcp` and `a2a` only, with execution mode and live connector execution pinned to constants; a declaration is not a runtime |

## G.8 Continuous-integration gates

*Chapters 15, 29.*

| ✅ | Item | Why it matters |
|---|---|---|
| ☐ | Contract validation runs on every change | With a pinned `--as-of` where any expiry or freshness matters |
| ☐ | Exit code 2 is handled distinctly from 1 | A 2 is a structural refusal — parse failure, path rejection, lock validation failure — not a policy verdict |
| ☐ | The full-output drift gate runs | Regenerate and compare every artifact by digest |
| ☐ | Lock verification runs | Both the profiles lock and, where applicable, the network lock |
| ☐ | Evidence validation runs strictly | And its report is retained as a build artifact |
| ☐ | Skipped tests fail the build | An import-guarded framework test suite skips silently when the extra is absent; parse the test report and fail closed on any skip |
| ☐ | The installed artifact is smoke-tested outside the source tree | A package that only works from a source checkout is not the package your users get |
| ☐ | Network isolation is asserted, not assumed | Patch socket connection in the smoke test and assert zero attempts |
| ☐ | Release publication is tag-bound and fails closed on mismatch | And uses trusted publishing rather than a stored token |
| ☐ | The pipeline verifies it built the candidate it was asked to build | Compare the checked-out revision against the requested head |
| ☐ | Governance failures block the lane they protect | A contract that fails validation should block the merge lane entirely, not annotate it |
| ☐ | The governance layer itself is monitored | A gate that silently stopped running is indistinguishable from a gate that keeps passing |

## G.9 Closing claims review — the eight questions

*Chapter 3 introduces these; Chapters 13, 36, and 38 apply them.* Work through them for each claim
the system makes, and write the answers down. A claim whose answers cannot be written is not ready
to be made.

| ✅ | Question | What a good answer contains |
|---|---|---|
| ☐ | **1. What exactly is guaranteed?** | A scoped statement naming the surfaces, the contract revision, and the actions. Not "the agent cannot deploy to production" but "the declared production-deploy capability denies for these identities at this revision on these wrapped surfaces." Note that the assurance model deliberately avoids the word *guarantee*: these are tiers with claim boundaries |
| ☐ | **2. Which component enforces it?** | A named component. "The contract" enforces nothing. Either an in-process cooperative wrapper, or an external gateway, sandbox, or identity boundary — and if the answer is "nothing at run time", the claim is design-time only |
| ☐ | **3. What evidence proves it?** | Named artifacts with digests: a validated evidence report, a verified lock, a checker run, an approval record. And a statement of what each artifact binds, since a digest binds content rather than truth |
| ☐ | **4. What assumptions are required?** | At minimum: that the adapter was used; that the producer reported honestly; that no undeclared surface exists; that the repository history was reviewed; that the approver was who the record says |
| ☐ | **5. How can it be bypassed?** | Concretely. Calling the underlying callable directly. Reaching an unsupported surface. Editing a generated artifact without regenerating. Regenerating a lock without review. Adding a surface no inventory names |
| ☐ | **6. What happens when the enforcing component fails?** | Fail-closed or fail-open, and how you know. Verify that evaluation errors, recording errors, and malformed metadata all prevent the action rather than skipping the check |
| ☐ | **7. Which assurance tier does the claim support?** | Tier 1 for declarations, checks, locks, and verified approvals. Tier 2 for cooperative enforcement over declared surfaces, with the deny-path and evidence conditions met. Tier 3 only with an external enforcement and attestation system whose independence is established out of band. A system may hold several tiers on different surfaces at once |
| ☐ | **8. What remains unproven?** | The honest list. Producer honesty and evidence completeness. Distributed causality across systems. That no undeclared surface exists. That the approver was authenticated. That any policy was actually deployed. That the package is safe |

**Table G.1 — The eight questions as a claims review.** The exercise is not to make the answers
comfortable. It is to make them writable, so that a reader outside the team can tell what the
system establishes and what it does not.

## G.10 Reviewer's summary template

A review is finished when it can be stated in this shape.

> **Scope.** Contract `<path>` at revision `<git:…>`, profile `<name>`, modules `<list>`, adapter
> `<name>@<version>` against framework `<name>==<version>`, interface `<version>`.
>
> **Verified.** Contract validation passed at `--as-of <instant>`; profiles lock and network lock
> verified; generated artifacts drift-free; evidence stream validated strictly with zero
> diagnostics; the five per-surface tests pass for each wrapped surface; the deny path is
> demonstrated.
>
> **Tier claimed.** Tier 1 for the contract and its approvals; cooperative Tier 2 for the surfaces
> `<list>` only.
>
> **Residual risks accepted.** Bypass of the cooperative wrapper may leave no trace. Producer
> honesty and evidence completeness are unproven. Approvers are bound by declared role and
> revision, not authenticated. Unauthorised lock regeneration is detected by repository review, not
> by the lock. Authority ranking in contexts is advisory metadata.
>
> **Not claimed.** Independent or mandatory enforcement; complete coverage of agent actions;
> attestation of deployment; safety of any scanned package; compliance with, or certification
> against, any standard.

**Listing G.1 — A review summary the checklist supports.** Illustrative wording. The value is in
the fourth and fifth paragraphs: a review that omits them has not finished.
