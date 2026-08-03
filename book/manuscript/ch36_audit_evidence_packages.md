---
chapter: 36
part: VII
title: "Audit and Evidence Packages"
---

# Audit and Evidence Packages

> **Opening scenario.** Fourteen weeks after Atlas shared a research summary with an external partner, Northstar's internal audit function opens a review. The trigger is mundane — a rotation-schedule item, not an incident — but the auditor's first meeting goes badly. The Research & Insights lead offers a screenshot of a dashboard showing "approvals: 100% compliant" for the quarter, an export of log lines with no version information, and a sincere personal recollection that "Priya approved it, I was there." The auditor, who has done this before, writes one sentence on the whiteboard: *Under which exact revision of which policy was the share of 14 March authorized, by whom, bound to what, and what evidence supports each clause of that answer?* The room goes quiet, and then someone says the useful thing: everything in that sentence is a field name in an artifact we already have. The rest of this chapter is the fourteen days that follow, compressed.

> **Learning objectives.**
> - Formulate audit questions that are narrow, subject-revision-bound, and answerable from artifacts, and explain why "is the system compliant?" is not one of them.
> - Execute the seven-step reconstruction chain — contract, composition, lock, approval, events, artifacts, interpretation — and name the artifact and check that each step rests on.
> - Perform a full reconstruction of one governed decision, reading real-shaped artifacts at every step.
> - Write a defensible audit conclusion in which the scope and evidence boundary are part of the technical result.
> - Preserve failed evidence packages immutably and link remediation to a new revision rather than a repaired record.
> - Assemble an auditor-facing package with contents, a reading guide, and a claim register, and recognize the three anti-patterns that make packages worthless.

> **Prerequisites.** Chapter 9 (approvals as bound records), Chapter 11 (evidence versus logs; supplied versus observed), Chapter 12 (locks, digests, ordering, occurrence identity), Chapter 13 (tier claims and their scope), Chapter 20 (the evidence architecture in implementation), and Chapter 33 (incident reconstruction, which shares machinery with this chapter but not its purpose). Chapter 35 supplies the standards context an audit often serves. Status badges follow Chapter 16.

## 36.1 The audit-question discipline

An audit fails at the question, long before it fails at the evidence.

"Is the system compliant?" is not an audit question. It has no subject revision, no time interval, no defined evidence base, and no possible answer other than an opinion. The same is true of its politer variants — "are the controls effective?", "is the governance working?" — and of the vendor-questionnaire phrasing "does the platform provide full auditability?". Chapter 13 showed that an assurance claim without a scope is not a claim; the mirror-image rule is that an audit question without a scope is not a question.

A usable <span class="ix" data-ix="audit question">audit question</span> has four properties. It names a *decision or action class*, not a system. It is bound to an *exact subject revision*, because policy changes over time and an answer that averages over revisions answers nothing. It names a *time interval* evaluated at declared instants rather than at whatever clock the reviewer's laptop has. And it decomposes into *clauses that artifacts can discharge*, so that the auditor's product is a chain of checks rather than an impression.

The whiteboard sentence from the opening scenario has all four:

> Under contract revision `git:9f3c1a7…` of the Atlas research network, was the external share of summary `brief-2026-03-14` to the partner zone authorized; if so, under which approval, granted by which role of which actor type, bound to which revision, valid at which instant; and what evidence supports each clause?

This is answerable, and — just as important — *refusable*: for each clause there is a specific artifact whose absence or failure makes the honest answer "cannot be established from the available evidence," which is a finding, not a failure of the audit.

Two boundaries keep the discipline honest. First, an audit question about a cooperative Tier 2 system is a question about the *governed surfaces* named in a coverage inventory. The question "did anything else touch the partner?" is a different question at a different tier, and Chapter 13's rule applies: the absence of records is not evidence of the absence of action. A well-formed audit report states this in its scope, not in its footnotes. Second, the question binds to a revision even when the reviewer would rather it did not. "Was the share authorized under whatever policy was current at the time?" invites the reconstruction to drift onto today's policy, which is the single most common way an audit silently answers the wrong question.

