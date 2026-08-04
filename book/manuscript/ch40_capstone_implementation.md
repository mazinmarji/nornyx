---
chapter: 40
part: VIII
title: "Capstone: Implementation, Verification, and Assurance Review"
---

# Capstone: Implementation, Verification, and Assurance Review

> **Opening scenario.** The design of Chapter 39 is signed. Northstar's platform team now has three weeks to a review board that will contain one skeptic by design: the Risk & Audit chief has told her deputy to "assume the register is wrong and make them prove otherwise." The team's plan reflects the book they have implicitly been following. Week one: build the artifact set and make every gate green. Week two: *break it* — eight deliberate failures, each aimed at one claimed boundary, each expected to stop at a named diagnostic, with the evidence preserved as if each were a real incident. Week three: sit the three most consequential claims down with the eight questions, and reconstruct one high-value decision end to end the way an auditor would, before an auditor does. "Green pipelines," the architect tells the team, "are the *least* interesting deliverable. The board is buying the red ones."

> **Learning objectives.**
> - Assemble the complete Northstar artifact set — contracts, generated artifacts, locks, adapter wiring, and pipeline gates — as one integrated build with real transcripts.
> - Wire one tool surface and one graph node through the supported adapter interfaces, and state precisely what was executed versus what is repository-tested.
> - Run a failure-injection programme: eight deliberate failures, each mapped to the boundary that stops it, its diagnostic family, the evidence to preserve, and the assurance lesson.
> - Produce a verification matrix that ties every register claim to its verifying mechanism and transcript.
> - Apply the eight questions to the three most consequential claims, and reconstruct a high-value decision end to end using Chapter 36's method.

> **Prerequisites.** Chapter 39 (the design, inventory, tier table, and claim register this chapter implements and attacks), Chapters 17–21 (language, locks, the authorization service provider interface (SPI), evidence, drift), Chapters 22–25 (adapters and coverage), Chapter 15 (negative controls and failure injection), Chapter 36 (audit reconstruction). All transcripts in this chapter were produced against the pinned snapshot, distribution 1.11.0, in a working directory laid out exactly as Listing 39.1 describes.

## 40.1 The build: one integrated artifact set

The build proceeds source-first, in the order the artifacts depend on one another: contracts, then workspace verification, then generated artifacts, then locks, then runtime wiring, then the pipeline that re-checks all of it on every change.

The three application contracts check clean against their composed governance. Atlas and Forge are v0.1 delivery contracts in the shape of `examples/governed_delivery_control_plane.nyx`; Ledger is a v0.2 agentic-network contract in the shape of `examples/agentic_network_support/support_network.nyx`, with the identities, capabilities, zones, delegation, and handoff of Table 39.1, pinned to subject revision `git:b5e91c4e0b4d2c8f6a1b3d5e7f9a0c2e4b6d8f01`. Building it produced the design lesson reported in Section 39.6, and the transcript, Listing 40.1, is worth showing because it is the first time in this book a *checker* has corrected an *organization chart*:

```text
$ nornyx check treasury-ledger/ledger.nyx --as-of 2026-08-03T00:00:00Z
{ "level": "error", "code": "AN_APPROVAL_DECLARED_ROLE_UNAUTHORIZED",
  "message": "Document approval roles are absent from the composed module
              authority: treasury_officer.", "path": "approvals[0].required_roles",
  "source_id": "agentic_network_foundation.v1" }
{ "level": "error", "code": "AN_APPROVAL_MODULE_ROLE_OMITTED",
  "message": "Document approval requirements omit module-required roles:
              network_governance_owner.", ... }
# ...after mapping the treasury officer onto network_governance_owner:
$ nornyx check treasury-ledger/ledger.nyx --as-of 2026-08-03T00:00:00Z
Nornyx check passed
```

**Listing 40.1 — The composed module authority correcting the draft.** Real output (abridged) from building the Ledger contract. A document cannot widen the role set fixed by the composed `agentic_network_governance` module **[implemented]**; the fix was organizational — assign the module's role to the right person — not mechanical.

With all three contracts green, the org gate confirms the Charter property: `nornyx workspace-check --manifest nornyx.workspace.yaml` reports `"status": "pass"` with every member's `NorthstarBaseline` `ok`, exit 0. Generation and locking then follow for each application. For Forge, `nornyx generate` writes the full artifact set — `AGENTS.md`, `policy.yaml`, `context.yaml`, `harness.yaml`, `evals.yaml`, `trace.yaml`, `goals.yaml`, per-skill READMEs, the evidence contract, and the hash-bearing generation manifest — and `nornyx drift` passes against the committed output. For Ledger, the agentic-network generator and <span class="ix" data-ix="network lock!capstone build">lock</span> produce the capstone's most consequential Tier 1 artifacts (Listing 40.2):