> **Misconception.** *"Audit and incident response are the same activity with different urgency."* They share the reconstruction machinery of this chapter and Chapter 33, and they differ in the direction of inference. Incident response starts from an observed harm and searches for causes, accepting any evidence that narrows the search. Audit starts from a claim and tests whether the evidence supports it, accepting only evidence whose own provenance survives scrutiny. An artifact that is useful for the first can be inadmissible for the second — a log line with no revision binding can point an incident responder at the truth while proving nothing at all to an auditor.

## 36.2 The reconstruction chain

Answering a well-formed audit question is a <span class="ix" data-ix="reconstruction chain">chain of seven steps</span>, each of which consumes the output of the one before and each of which can fail independently. Figure 36.1 shows the chain; the rest of the chapter walks it.

<figure class="nx-fig" id="fig-36-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow">
        <div class="node authority">1 · Contract<br/>the reviewed declaration<br/>at the exact revision</div>
        <div class="arr">→</div>
        <div class="node">2 · Composition<br/>the effective governance<br/>after profiles and modules</div>
        <div class="arr">→</div>
        <div class="node">3 · Lock<br/>binding of source, packs,<br/>schemas, records, artifacts</div>
        <div class="arr">→</div>
        <div class="node">4 · Approval<br/>the bound human record<br/>and its validity checks</div>
      </div>
      <div class="flow">
        <div class="node">5 · Events<br/>the supplied runtime stream,<br/>validated against the lock</div>
        <div class="arr">→</div>
        <div class="node">6 · Artifacts<br/>referenced payloads verified<br/>by digest, in place</div>
        <div class="arr">→</div>
        <div class="node authority">7 · Interpretation<br/>the conclusion, with its scope<br/>and evidence boundary</div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 36.1 — The seven-step audit reconstruction chain.</b> Double borders mark the two normative ends: the chain starts from the authoritative declaration and ends in a human conclusion; everything between is mechanical verification. The teaching purpose is the dependency structure — each step certifies the inputs of the next, so a failure at step <em>n</em> does not merely weaken step <em>n</em>+1, it makes it meaningless: events validated against a stale lock are validated against nothing.</figcaption>
</figure>

The order is not decorative. Steps 1 through 3 establish *what the rules were*: the contract as reviewed, the governance actually in force after composition, and the proof that the artifact set under audit is the reviewed one. Steps 4 through 6 establish *what the record says happened*: the approval, the decision and action events, and the payloads those events reference. Step 7 is the only step performed by a human, and it is constrained by everything upstream — an interpretation may not claim more than the weakest link beneath it supports.

One structural fact makes the chain workable at all: every artifact in steps 3 through 6 carries the same <span class="ix" data-ix="binding tuple">binding tuple</span>. In the runtime-events schema, every single event is required to carry `network_id`, `contract_digest`, `network_lock_digest`, and `subject_revision`, and the validator compares each against the expected values with distinct diagnostics on mismatch **[implemented]**. The auditor is therefore never matching records to policies by timestamp proximity or filename convention — the records name their policy, exactly, or they fail validation.

> **Nornyx in practice.** The chain is not an abstraction imposed on the toolchain; the reference pipeline assembles it. The repository's reference continuous-integration script runs check, governance resolution, generation, a regenerate-and-byte-compare drift gate, lock build and lock-check, evidence validation in strict mode for both framework paths, and a governance explanation, then copies the lock, the generated artifacts, the evaluation report, both evidence reports, and the demonstration summary into an `audit-package/` directory with a manifest listing every file (`scripts/agentic_network_ci.py`; the manifest declares schema `nornyx.agentic_network_audit_package.v1`) **[implemented]**. What the script does *not* do is step 7: no interpretation is generated, because interpretation is the step that cannot be automated honestly.

## 36.3 A worked audit: the Atlas partner share

Thread A's signature review is the partner-share decision, and we now perform it end to end. The setting, fixed by the case bible and Chapters 7, 9, 11, and 17: Atlas may search, summarize, and file internally without a gate; the one-off share of a summary with an external partner required a human approval bound to the contract revision. The audit question is the whiteboard sentence of Section 36.1. All artifacts below are illustrative — built for this book, for a fictional enterprise — but their *shapes* are real: every field name is taken from the repository's schemas at the pinned snapshot, and each caption names the schema that fixes the shape.

**Step 1 — Contract.** The auditor obtains the contract at the revision named in the question, from repository history — not from anyone's working copy. The governing declarations are the approval requirement and the two trust zones:

```yaml
approvals:
  - name: partner_share_authority
    required_roles: [research_lead]
    eligible_roles: [research_lead, security_reviewer]
    denied_actor_types: [ai_tool, execution_surface, autonomous_agent, model, connector, generated_output]
    required_evidence: [approval_record, partner_share_review]
    required_for: [external_share]
    timing: before_action
    accountable_authority: research_lead
    revision_binding:
      kind: git
      revision: git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b
      exact: true
    invalidation_conditions: [revision_change, identity_change, capability_change, trust_zone_change]
    expires_at: "2026-03-21T00:00:00Z"
```

```yaml
agentic_network:
  trust_zones:
    - id: zone.research_internal
      classification: internal
      allowed_transition_targets: [zone.partner_channel]
      share_allowlist: [research_summary, evidence_digest]
      never_share: [customer_data, credentials, secrets, tokens, private_memory]
      ingress_gate_refs: []
      egress_gate_refs: [gate.partner_share_review]
    - id: zone.partner_channel
      classification: external_contract_only
      allowed_transition_targets: []
      share_allowlist: [research_summary]
      never_share: [customer_data, credentials, secrets, tokens, private_memory]
      ingress_gate_refs: [gate.partner_share_review]
      egress_gate_refs: []
```

**Listing 36.1 — The declarations under audit.** Illustrative; field names follow `schemas/agentic_network_v1.schema.json` (trust zones require a non-empty `never_share`; classifications come from a seven-value enumeration in which `external_contract_only` marks the partner side) and the approval shape follows the normalized approval model of Chapter 9. The reading matters: the share is *representable* — the internal zone lists the partner zone as a transition target and both allowlists carry `research_summary` — and it is *gated*, because the destination classification is external, which is what will force the approval at evaluation time.

The auditor's step 1 checks are that the contract at this revision parses, passes the checker deterministically, and contains these declarations. Nothing about behavior yet.

**Step 2 — Composition.** The contract alone is not the governance in force; profiles and modules compose into it, and composed denial lists include categories no document can remove. The auditor runs the read-only inspection command against the same revision and the same evaluation instant and reads the effective approval — the equivalent of Chapter 35's Listing 35.2 — confirming three things: `external_share` is in the actions requiring approval, the denied actor types include the full intrinsic non-human core unioned back regardless of declarations **[implemented]**, and the composition's source hashes allow the envelope to be replayed rather than trusted. Step 2 is where an entire class of audit error dies quietly: auditing the document instead of the composition misses every control a module added and every weakening a composition would have refused.

**Step 3 — Lock.** The lock ties the reviewed bytes together. The auditor obtains the lock file preserved with the evidence package and verifies it against the step 1 contract:

```json
{
  "schema": "nornyx.agentic_network_lock.v1",
  "lock_format_version": "1.0",
  "generation_format_version": "1.0",
  "network_id": "network.northstar_research",
  "subject_revision": "git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b",
  "source_contract_digest": "sha256:c41d8aa2…",
  "runtime_events_schema": {"id": "nornyx.agentic_runtime_events.v1", "version": "1.1"},
  "structural_checks": ["agentic_network_delegation.v1", "agentic_network_foundation.v1",
                        "evidence_integrity.v1", "human_approval.v1"],
  "approval_requirements": ["governance_authority", "partner_share_authority"],
  "records": {
    "agent_identities": [{"id": "identity.atlas", "digest": "sha256:7be2…"}],
    "trust_zones": [{"id": "zone.partner_channel", "digest": "sha256:20fa…"},
                    {"id": "zone.research_internal", "digest": "sha256:91c4…"}]
  },
  "artifacts": [{"path": "trust_zone_map.json", "sha256": "5d1e…"}]
}
```

**Listing 36.2 — Lock fields the auditor actually reads.** Illustrative and abridged; the field set follows `schemas/agentic_network_lock_v1.schema.json`, whose required fields additionally include the profile and module identities with content hashes, block schemas, protocol declarations, evidence requirements, and the full sorted per-record digest lists. Three fields do the audit work here: `subject_revision` is content-addressed (a branch name would have failed lock construction with `AN_LOCK_REVISION_MUTABLE`), `source_contract_digest` must match a digest recomputed from the step 1 contract (mismatch is `AN_LOCK_SOURCE_STALE`), and `runtime_events_schema` pins the evidence schema version that step 5 must match.