```text
$ nornyx agentic-network generate ledger.nyx --out generated/agentic_network \
    --as-of 2026-08-03T00:00:00Z --json
{ "status": "pass", "out": "generated/agentic_network", "artifact_count": 10,
  "artifacts": ["a2a_declaration.json", "agentic_generation_manifest.json",
   "capability_matrix.json", "delegation_policy_bundle.json",
   "handoff_manifest.json", "identity_manifest.json",
   "mcp_capability_declaration.json", "network_manifest.json",
   "runtime_evidence_contract.json", "trust_zone_map.json"] }

$ nornyx agentic-network generate ledger.nyx --out /tmp/regen_an \
    --as-of 2026-08-03T00:00:00Z && diff -r /tmp/regen_an generated/agentic_network
# (no output — byte-identical regeneration)

$ nornyx agentic-network lock ledger.nyx --artifacts generated/agentic_network \
    --as-of 2026-08-03T00:00:00Z --json
{ "status": "pass", "lock_path": "nornyx.agentic_network.lock",
  "lock_digest": "sha256:44f0cfb0928bf4385538232276707109d9f4d29c7855f04fe91b6fc6c4b48dc5",
  "artifact_count": 10 }
```

**Listing 40.2 — Generation, determinism, and the network lock.** Real transcripts from the capstone build. The ten timestamp-free artifacts regenerate byte-identically; the lock binds contract digest `sha256:70119e93…`, the subject revision, the composed packs (`agentic_network` 0.1.0 profile; `agentic_network_governance` 0.2.0, `evidence_integrity` 1.0.0, and `human_approval` 1.0.0 modules), four structural-check identities, runtime-events schema 1.1, per-record digests for all ten record collections, and per-artifact SHA-256 hashes — the binding structure of Chapter 18, now populated with Northstar's own content.

The lock's `records` section doubles as a machine-checked census of the design: 4 agent identities, 7 capabilities, 3 trust zones, 4 memberships, 2 network gates, 1 protocol target, 1 delegation, 1 handoff, 4 relations, 0 revocations — exactly Table 39.1.

The <span class="ix" data-ix="pipeline gate!capstone">pipeline</span> that holds the build honest is a straight instantiation of the reference continuous-integration (CI) pattern (`scripts/agentic_network_ci.py`, Chapter 29): per-repo, `nornyx check` with a pinned `--as-of`, `nornyx drift` (Forge, Atlas) or generate-and-byte-compare plus `lock-check` (Ledger), and `workspace-check` in every member pipeline; each gate blocks on its documented exit code, with lock and parse failures exiting 2 rather than 1 **[implemented]**. The gates need no secrets and no network — a property inherited from the toolchain rather than engineered here. Figure 40.1 lays the gates out in dependency order.

<figure class="nx-fig" id="fig-40-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow">
        <div class="node">contract change</div>
        <div class="arr">→</div>
        <div class="node">nornyx check --as-of ✋</div>
        <div class="arr">→</div>
        <div class="node">workspace-check ✋</div>
        <div class="arr">→</div>
        <div class="node">drift / regenerate+compare ✋</div>
        <div class="arr">→</div>
        <div class="node">lock-check ✋</div>
        <div class="arr">→</div>
        <div class="node">merge lane</div>
      </div>
      <div class="flow">
        <div class="node">runtime evidence</div>
        <div class="arr">→</div>
        <div class="node">evidence-validate --strict ✋</div>
        <div class="arr">→</div>
        <div class="node">audit-store 📄</div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 40.1 — The capstone gate pipeline.</b> Top row: the change-time gates, in dependency order, each blocking on its documented exit code (1 for governance failures, 2 for parse, lock, and <code>--as-of</code> failures). Bottom row: the evidence lane, which runs per mission rather than per change and files both stream and validation report. The teaching purpose is that every gate here is exercised in red at least once by the failure programme of Section 40.4 — a pipeline whose gates have never fired is a pipeline whose gates are untested.</figcaption>
</figure>

## 40.2 Adapter wiring: one tool surface, one graph node

The runtime touchpoints use the supported adapter package, `nornyx-agentic-adapters` 0.2.0, and this section is precise about what was executed here versus what is repository-tested, because that distinction *is* the coverage discipline of Chapter 14.

For Atlas's tool surface, the wiring target is the CrewAI adapter's `make_governed_tool` **[implemented]**: it validates a `SurfaceBinding(surface, identity_ref, capability_ref)`, constructs a `BaseTool` subclass whose synchronous `_run` evaluates a `CapabilityRequest` through `enforce()` before the wrapped action, and records a `tool_invoked` observation only after the action returns; any non-allow decision raises `AdapterDenied` carrying the core `Decision` (`adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/crewai_adapter.py`). For Ledger's graph nodes, the target is `make_governed_node` **[implemented]**: it maps the declared surface to the operation, LangGraph's public `task_id` to the occurrence, and the one-based `node_attempt` (offset by the validated recorder prefix after a checkpoint resume) to the attempt, and it refuses coroutine actions at construction (`.../langgraph.py`). Both adapters were built and tested in the repository against the exact pinned frameworks — CrewAI `==1.15.4` and LangGraph `==1.2.2` — with continuous-integration jobs that fail closed if any framework test is skipped **[implemented]**.

The capstone build environment has neither framework installed, and the adapter package says so in the fail-closed style the design expects:

```text
>>> from nornyx_agentic_adapters.crewai_adapter import make_governed_tool
MissingOptionalDependencyError: 'crewai.tools' is not installed. Install it
with 'pip install nornyx-agentic-adapters[crewai]'.
>>> from nornyx_agentic_adapters.langgraph import make_governed_node
MissingOptionalDependencyError: 'langgraph.runtime' is not installed. Install
it with 'pip install nornyx-agentic-adapters[langgraph]'.
```