The check is mechanical — `lock-check` compares field by field and exits nonzero on any mismatch, with distinct codes for a stale source, a mismatched record digest, an artifact whose hash changed, an artifact missing, and an artifact present but not in the lock **[implemented]**. From this point on, "the policy" means these bytes, not anyone's memory of them.

**Step 4 — Approval.** The approval is the heart of this particular question. The preserved package contains the assertion that was presented at decision time, in the shape the authorization interface defines:

```json
{
  "approval_ref": "partner_share_authority",
  "claimed_approver_ref": "user:priya.n",
  "claimed_actor_type": "human",
  "role": "research_lead",
  "granted": true,
  "action_ref": "external_share",
  "subject_revision": "git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b",
  "issued_at": "2026-03-14T09:12:00Z",
  "expires_at": "2026-03-15T09:12:00Z",
  "evidence_refs": ["approval_record", "partner_share_review"]
}
```

**Listing 36.3 — The approval assertion as evaluated.** Illustrative; the field set is the `ApprovalAssertion` dataclass of the authorization interface (`nornyx/agentic/authz.py`) — `approval_ref`, `claimed_approver_ref`, `claimed_actor_type`, `role`, `granted`, `action_ref`, `subject_revision`, `issued_at`, `expires_at`, `evidence_refs`. The two "claimed" prefixes are the schema telling the auditor the truth about itself.

Against this record the auditor replays the engine's own checking order, documented in Chapter 9 and enforced in code **[implemented]**: the assertion's `subject_revision` equals the contract revision and the declared binding revision (else `APPROVAL_REVISION_MISMATCH`); `action_ref` is in scope (else `APPROVAL_ACTION_MISMATCH`); the actor type is human and not in the denied set (else `APPROVAL_NON_HUMAN` — "AI systems, tools, models, and execution surfaces cannot approve"); the role is eligible (else `APPROVAL_ROLE_INVALID`); the required evidence references are present (else `APPROVAL_EVIDENCE_MISSING`); the approval was temporally valid *at the decision instant* — not at audit time — (else `APPROVAL_STALE`); and `granted` is true. Every clause of the audit question's middle section is now discharged by a field.

**Step 5 — Events.** The preserved stream for mission `GOAL-RESEARCH-014` contains eight events; the four that carry the decision are:

```json
{"event_id": "GOAL-RESEARCH-014-0003", "event_type": "approval_requested",
 "mission_id": "GOAL-RESEARCH-014", "sequence": 3,
 "timestamp": "2026-03-14T09:11:42Z",
 "actor_ref": "identity.atlas", "approval_ref": "partner_share_authority",
 "network_id": "network.northstar_research",
 "contract_digest": "sha256:c41d8aa2…", "network_lock_digest": "sha256:88f0b3…",
 "subject_revision": "git:9f3c1a7d0b2e4f6a8c1d3e5f7a9b1c3d5e7f9a0b",
 "producer": {"type": "framework_adapter", "id": "crewai-adapter", "version": "0.2.0"},
 "occurrence": {"operation_id": "tool.partner_share", "occurrence_id": "task.14", "attempt": 1}}

{"event_id": "GOAL-RESEARCH-014-0004", "event_type": "approval_granted",
 "sequence": 4, "timestamp": "2026-03-14T09:12:03Z",
 "actor_ref": "identity.atlas", "approval_ref": "partner_share_authority",
 "approver": {"role": "research_lead", "actor_type": "human"}, "...": "…"}

{"event_id": "GOAL-RESEARCH-014-0005", "event_type": "trust_zone_crossed",
 "sequence": 5, "timestamp": "2026-03-14T09:12:04Z",
 "actor_ref": "identity.atlas",
 "source_zone_ref": "zone.research_internal", "target_zone_ref": "zone.partner_channel",
 "approval_ref": "partner_share_authority", "...": "…"}

{"event_id": "GOAL-RESEARCH-014-0006", "event_type": "data_shared",
 "sequence": 6, "timestamp": "2026-03-14T09:12:05Z",
 "actor_ref": "identity.atlas", "target_ref": "zone.partner_channel",
 "share_categories": ["research_summary"],
 "evidence_artifact": {"path": "artifacts/brief-2026-03-14.md",
                       "sha256": "e3b58a1c…"}, "...": "…"}
```

**Listing 36.4 — The decision events, abridged.** Illustrative; every field name is from `schemas/agentic_runtime_events_v1.schema.json` — `approval_granted` carries an `approver` object whose `actor_type` comes from a closed enumeration; `data_shared` carries `share_categories` and an `evidence_artifact` with `path` and `sha256`; the four binding fields repeat on every event; the elided fields (marked `"…"`) repeat the binding tuple, producer, and occurrence of the first event. The `attempt` is 1 and stays 1: this occurrence succeeded once, and a retry after success would have failed validation with `AN_EVT_ATTEMPT_AFTER_SUCCESS`.

The auditor does not eyeball this. The stream is fed to the validator with the step 3 lock, and the validator performs the full battery of Chapter 20: schema conformance against the exact version the lock pinned, the binding-tuple comparison on the envelope and on every event, per-type required fields, referential and temporal effectiveness of every referenced identity, capability, zone, and approval at each event's own timestamp, sequence contiguity from 1, non-decreasing timestamps, dependency ordering, paired transitions (a `data_shared` whose zone crossing never appeared would fail), replay fingerprints, and — specifically load-bearing here — the rule that an `approval_granted` approver must be of human actor type with a role inside the composed authority, checked as `AN_EVT_APPROVAL_NON_HUMAN` and `AN_EVT_APPROVAL_ROLE_INVALID` **[implemented]**. The result is a deterministic report: `status: pass`, `event_count: 8`, zero diagnostics, and — always — the embedded limitations block.

**Step 6 — Artifacts.** The `data_shared` event names the shared payload by path and digest. The validator has already resolved that path relative to the events file's own directory, refused any escape from it, and compared the hash (`AN_EVT_ARTIFACT_MISSING`, `AN_EVT_ARTIFACT_HASH_MISMATCH` on failure) **[implemented]**. The auditor opens `artifacts/brief-2026-03-14.md`, confirms independently that its SHA-256 matches, and reads it — because a digest proves these bytes are those bytes, and only a human can check that the bytes are a research summary rather than a customer list wearing one's filename. This single manual read is not a weakness of the chain; it is the chain working as designed, delivering exactly one artifact that needs human judgment instead of eight thousand log lines.

> **Case study — Atlas.** Fourteen days compress as promised. Days one and two: obtaining the artifacts, and discovering that the team's first instinct — re-running generation on today's contract — must be refused, because today's contract is two revisions ahead. Days three through five: steps 1–3, with one genuine finding — the lock preserved with the package verifies, but a second lock found on a developer's branch does not, and the branch copy is recorded and set aside precisely because the lock binds bytes, not authority to have written them. Days six through nine: steps 4 and 5, all checks passing. Day ten: step 6, the brief read and confirmed. Days eleven through fourteen: writing step 7, which takes four days not because the conclusion is unclear but because the *boundary* of the conclusion has to be negotiated with stakeholders who want it to say more.

## 36.4 What a defensible conclusion sounds like

Here is the <span class="ix" data-ix="defensible conclusion">conclusion</span> of the Atlas audit, in the form the auditor signs:

```text
CONCLUSION — Atlas partner share of 2026-03-14 (mission GOAL-RESEARCH-014)

Under contract revision git:9f3c1a7…, as composed with the governance packs
named in lock sha256:88f0b3… (verified against the source at that revision):

1. The external share of brief-2026-03-14 (sha256:e3b58a1c…) to
   zone.partner_channel was subject to approval requirement
   partner_share_authority for action class external_share.  [steps 1–3]
2. The supplied evidence stream, which validates with zero diagnostics
   against that exact lock, records an approval asserted for role
   research_lead, actor type human, bound to that exact revision, in scope
   for that action, temporally valid at the recorded decision instant,
   and granted — followed by the declared zone crossing and a share of
   category research_summary only.  [steps 4–5]
3. The shared artifact's content is digest-bound to the data_shared event
   and matches on independent recomputation.  [step 6]

SCOPE AND EVIDENCE BOUNDARY (part of the result):
- These conclusions cover the wrapped surfaces named in the adapter
  coverage inventory for this deployment, and no other path.
- The evidence is supplied by the runtime's recorder, not observed by an
  independent party. Validation proves conformance of the supplied
  records to the reviewed contract; it does not prove the records are
  complete, and an omitted event would not be detectable from this
  package. [Chapter 11; validator limitations block]
- The approver identity "user:priya.n" is a binding carried by the
  record, not an authenticated identity; no identity provider
  participated in this control.
- Accordingly: this audit establishes that the recorded share was
  authorized under the reviewed policy. It does not establish that no
  unrecorded share occurred.

Tier of the claims above: 1 for items resting on steps 1–3; 2,
cooperative and declared surfaces only, for items resting on steps 4–6.
```