What *can* be executed here — and matters more, because it is the object both framework wrappers delegate to — is the enforcement boundary itself. `enforce()` is the package's single evaluate → record → execute sequence: it evaluates the request, records the decision's event intents, raises `AdapterDenied` on any non-allow, and only then runs the action exactly once (`.../enforcement.py`). Listing 40.3 wires it against the real Ledger authorizer and lock, with a <span class="ix" data-ix="side-effect ledger">side-effect ledger</span> as the proof of prevention, in the method of the repository's A/B benchmark (Chapter 23).

```python
authz = load_authorizer("ledger.nyx", "nornyx.agentic_network.lock",
                        validation_as_of="2026-08-03T00:00:00Z")
ctx = EvaluationContext(decision_at="2026-08-03T10:00:00Z",
                        observed_subject_revision=REV)
rec = EvidenceRecorder(authz, ctx, producer_id="northstar-ledger-adapter",
                       producer_type="synthetic_harness")
ledger = []                                    # side-effect ledger

b = SurfaceBinding(surface="tool.compute_exposure",
                   identity_ref="identity.analyst",
                   capability_ref="analyze.exposure")
validate_binding(b)
result = enforce(authz, CapabilityRequest(b.identity_ref, b.capability_ref),
                 context=ctx, recorder=rec, mission_id="GOAL-LEDGER-001",
                 action=compute_exposure)
```

```text
nornyx-agentic-adapters 0.2.0
ALLOW -> {'exposure_eur': 61250} | ledger: ['exposure_computed']
DENY  -> AdapterDenied CAPABILITY_DENIED | ledger: ['exposure_computed']
         <- unchanged; the callable never ran
evidence: pass | events: 5 | diagnostics: 0
counts: {"capability_allowed": 1, "capability_denied": 1,
         "capability_requested": 2, "tool_invoked": 1}
```

**Listing 40.3 — The enforcement boundary, executed.** Real code and output: the allowed analyst call runs exactly once and appends to the side-effect ledger; the executor's `payment.submit` attempt raises `AdapterDenied` with `CAPABILITY_DENIED` and the ledger is untouched — the denial is proven by the absence of the effect, not by the presence of an exception. The five-event stream validates `pass` against the lock. `SurfaceBinding`, `validate_binding`, `enforce`, and `AdapterDenied` are the real interfaces from `nornyx_agentic_adapters` 0.2.0; the framework-specific wrappers add framework plumbing around exactly this sequence.

## 40.3 The governed run: decisions and evidence

Before breaking anything, the build demonstrates the full decision surface with an <span class="ix" data-ix="occurrence!explicit mode">explicit-occurrence</span> recorder (`EvidenceRecorder.for_occurrences`, runtime-events 1.1) driving one mission through every request type of the authorization SPI. The transcript is the capstone's positive baseline; every failure in Section 40.4 is a perturbation of it.

```text
SPI 1.2  network network.treasury_exceptions
resolve crewai/planner    -> identity.planner
resolve langgraph/analyst -> identity.analyst
read.exception_case                   : effect=allow  code=ALLOWED
delegation.exposure_analysis          : effect=allow  code=ALLOWED
analyst analyze.exposure (delegated)  : effect=allow  code=ALLOWED
    basis: [('delegation', 'delegation.exposure_analysis')]
executor payment.draft                : effect=allow  code=ALLOWED
executor payment.submit (not held)    : effect=deny   code=CAPABILITY_DENIED
crossing plan->payment_exec (no appr) : effect=approval_required
                                        code=CROSSING_APPROVAL_REQUIRED
crossing with human approval          : effect=allow  code=ALLOWED
AI-claimed approval                   : effect=deny   code=APPROVAL_NON_HUMAN
    reason: AI systems, tools, models, and execution surfaces cannot approve.
approval bound to superseded revision : effect=deny   code=APPROVAL_REVISION_MISMATCH
share credentials to payment_exec     : effect=deny   code=SENSITIVE_SHARING
    reason: Sensitive categories are never shareable: credentials.

evidence validation: pass  events: 19  missions: 1  diagnostics: 0
```

**Listing 40.4 — The positive baseline.** Real output from the capstone harness against the Ledger contract and lock. Note the three-valued decision domain in action: `payment.submit` *denies* because no membership holds it, while the zone crossing returns `APPROVAL_REQUIRED` — a distinct effect that the wrapper surfaces as a denial with a request for exactly the missing thing. The delegated allowance carries its `delegation_ref` in the decision basis, which the recorder stamps into the `capability_allowed` event.

Figure 40.2 renders the high-value scene — the crossing into `payment-exec` for the €61,250 adjustment — as a sequence, because it is the decision Section 40.5 reconstructs. One honest caveat belongs next to it. Ledger's design (Table 31.1) requires *two* human approvals above €50,000 — a treasury officer and a risk officer — but the composed module fixes the approval role set, and the demonstration records a single assertion in the role it permits, `network_governance_owner`. The second officer is therefore a procedural control in this run, invisible to the recorded evidence, and the claim register carries that gap as a residual rather than letting the single recorded approval imply the full dual-control design was exercised.

<figure class="nx-fig" id="fig-40-2">
  <div class="fig-body">
    <div class="seq">
      <div class="seq-cols" data-cols="Executor node|Adapter (enforce)|Authorizer|Recorder|Treasury officer (human)"></div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">crossing: treasury_plan → payment_exec</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">ZoneCrossingRequest (no approval)</div>
      <div class="msg" data-from="3" data-to="2" data-kind="deny">APPROVAL_REQUIRED · CROSSING_APPROVAL_REQUIRED</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record approval_requested intent</div>
      <div class="msg" data-from="1" data-to="5" data-kind="call">approval package (amount, policy, evidence, revision git:b5e91c4…)</div>
      <div class="msg" data-from="5" data-to="1" data-kind="return">signed, revision-bound, expiring approval record</div>
      <div class="msg" data-from="1" data-to="2" data-kind="call">crossing retried with ApprovalAssertion</div>
      <div class="msg" data-from="2" data-to="3" data-kind="call">ZoneCrossingRequest + assertion</div>
      <div class="msg" data-from="3" data-to="2" data-kind="return">ALLOW (basis: approval, gate)</div>
      <div class="msg" data-from="2" data-to="4" data-kind="call">record approval_granted (actor_type human) + crossing events</div>
    </div>
  </div>
  <figcaption><b>Figure 40.2 — The high-value crossing, end to end.</b> The first attempt returns <code>APPROVAL_REQUIRED</code> rather than deny — the engine names the missing control. The human decision happens entirely outside the toolchain; what returns is an assertion the engine verifies in a fixed order: revision binding, declared binding, action scope against the gate's action classes, non-human rejection, role authority, required evidence, temporal validity, granted. The teaching purpose is that the human is on the sequence diagram as a first-class participant with an artifact, not as an annotation.</figcaption>
</figure>

> **Case study — Gateway.** Thread D closes its decision table with capstone numbers. Path 1 (framework-native, ungoverned): the refund/adjustment callable runs, nothing is evaluated, nothing is recorded. Path 2 (wrapped): Listing 40.3 — evaluated, recorded, denied with zero side effects. Path 3 (bypass under the wrapper): Section 40.4, injection F6 — the callable runs and the governance layer is silent. Path 4 (mandatory gateway): still **[extension]**, and the only path whose row in the table could ever claim Tier 3. Same workload, four assurance positions — the thesis of Figure 13.2, now with transcripts in three of the four rows.

## 40.4 The failure-injection programme

<span class="ix" data-ix="failure injection!capstone programme">Failure injection</span> is the register's trial by ordeal: each injection targets one claimed boundary, and the deliverable per injection is fourfold — the boundary that stopped it (or, in one deliberate case, did not), the diagnostic family, the evidence to preserve, and the assurance lesson. The programme extends the prior edition's table with the same eight scenarios, now run rather than described. Table 40.1 summarizes; the numbered subsections carry the transcripts.

| # | Injection | Boundary that responds | Diagnostic family (observed) | Assurance lesson |
|---|---|---|---|---|
| F1 | Hand-edit a generated artifact (`policy.yaml`) | Full-output drift gate | `nornyx.repo_drift_report.v0.1`: `policy.yaml` `changed`, exit 1 | Derived files hold no independent authority |
| F2 | Approval bound to a superseded revision | Authorization engine; static check; `--as-of` freshness | `APPROVAL_REVISION_MISMATCH`; `AN_APPROVAL_EXPIRED`, `EVIDENCE_STALE` | Human intent binds to an exact candidate, and decays |
| F3 | Ambiguous framework identity | Static check; authorizer load; identity resolution | `AN_IDENTITY_BINDING_DUPLICATE`; `AuthorizerLoadError CONTRACT_INVALID`; `IDENTITY_UNKNOWN` | Governance identity is never guessed |
| F4 | Replay an event with only a new timestamp | Evidence validator (explicit-mode fingerprint) | `AN_EVT_REPLAY`, strict exit 1 | Transport restamping does not create new work |
| F5 | Asynchronous call on an unsupported surface | Coverage inventory; inherited fail-closed behavior | `unsupported` inventory entry; no coverage claim, no event | Sync coverage never implies async coverage |
| F6 | Direct function call beneath the wrapper | **None** — by design | No diagnostic; no record | Tier 2 requires the qualifier or an external policy enforcement point (PEP) |
| F7 | Hostile tool bundle with install hook | Package scanner + approval gate | Hook/MCP/command/claim-mismatch findings; `risk_tier: critical` | Package claims are untrusted input |
| F8 | Evidence artifact path escaping its package | Evidence validator path containment | `AN_EVT_ARTIFACT_MISSING` (with schema rejection) | Supporting bytes stay inside the bounded package |

**Table 40.1 — The failure-injection programme.** Every diagnostic in the third column was observed in this build except F5's, which is repository-tested (the capstone environment installs no frameworks); the F5 row's evidence is the declared inventory plus the repository's own fail-closed test. F6 is the programme's control: the row where the correct result is *no response*, and the claim register — not a gate — is what has to absorb it.