**Listing 36.5 — A defensible audit conclusion.** Illustrative. Every numbered finding cites the steps it rests on; every sentence in the scope block is a technical statement traceable to a mechanism's documented limits, three of them to the limitations text the validator embeds in every report it emits **[implemented]**.

The point that separates professional work from theater is that the <span class="ix" data-ix="scope block">scope block</span> is *part of the result*, not a disclaimer softening it. A disclaimer is protective language about the author. The scope block is information about the system: it tells the reader precisely which further question would require which further mechanism — completeness needs an independent observer, approver identity needs an identity provider and a signing scheme, off-inventory paths need an enforcement point the workload cannot avoid. Deleting the block would not make the audit stronger; it would make it *wrong*, by transforming three true Tier 2 findings into one false Tier 3 finding. This is the same move Chapter 13 made for claims and Chapter 35 made for mapping rows, now performed at the end of the chain where it matters most, because an audit conclusion is the single artifact most likely to be quoted upward without its qualifiers.

This structure also connects cleanly to what external assurance frameworks expect. A service-organization examination is built from an explicit system description, criteria, the practitioner's tests of controls, and results — and its report is bounded by a defined period and a defined system, with complementary controls the reader's own organization must operate listed as such [@soc2]. An evidence package whose conclusions carry their scope, their producer assumptions, and their tier maps naturally onto that structure; a dashboard screenshot maps onto none of it. The connection is interpretive, not procedural: nothing here is or substitutes for such an examination, but an engineering team that practices this chapter's discipline will find the practitioner's requests familiar rather than alien.

## 36.5 Evidence preservation, failed packages, and remediation

The reconstruction chain assumed the artifacts were still there and still trustworthy fourteen weeks later. That is a property someone engineered.

The preservation rules are few and strict. An <span class="ix" data-ix="evidence package">evidence package</span> — contract, lock, effective-governance output, approval records, event streams, referenced artifacts, and validation reports — is written once, at the time of the run, and never modified. Storage is append-only from the perspective of every identity that produces evidence; Chapter 31's Ledger thread drew the `audit-store` zone that way, and Chapter 34's threat model explained why the recorder must not share a compromise domain with the actor it records. Packages are stored under the revision and lock digest they bind to, because that tuple is the only durable name they have.

The rule that gets tested organizationally is the one about failure. **A <span class="ix" data-ix="failed evidence package">failed package</span> is preserved exactly like a passing one.** When evidence validation fails — a sequence gap, a stale lock, an approval asserted by a non-human actor type — the report with its diagnostics is itself evidence, often the most valuable evidence the organization possesses, and the temptation to fix and re-emit the stream must be refused structurally, not just procedurally. A "repaired" evidence stream is a fabricated one: the validator's replay fingerprinting and ordering checks make many casual repairs detectable **[implemented]**, but the honest control is that nobody has write access to try. The failed package stays immutable; the *remediation* happens in the world — fix the producer, fix the contract, fix the process — and produces a new run, bound to a new or re-verified revision, whose package sits beside the failed one. The audit trail of a healthy governance program contains failures with successors, not a suspiciously unbroken row of passes. Chapter 16 made this point about the toolchain's own release history; it holds with more force for the evidence the toolchain validates.

<span class="ix" data-ix="evidence retention!by obligation class">Retention</span> follows obligation class, per Chapter 11: packages supporting regulatory record-keeping obligations inherit those horizons; packages supporting only internal claims inherit shorter ones; and the tension with data minimization — the package wants completeness, the privacy obligation wants absence — is resolved at production time by digest-binding payloads rather than embedding them, so the package can outlive the data it once described. Chapter 38 returns to what that trade genuinely costs.