**F1 — Hand-edited generated artifact.** A platform engineer "fixes" the committed `payments-api/.nornyx/policy.yaml` directly, deleting `deny destructive_schema_change`. The injection first confirms the trap the tool's own history warned about: the regenerated `AGENTS.md` is byte-identical to the committed one, so any gate that diffs only `AGENTS.md` stays green — precisely the under-checking defect Nornyx's multi-repo case study found in its own recommended gate and fixed in 1.1.6. The full-output gate is not fooled: `nornyx drift payments-api/forge.nyx --out payments-api/.nornyx` reports every artifact `ok` except `"path": "policy.yaml", "status": "changed"` and exits 1. *Evidence to preserve:* the drift report JSON, the git diff of the edited artifact, and the generation manifest whose per-artifact hashes date the divergence. *Lesson:* generated artifacts are projections, not sources; an edit to one is not a policy change but a forgery of one, and the gate that catches it must compare everything the generator writes.

**F2 — Approval bound to a superseded revision.** The Forge scene from the case-study bible: an approval is granted against `git:9f3c1a7…`, then the branch is force-pushed. At the engine, an `ApprovalAssertion` whose `subject_revision` names any other revision is rejected before actor-type, role, or expiry are even examined — `APPROVAL_REVISION_MISMATCH`, "Approval subject_revision does not match the contract subject_revision" (Listing 40.4) — because revision binding is the *first* check in the engine's fixed order **[implemented]**. The same boundary exists statically (`AN_REVISION_MISMATCH` against the declared binding) and temporally: re-running `nornyx check --as-of 2026-08-11T00:00:00Z`, one day past the approval's expiry, fails with `AN_APPROVAL_EXPIRED` and `EVIDENCE_STALE`, while a malformed `--as-of` fails closed with `AS_OF_INVALID` at exit 2 rather than silently using the live clock. *Evidence to preserve:* the denial's decision record and `approval_rejected` event, the original approval artifact with its hash, and both revisions' identifiers. *Lesson:* approval is consent to *bytes*, not to a branch name; anything that changes the bytes must orphan the consent, automatically.

**F3 — Ambiguous framework identity.** A copy-paste error gives two Ledger identities the same `{framework: crewai, agent_key: planner}` binding. The static layer refuses the contract outright — `AN_IDENTITY_BINDING_DUPLICATE`, "Framework binding ('crewai', 'planner') is duplicated" — so `load_authorizer` fails closed with `AuthorizerLoadError` at stage `CONTRACT_INVALID` and no authorizer exists to consult. On a healthy contract the same boundary appears at resolution time: `resolve_identity("crewai", "rogue_agent")` and `resolve_identity("autogen", "planner")` both raise `IdentityResolutionError` with `IDENTITY_UNKNOWN`, and a genuinely ambiguous key would raise `IDENTITY_AMBIGUOUS` — resolution errors are deliberately not policy decisions, so nothing is recorded as denied; the call simply cannot be attributed **[implemented]**. *Evidence to preserve:* the checker diagnostics and the adapter's configuration error, with the contract revision. *Lesson:* a governance identity is a binding, not a guess; when attribution is uncertain the system must stop rather than pick a plausible identity — the confused-deputy door stays shut from the inside.

**F4 — Replay with only a changed timestamp.** The injection duplicates the delegated `capability_allowed` event from the baseline stream, giving the copy a fresh `event_id`, the next `sequence`, and a timestamp five seconds later — everything a naive dedup keys on is new. Validation fails: `AN_EVT_REPLAY`, "Event content replays an earlier event," strict exit 1. The mechanism is Chapter 20's <span class="ix" data-ix="replay detection!content fingerprint">content fingerprint</span>: in explicit occurrence mode the fingerprint excludes `event_id`, `sequence`, *and* `timestamp`, precisely so that "a producer cannot evade exact replay detection merely by restamping a duplicate with a new timestamp" **[implemented]** (`nornyx/agentic_evidence.py`); identical work legitimately repeated must claim a new occurrence or attempt, which changes the fingerprint honestly. *Evidence to preserve:* the failing stream and its validation report — the report embeds its own limitations block, which the incident record should quote rather than paraphrase. *Lesson:* semantic identity, not transport identity, is what evidence dedup must key on.

**F5 — Unsupported asynchronous call.** An Atlas integrator "optimizes" by calling the governed tool's asynchronous path. The CrewAI adapter's <span class="ix" data-ix="coverage inventory!unsupported surface">coverage inventory</span> declares `async_tool_invocation` **unsupported**: the adapter overrides only the synchronous `_run`, the inherited `_arun` raises, "the wrapped action never executes and no `tool_invoked` observation is recorded" — behavior the repository proves against the real pinned framework in `test_async_arun_fails_closed_and_records_nothing` **[implemented]**. The capstone environment installs no frameworks, so this row's local evidence is the machine-readable inventory itself plus the repository test; the claim register already scoped NS-ATLAS-001 to the wrapped synchronous surface, so no claim needs qualifying — which is the point. *Evidence to preserve:* the inventory (`COVERAGE_INVENTORY.as_dict()`), the adapter version, and the framework pin. *Lesson:* a surface that produces no coverage claim must fail loudly rather than succeed silently; "unsupported" is a designed behavior, not a gap discovered later.

**F6 — <span class="ix" data-ix="bypass!direct invocation">Direct function bypass</span>.** The programme's control. The same `submit_payment` callable that `enforce()` denied in Listing 40.3 is called directly, one line, no wrapper (Listing 40.5):

```text
>>> submit_payment()
{'submitted': True}
ledger: ['payment_submitted']   <- the effect happened; no decision,
                                   no event, no record
```

**Listing 40.5 — The bypass that succeeds.** Real output. The side-effect ledger shows the payment-submission effect occurred; the governance layer contains no trace that anything happened at all — not a denial, not an event, nothing whose absence could be alarmed on.

No boundary responds, and none was claimed to. What the injection *verifies* is the claim register: NS-LEDGER-002's `bypass_paths` names exactly this path, its tier is 2 with the cooperative qualifier, and its residual dependency motivates the gateway **[extension]**. Had the register claimed "the executor cannot submit a payment" without the scope clause, this one-line transcript would falsify the register — which is why Chapter 14 called the bypass demonstration the most valuable test in the suite. *Evidence to preserve:* the transcript and the register row it qualifies, together. *Lesson:* Tier 2 claims survive their bypass only if the bypass is written into them; the alternative to the qualifier is not a stronger sentence but an external enforcement point.

**F7 — Hostile tool bundle.** A bundle named `northstar-research-tools` arrives for Atlas: its README claims "docs-only… no network access, no execution, templates only," while its `package.json` carries a `postinstall` hook running a script that pipes `curl` to `sh`, and its Model Context Protocol (MCP) configuration mounts a filesystem server at `/`. The <span class="ix" data-ix="package scanner!capstone">scanner</span> is not persuaded (Listing 40.6):

```text
$ nornyx package scan hostile-bundle --out scan_out \
    --package-id northstar-research-tools
{ "status": "pass", "risk_tier": "critical", "total_files_scanned": 4,
  "package_payload_executed": false }

# hook_risk_review.md:   `hook_content` in package.json line 5:
#                        "postinstall": "node ./scripts/setup.js"
# command_risk_report.md: `curl_pipe_sh` in scripts/setup.js line 3 (critical)
# mcp_risk_review.md:     filesystem server rooted at "/" (critical)
# claim_vs_evidence_report.md: no_execution_but_scripts_observed (critical),
#                              no_network_but_endpoints_observed (high)
```

**Listing 40.6 — The scanner versus the bundle's story.** Real transcript and report excerpts. The scan's `status: pass` means the *scan* completed; the finding is `risk_tier: critical` with ten findings, and `package_payload_executed: false` is the scanner's own safety assertion — the hook was surfaced, never activated **[implemented]**.

The claim-versus-evidence detector is the teaching centerpiece: every textual claim in the bundle is labeled an untrusted claim and checked against observed surfaces, and the contradiction — "no execution" beside lifecycle scripts — is itself a critical finding. The governed-package validation rules then require that detected hooks, MCP definitions, and critical mismatches be answered by review evidence and a security approval gate before the package can validate — and the profile's permitted claim is scoped exactly: inventoried, risk-surfaced, evidence-bound, hash-locked, approval-gated — "It must not claim that the package is safe" **[implemented]**. *Evidence to preserve:* the full report set (ten JSON, ten Markdown) with the bundle's hash inventory. *Lesson:* a package's documentation is adversarial input; the reviewable object is the divergence between what it says and what it contains.

**F8 — Evidence artifact escaping its package.** The baseline stream's `approval_granted` event carries an `evidence_artifact` — a path plus SHA-256 for the human approval record. With the correct relative path and hash, validation passes. The injection rewrites the path to `../northstar-governance/org_policies.nyx` (keeping a correct hash for that file): validation fails with <span class="ix" data-ix="evidence artifact!path containment">`AN_EVT_ARTIFACT_MISSING`</span> — "Evidence artifact '../northstar-governance/org_policies.nyx' cannot be read inside the evidence root" — alongside a schema rejection of the traversal-shaped path; artifact paths resolve strictly inside the events file's own directory **[implemented]**. *Evidence to preserve:* both validation reports (passing and failing) and the artifact's hash. *Lesson:* evidence packages are bounded by construction; a record may cite supporting bytes only from inside the boundary that travels with it, or the citation is an exfiltration vector wearing a citation's clothes.

> **Misconception.** *"Eight injections passed, so the system is safe."* The programme demonstrates that eight *specific* boundaries behave as documented at one revision under one toolchain. It does not bound the set of failures, prove coverage of undeclared surfaces, or authenticate any producer — and F6 exists precisely to keep one successful attack in the record. Failure injection calibrates claims; it does not certify systems. Rerunning the programme is part of every toolchain or framework upgrade, because F1–F8 are regression tests for the claim register itself.

## 40.5 Verification matrix and the assurance review

Table 40.2 — the <span class="ix" data-ix="verification matrix">verification matrix</span> — closes the loop from Chapter 39's register to this chapter's transcripts: every claim, the mechanism that verifies it, and where the proof lives.