## 36.6 Packaging for auditors, and the anti-patterns

An auditor-facing package is the evidence package plus two documents that exist only for the human on the other side.

| Worksheet column | Content for the Atlas audit |
|---|---|
| Question clause | e.g. "approval bound to the exact revision" |
| Chain step | 4 |
| Artifact | approval assertion in `approvals/GOAL-RESEARCH-014.json` |
| Check performed | field comparison against contract revision; engine order replayed |
| Mechanism and diagnostic on failure | `APPROVAL_REVISION_MISMATCH` **[implemented]** |
| Result | pass |
| What this does not establish | approver authentication; completeness of the stream |

**Table 36.1 — The audit worksheet, one row shown.** The full <span class="ix" data-ix="audit worksheet">worksheet</span> has one row per clause of the audit question — the Atlas audit produced eleven — and the last column is mandatory for every row. The worksheet is the auditor's working artifact and the package's best reading guide: a reviewer who disputes the conclusion can locate the exact row, artifact, and check they dispute.

The package contents, in the order a reader should meet them: a <span class="ix" data-ix="reading guide">*reading guide*</span> (one page: the question, the revision, the chain, where each step's artifacts live, and the order to read them); the <span class="ix" data-ix="claim register!in audit packages">*claim register*</span> for the claims the audit tested — claim, tier, surfaces, evidence, "not claimed" list, in Chapter 13's format; the *worksheet* (Table 36.1, all rows); then the artifacts themselves — contract, lock, composition output, approvals, streams, referenced payloads, validation reports — each named by digest; and finally the signed conclusion of Section 36.4. The reference pipeline's generated `audit-package/` directory with its manifest is the mechanical skeleton of this **[implemented]**; the reading guide, worksheet, register, and conclusion are the human flesh on it, and no tool emits them.

Three <span class="ix" data-ix="auditor anti-pattern">anti-patterns</span> account for most worthless packages.

**<span class="ix" data-ix="dashboard screenshot (anti-pattern)">The dashboard screenshot</span>.** A screenshot is an unversioned, unproducered, unbounded image of a mutable view. It answers no clause of any well-formed question: no revision, no digest, no producer, no validation. Its seductiveness is that it *looks* like evidence while being precisely the opposite — a rendering of whatever the dashboard's query returned at an unrecorded moment against unrecorded data. The repair is not a better screenshot; it is the underlying records, bound and validated.

**<span class="ix" data-ix="unversioned export (anti-pattern)">The unversioned export</span>.** One step better and still inadmissible: real records, exported without the tuple that makes them checkable — no subject revision, no contract digest, no lock, no schema version. Chapter 16 called an unpinned claim "a claim about nothing in particular"; an unversioned export is evidence of nothing in particular. The tell is a filename like `events_final_v2.json`. The structural fix is the one the event schema hardwires: records that carry their bindings *internally*, so that an export cannot shed them **[implemented]**.

**<span class="ix" data-ix="producer assumptions!outrun by conclusions">The conclusion that outruns its producer assumptions</span>.** The subtlest and the most damaging: a package whose artifacts are impeccable and whose summary sentence claims what the producers cannot support — "the evidence shows no unauthorized shares occurred," resting on records supplied by the very runtime under question. Every artifact is genuine; the inference is not. This is Chapter 34's overclaiming vulnerability in its final habitat, and the defense is mechanical: every concluding sentence must trace to worksheet rows, and no sentence may exceed the weakest "does not establish" cell among the rows it cites.

> **Assurance boundary.** The eight questions, applied to the audit itself. *What is guaranteed*: that the conclusions of Section 36.4 follow from artifacts that validate against the exact reviewed revision. *Which component enforces it*: none — an audit is an argument; the validator and lock-checker enforce only the premises. *What evidence proves it*: the package, whose every artifact is digest-named. *Assumptions*: honest producers, controlled repository history, preserved packages. *Bypass*: act outside the wrapped surfaces, and the audit never sees you. *On failure*: a broken chain step downgrades every dependent finding to "cannot be established" — visibly, not silently. *Tier*: the audit's findings inherit the tiers of the mechanisms beneath them, never exceed them. *Unproven*: completeness, producer identity, and everything off-inventory — which is why those three sentences are printed inside the conclusion.

## Summary

Audits fail at the question first: a usable audit question names a decision class, binds to an exact subject revision, fixes a time interval, and decomposes into clauses that artifacts can discharge. Answering one is a seven-step chain — contract, composition, lock, approval, events, artifacts, interpretation — in which each step certifies the next's inputs, every artifact carries the same binding tuple, and only the final step is human. Worked against the Atlas partner share, the chain runs from the approval and zone declarations at the pinned revision, through the composed effective approval with its intrinsic non-human denials, the field-by-field lock verification, the replayed approval-checking order, strict validation of the event stream, and digest verification of the shared payload, to a signed conclusion. A defensible conclusion carries its scope and evidence boundary as part of the technical result: supplied-not-observed, binding-not-authentication, inventory-not-application are statements about which further mechanism would answer which further question, and deleting them changes true Tier 2 findings into a false Tier 3 one. Failed packages are preserved immutably, with remediation expressed as a new run against a new revision, never as a repaired record. The auditor-facing package adds a reading guide, a claim register, and a worksheet whose final column — "what this does not establish" — is mandatory; the anti-patterns it defends against are the dashboard screenshot, the unversioned export, and the conclusion that outruns its producers.

- "Is the system compliant?" is an opinion request; a real audit question is revision-bound and clause-decomposable.
- Every event names its policy by digest; auditors never match records to rules by timestamp proximity.
- Audit the composition, not the document; audit the preserved lock, not today's regeneration.
- The scope block is information about the system, not protection for the author.
- A failed validation report is evidence; a repaired stream is a fabrication.
- No concluding sentence may exceed the weakest "does not establish" cell it rests on.

## Review questions

1. Rewrite "is Atlas compliant with our sharing policy?" as a well-formed audit question with all four properties of Section 36.1, then list the artifact that discharges each clause.
2. Steps in the reconstruction chain fail independently. For each of steps 2, 3, and 5, give a concrete failure, its diagnostic where one exists, and state exactly which of the Atlas conclusion's three findings survive it.
3. Why must the auditor refuse to regenerate artifacts from the current contract, even when regeneration is deterministic? Name the two distinct errors that regeneration would introduce.
4. The conclusion in Listing 36.5 says the audit "does not establish that no unrecorded share occurred." Which single architectural change would allow a future audit to establish it, at which tier, and what new producer assumption would that audit inherit instead?
5. A colleague proposes deleting failed evidence packages after remediation "to avoid confusing future reviewers." Give the strongest version of their argument, then defeat it using both Section 36.5 and Chapter 16's release-history lesson.
6. For each of the three anti-patterns, identify which chain step it counterfeits and which worksheet column would have exposed it.

## Exercises

1. **Run the chain on your own system.** Choose one consequential governed decision from the last quarter and attempt the seven steps with whatever artifacts exist. Record, per step: artifact found or missing, check performable or not, and the diagnostic or gap. Your deliverable is the honest worksheet, including empty rows — the empty rows are the finding.
2. **Write the conclusion twice.** For the reconstruction in Exercise 1, write the strongest conclusion your evidence supports, with a full scope block; then write the overclaimed version a hurried executive summary would produce. Diff them sentence by sentence and, for each difference, name the producer assumption or coverage fact the overclaim ignores.
3. **Design the preservation policy.** Specify, for your organization: where evidence packages live, under what naming tuple, who can write (and prove why no evidence producer can rewrite), how failed packages are marked and linked to their remediating successors, and the retention horizon per obligation class. Then test it: pick one package from six months ago and perform steps 3 and 5 of the chain against it today.

## Further reading

- [@soc2] — how independent practitioners structure system descriptions, control tests, and bounded opinions; the closest external counterpart to this chapter's package discipline, and the reason its vocabulary will feel familiar to your auditors.
- [@in-toto] — supply-chain layouts and link metadata as a formalization of "every step certifies the next's inputs"; the reconstruction chain is the same idea applied to decisions rather than builds.
- [@merkle] — the primitive underneath every digest check in this chapter; worth reading once to understand exactly what a hash tree does and does not bind.
- [@lamport-clocks] — why timestamps from different producers cannot order events, and what declared causal references buy; the theoretical floor under step 5's ordering checks.
- [@sre-book] — the postmortem culture chapters; incident reconstruction as the sibling discipline whose evidence standards differ from audit's for principled reasons.