| Register claim | Verifying mechanism | Transcript / artifact in this build |
|---|---|---|
| NS-ORG-001 (canonical policy everywhere) | `workspace-check` set comparison | Pass report, all members `ok`; drift run in Ch. 39's Charter scene (`missing: ["deny secrets_to_llm"]`, exit 1) |
| NS-ORG-002 (artifacts match source) | `nornyx drift` full-output; byte-compare regeneration; `lock-check` | F1 report (`policy.yaml` `changed`); clean `diff -r`; lock-check `pass` with digest `sha256:44f0cfb0…` |
| NS-ATLAS-001 (no undeclared tools, wrapped surface) | Coverage inventory + `enforce()` boundary | Listing 40.3 deny; inventory (1 wrapped of 6); F5 |
| NS-ATLAS-002 (external share needs human approval) | Engine approval order; gate action classes | Listing 40.4: `CROSSING_APPROVAL_REQUIRED` then `ALLOWED` with human assertion |
| NS-FORGE-001 (no unapproved merge) | Branch protection (platform) + revision-bound approval | Platform-owned audit log **[guidance]**; F2 engine denial for the binding half |
| NS-FORGE-002 (approval dies with its revision) | Engine first-check revision binding; `--as-of` freshness | F2: `APPROVAL_REVISION_MISMATCH`; `AN_APPROVAL_EXPIRED` at +1 day |
| NS-LEDGER-001 (no agent approves) | Schema constants; static, engine, evidence layers | `APPROVAL_NON_HUMAN` denial (Listing 40.4); `approval_rejected` event validates in the stream |
| NS-LEDGER-002 (executor cannot submit) | Deny-by-default capability evaluation | `CAPABILITY_DENIED` + ledger unchanged (Listing 40.3); **qualified by F6** |
| NS-LEDGER-003 (sensitive never shared) | Engine share evaluation; zone `never_share` | `SENSITIVE_SHARING` denial with reason naming the category |
| NS-PKG-001 (bundles inventoried, gated) | Package scanner + validation rules | F7: critical tier, hook and claim-mismatch findings, `package_payload_executed: false` |

**Table 40.2 — The verification matrix.** Every row of the register now points at a mechanism and a reproducible artifact. The teaching purpose is the NS-LEDGER-002 row: it cites its own successful bypass as part of its verification, because a Tier 2 claim is verified *including* its boundary, not up to it.

**The <span class="ix" data-ix="eight questions!capstone review">eight questions</span>, applied.** The review board takes the three most consequential claims — NS-LEDGER-001, NS-LEDGER-002, and NS-ORG-001 — through Chapter 3's eight questions. Compressed to their load-bearing answers: For **NS-LEDGER-001** (no agent approves): guaranteed — no representable, composable, evaluable, or evidentiable path grants approval authority to a non-human, enforced redundantly by schema constants, structural checks, the engine's `APPROVAL_NON_HUMAN`, and the evidence validator's grant-scoped human check; evidence — this build's denial decision and the validating `approval_rejected` event; assumptions — the humans holding roles are who the identity provider says, which is outside the boundary; bypass — a human rubber-stamping on an agent's behalf, invisible to every layer; on failure — all four layers must fail together for a grant to slip through, and each fails closed independently; tier — 1 plus 2; unproven — everything about the quality of human judgment. For **NS-LEDGER-002**: guaranteed — on evaluated requests, `payment.submit` denies for every identity; evidence — decision, event, and untouched side-effect ledger; assumption — reachability only via governed surfaces, *known false* by F6; bypass — one line; on failure — `load_authorizer` refuses stale locks, `enforce()` raises before the callable; tier — 2, cooperative, declared surfaces only; unproven — that no ungoverned path was exercised, which is exactly what the gateway extension would convert from assumption to architecture. For **NS-ORG-001**: guaranteed — rule-set equality between manifest and members at check time; evidence — the workspace report; assumptions — the gate runs, and its exit code blocks; bypass — merge past a red gate, or change the manifest itself without review; on failure — the check fails closed but blocks nothing by itself; tier — 1; unproven — that the canonical policy is *good*, a question no mechanism in this book answers.

**One decision, reconstructed.** Chapter 36's <span class="ix" data-ix="audit reconstruction!capstone">method</span>, compressed to its chain, applied to the €61,250 adjustment's approved crossing (Figure 40.2). The auditor starts from the *claim*: register row NS-ATLAS-002's Ledger sibling — external crossings require revision-bound human approval. Down one link: the *event* — `approval_granted`, mission `GOAL-LEDGER-001`, approver role `network_governance_owner`, `actor_type: human`, bound to contract digest `sha256:70119e93…`, lock digest `sha256:44f0cfb0…`, revision `git:b5e91c4…`, with an `evidence_artifact` naming the approval record and its SHA-256. Down again: the *validation report* — status `pass`, and its embedded limitations, which the auditor records rather than trims: supplied-record conformance only; hash validity is content binding, not truth. Down again: the *lock* — verified against the contract, binding the composed packs and the approval requirement the event references. Down again: the *contract at the revision* — the gate `gate.exec_ingress` with its action classes, the approval declaration with its roles, denial list, binding, and expiry. Sideways: the *approval artifact itself* — hash-matched, human producer, in-authority role, unexpired at `decision_at`. The reconstruction terminates in two residuals the auditor writes down: the event stream's completeness is asserted by its producer, not proven; and the person behind `network_governance_owner` is the identity provider's statement, not the toolchain's. Total reconstruction time in the review: eleven minutes — the deliverable Chapter 36 promised, purchased by every binding discipline in Parts III through V.

> **Assurance boundary.** What this chapter demonstrated, at revision `git:b5e91c4…` under distribution 1.11.0: the artifact set builds deterministically and locks; the org and drift gates catch the divergences injected into them; the engine denies the unauthorized, the unapproved, the non-human, the stale, and the sensitive on *evaluated* requests, and its evidence validates against the exact locked revision. What it did not and cannot demonstrate: that any unevaluated path was absent (F6 proves the opposite), that any producer was honest, that any framework surface behaves as tested here under a different pin, or that a single Tier 3 sentence is available anywhere in the system today. The register survives the review because it never claimed any of those.

## Summary

The capstone build assembles the design of Chapter 39 into artifacts and transcripts: three checked contracts under one workspace gate; ten deterministic, byte-identically regenerating network artifacts under a content-addressed lock whose record census matches the design inventory; adapter wiring through the real `SurfaceBinding`/`enforce()` boundary with framework wrappers repository-tested against exact pins; and a pipeline of fail-closed gates with documented exit codes. The positive baseline exercises every request type — including the three-valued crossing that returns approval-required and the delegated allowance that carries its basis into evidence. The failure-injection programme then attacks eight boundaries: seven stop at named diagnostics (`repo_drift` change reports, `APPROVAL_REVISION_MISMATCH`, `AN_IDENTITY_BINDING_DUPLICATE`, `AN_EVT_REPLAY`, the unsupported-surface inventory, the scanner's critical findings, `AN_EVT_ARTIFACT_MISSING`), and the eighth — the direct bypass — succeeds by design and is absorbed by the claim register rather than by any gate. The verification matrix ties every register row to its mechanism and transcript; the eight questions expose each consequential claim's residuals; and the compressed reconstruction shows the whole binding chain traversable in minutes. The red transcripts, as the architect predicted, are the deliverable.

- Build order follows dependency order: contracts, workspace, artifacts, locks, wiring, gates.
- State precisely what was executed here versus repository-tested; the distinction is the coverage discipline.
- A denial is proven by the absence of the effect, not the presence of an exception.
- Every injection deliverable is fourfold: boundary, diagnostic family, preserved evidence, lesson.
- The bypass that succeeds is a register test, and the register passes only if it predicted it.
- Reconstruction speed is a designed property, purchased by revision binding at every layer.

## Review questions

1. Injection F1 first verifies that the `AGENTS.md`-only diff stays green before running the full gate. Why is demonstrating the *insufficient* gate part of the injection, and which historical defect in the toolchain's own guidance does it re-enact?
2. The engine checks an approval's revision binding before its actor type. Construct the failure that ordering prevents: what could an auditor wrongly conclude from an `APPROVAL_NON_HUMAN` denial if revision binding were checked second?
3. F3 produces no denial event when identity resolution fails. Defend this design choice against the objection that "everything should be recorded," using the distinction between a policy decision and an attribution failure.
4. Explain why the explicit-mode replay fingerprint must exclude the timestamp, and what a producer must legitimately change to repeat identical work without tripping `AN_EVT_REPLAY`.
5. The F6 transcript is two lines long and defeats nothing. Trace exactly which register fields it exercises, and state the condition under which the same transcript would instead falsify the register.
6. In the reconstruction, the auditor records the validation report's limitations verbatim. What claim inflation does paraphrasing that block typically introduce?

## Exercises

1. **Run the programme.** Reproduce injections F1, F4, and F8 against your own build of the Ledger contract (or the repository's support-network example). For each, capture the failing report, write the four-part deliverable, and note any diagnostic that differed from this chapter's — with the revision you ran against.
2. **Design F9.** The programme omits at least one boundary worth attacking: the profiles lock (`nornyx.profiles.lock`). Design the injection — what you would tamper with, which diagnostic family you predict (`PACK_LOCK_MISMATCH` and its siblings, exit 2), what evidence you would preserve — then run it and compare prediction to observation.
3. **Reconstruct under pressure.** Give a colleague only the evidence store from this chapter's build (streams, reports, lock, contracts) and the claim register, and have them reconstruct the high-value crossing without your help, timing the exercise. Every question they ask you out-of-band is a missing binding; add each one to the evidence design and rerun.

## Further reading

- [@swebok-testing] — the testing vocabulary within which failure injection sits as a designed, hypothesis-driven activity rather than exploratory breakage.
- [@schneider-enforceable] — why F6's result is a theorem rather than a defect: no execution monitor enforces a policy on paths it does not observe.
- [@in-toto] — the supply-chain analogue of this chapter's binding chain, and the direction NS-PKG-001's evidence would grow toward attestation.
- [@merkle] — the content-addressing substrate beneath every digest in the reconstruction chain.
- [@nornyx-repo] — the reference CI, the A/B benchmark's ledger method, and the adapter test suites this chapter's programme extends; reading `examples/crewai_governance_benchmark/REVIEWER_QUICKSTART.md` shows the same discipline applied by the toolchain to itself.
