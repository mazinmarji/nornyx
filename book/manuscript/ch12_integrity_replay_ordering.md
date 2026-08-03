---
chapter: 12
part: III
title: "Integrity, Replay, Ordering, and Determinism"
---

# Integrity, Replay, Ordering, and Determinism

> **Opening scenario.** Northstar's Treasury team is reviewing a week of activity from Ledger, its multi-agent payment-exception workflow. The evidence set contains two records that are, field for field, almost identical: the same executor identity, the same capability, the same €50,000 adjustment on the same case, four minutes apart. Three explanations are consistent with what the reviewer sees. The producer emitted one record twice — a bug, and the adjustment happened once. The first attempt failed and the executor retried — one intended adjustment, two attempts. Or the executor drafted two adjustments because Treasury genuinely needed two — two intended adjustments. Nothing in either record distinguishes these cases, and the difference between them is €50,000. The reviewer's instinct is to ask for better logging. The correct response is that the evidence model is missing a concept: it records *what* happened without recording *which execution it belongs to*. This chapter builds the machinery that closes that gap, along with the integrity and ordering machinery it rests on.

> **Learning objectives.**
> - Explain content addressing and state precisely what a digest binds — and the five things it does not.
> - Describe a lock as a multi-way binding structure and enumerate what a governance lock should bind.
> - Apply the four ordering checks available within a single-producer stream and state what each rules out.
> - Explain why local ordering validation cannot establish distributed causality.
> - Construct a semantic fingerprint that detects replay while permitting legitimate repeated work.
> - Use the mission / operation / occurrence / attempt hierarchy to classify a pair of similar events as duplicate, retry, or repeated work.
> - Explain why nondeterministic artifact generation destroys drift detection.

> **Prerequisites.** Chapter 8 (canonicalization and semantic identity; deterministic composition) and Chapter 11 (evidence, producers, packages). Chapter 8 established that a digest is meaningful only relative to a named canonical form and a canonicalizer version; that result is used here without re-derivation.

## 12.1 Content addressing: what a digest binds

<span class="ix" data-ix="content addressing">Content addressing</span> names a thing by a cryptographic digest of its bytes rather than by a location. The idea is old and its consequences are still underused: if the name is derived from the content, then the name cannot survive a change to the content, and any party holding the name can check that the bytes they were handed are the bytes the name refers to. Merkle's construction extends this from a single blob to a tree, so that one short digest commits to arbitrarily much structured content [@merkle]; every lock, manifest, and artifact digest in this book is an application of that idea.

The engineering value is that a <span class="ix" data-ix="digest">digest</span> converts a *trust* question into a *comparison* question. "Is this the policy we reviewed?" requires knowing what was reviewed, who reviewed it, and whether the file has been touched since. "Does `sha256:3cdf632c…` equal `sha256:3cdf632c…`?" requires a hash function. The first question is a process; the second is an equality test, and equality tests can be put in a build pipeline.

What is dangerous about digests is not what they do but how readily readers extrapolate from them. A digest supports exactly one claim: *these bytes are those bytes*. Five claims that people routinely read into a digest are not supported by it, and Figure 12.1 lays them out side by side because keeping them separate is the whole discipline.

<figure class="nx-fig" id="fig-12-1">
  <div class="fig-body">
    <table class="fig-table">
      <tr><th>A digest binds</th><th>A digest does not establish</th></tr>
      <tr><td>Content: these bytes are the bytes the digest was computed over.</td><td><b>Truth.</b> A digest of a false statement is a perfectly valid digest.</td></tr>
      <tr><td>Detection: any change to the content changes the digest.</td><td><b>Identity.</b> Nothing in the digest says who computed it or who wrote the content.</td></tr>
      <tr><td>Comparability: two parties can compare without exchanging content.</td><td><b>Completeness.</b> A digest over a record set says nothing about records that were never added.</td></tr>
      <tr><td>Stability: the same canonical content yields the same digest anywhere.</td><td><b>Authorization.</b> A matching digest does not mean anyone approved the content.</td></tr>
      <tr><td>Reference: a short name can commit to arbitrarily large content.</td><td><b>Producer honesty.</b> A conforming, correctly hashed record from a lying producer hashes just as cleanly.</td></tr>
    </table>
  </div>
  <figcaption><b>Figure 12.1 — What a digest binds and what it does not.</b> The left column is the entire guarantee; the right column is the set of claims organizations attach to it anyway. The teaching purpose is that every row on the right requires a *different* mechanism — attestation for identity, an enumeration contract for completeness, an approval record for authorization, an independent observer for honesty — and that adding more hashing does not supply any of them.</figcaption>
</figure>

The completeness row deserves particular attention because it is the one that bites hardest in evidence work. Hashing a set of records makes the set tamper-evident. It does nothing about a record that was never produced, because a set with a missing element is a perfectly well-formed set with its own perfectly valid digest. This is the integrity-layer restatement of Chapter 11's omission problem, and it is why detecting omission needs *enumeration* — an independently known expectation of what should be present — rather than more integrity.

## 12.2 Locks as multi-way binding structures

A digest binds one thing. Real governance questions involve many things that must agree with each other: the policy source, the artifacts generated from it, the schema versions those artifacts conform to, the modules composed into the effective policy, and the specific revision of the subject being governed. A <span class="ix" data-ix="lock">lock</span> is the artifact that binds all of them *at once*, into a single reviewable, committable file.

The general shape is worth stating independently of any implementation. A governance lock should record, for each participating element, an identity and a content digest; it should record the format version of the lock itself, so that a change to the canonical form is a visible event rather than a mass re-hash; it should record the immutable <span class="ix" data-ix="subject revision">revision of the governed subject</span>, refusing mutable references such as branch names, because a lock pointing at a moving target binds nothing; and it should be verifiable by recomputation, meaning that anyone with the inputs can rebuild the lock and compare rather than having to trust the file.

<figure class="nx-fig" id="fig-12-2">
  <div class="fig-body">
    <div class="layers">
      <div class="layer authority" data-note="one file, committed and reviewed">Lock — binds every element below to one another</div>
      <div class="layer" data-note="digest of the canonical governed content">Contract source</div>
      <div class="layer" data-note="immutable, content-addressed only">Subject revision</div>
      <div class="layer" data-note="identity + version + content hash per pack">Composed profile and modules</div>
      <div class="layer" data-note="which schema each block validates against">Block schemas and structural checks</div>
      <div class="layer" data-note="pins the exact evidence schema version">Runtime-events schema version</div>
      <div class="layer" data-note="one digest per declared record">Per-record digests</div>
      <div class="layer" data-note="path + digest for each generated file">Generated artifacts</div>
    </div>
  </div>
  <figcaption><b>Figure 12.2 — A lock as a multi-way binding.</b> The teaching purpose is the arity. Each layer alone could be hashed independently; the lock's contribution is that a change to <em>any</em> of them breaks a single check, so drift cannot hide in the gap between two separately verified artifacts. Note that the runtime-events schema version is inside the lock: evidence produced under a different schema version is therefore evidence for a different agreement.</figcaption>
</figure>

Listing 12.1 shows an abridged real lock so that the arity is concrete rather than schematic.

```json
{
  "schema": "nornyx.agentic_network_lock.v1",
  "lock_format_version": "1.0",
  "network_id": "network.governed_support",
  "subject_revision": "git:feedfacefeedfacefeedfacefeedfacefeedface",
  "source_contract_digest": "sha256:3cdf632c08684efa2382a047b474b8f56ea4a83c…",
  "profile": {"id": "nornyx.builtin.agentic_network", "version": "0.1.0",
              "content_hash": "sha256:94ab4650c2a2…"},
  "structural_checks": ["agentic_network_delegation.v1", "agentic_network_foundation.v1"],
  "runtime_events_schema": {"id": "nornyx.agentic_runtime_events.v1", "version": "1.1"},
  "records": {"agent_identities": "…4 digests…", "capabilities": "…8…",
              "trust_zones": "…2…", "memberships": "…4…"},
  "artifacts": [{"path": "a2a_declaration.json", "sha256": "d55d31907279…"}]
}
```

**Listing 12.1 — An agentic-network lock, abridged.** Built during the fact-pack audit by running the repository's lock command on `examples/agentic_network_support/support_network.nyx`; digests truncated and collections elided. Read it as one entry per layer of Figure 12.2: a source digest, an immutable revision, resolved packs with content hashes, the structural checks applied, the pinned evidence schema version, per-record digests, and a digest per generated artifact.

The `runtime_events_schema` entry is what makes a lock useful at runtime rather than only at review time. Because the lock pins the evidence schema version, an evidence stream can be checked not merely against a schema but against *the schema this contract agreed to*. That converts a whole class of version-skew problems into a deterministic mismatch.

> **Nornyx in practice.** As implemented at the snapshot, the agentic-network lock binds nine things: the digest of the canonical governed-content view of the contract; the network identifier and its subject revision; the resolved profile and modules by identity, version, and content hash; the block schemas and structural checks applied; the runtime-events schema identifier and version; the protocol declarations; a sorted per-record digest list across all ten declared collections; the approval and evidence requirement references; and a path-plus-digest entry for every generated artifact (`schemas/agentic_network_lock_v1.schema.json`, `nornyx/agentic_artifacts.py`). Verification is field-by-field with a distinct diagnostic per class of divergence: an edited contract yields `AN_LOCK_SOURCE_STALE`, a changed declaration yields `AN_LOCK_RECORD_MISMATCH`, and an artifact that is modified, deleted, or added on disk yields `AN_LOCK_ARTIFACT_MISMATCH`, `AN_LOCK_ARTIFACT_MISSING`, or `AN_LOCK_ARTIFACT_UNEXPECTED`. The immutability rule is enforced at build time: a subject revision that is not a content-addressed `git:` or `sha256:` identifier fails with `AN_LOCK_REVISION_MUTABLE`. The lock format version is itself a constant in the schema, so a future change to canonical form is a declared bump rather than a silent re-hash.

> **Assurance boundary.** A lock establishes that today's inputs are byte-identical to the reviewed ones. It does not establish that anyone reviewed them, that the reviewer was authorized, or that the runtime obeyed them. A writer with repository access can regenerate a fully self-consistent lock around weakened inputs; the repository states this directly — "A hostile local writer can regenerate a consistent lock — detecting unauthorized regeneration is a repository control (git history and human review), not a lock property" (`docs/agentic-network/07_NETWORK_LOCK.md`). The lock is a mechanism for making change *visible*, and visibility only becomes control when a human or a branch-protection rule is looking.

## 12.3 Ordering within a single-producer stream

Move now from artifacts to streams. An evidence stream arrives as a list of records. Before any semantics can be checked, the stream's internal structure must be checked, and there are exactly four kinds of check available to a validator that has nothing but the stream itself.

**<span class="ix" data-ix="sequence number">Contiguous sequence numbers</span>.** Each record in a stream carries a sequence number, and the numbers must run from one upward with no gaps and no repeats. Contiguity is what converts omission from invisible to visible *within the producer's own accounting*: if the producer numbered an event 7 and never emitted it, the validator sees 6 followed by 8. This is a real and useful property, and it is narrower than it first appears — it detects a *gap in the producer's numbering*, not a gap in reality. A producer that never assigned a number to an action it took has produced a perfectly contiguous stream.

**Non-decreasing timestamps.** Timestamps must not go backwards along sequence order. This catches clock resets, out-of-order assembly, and records spliced in from another run. It does not establish that the timestamps are accurate, and a producer with a wrong clock produces a consistently wrong and perfectly valid stream.

**Dependency ordering.** Where a record declares that it depends on another, the referenced record must exist in the stream and must carry a lower sequence number. This lets a producer express structure that plain sequence order cannot — "this share was authorized by that approval" — and lets the validator check that the structure is acyclic and grounded.

**Valid transition pairs.** Certain record types are meaningless in isolation: a completion without an initiation, an acceptance without a request, a grant without a request, a tool invocation without a prior allowance for that capability. Pairing rules are the closest a stream-local validator gets to checking that the *protocol* of governance was followed, rather than merely that records are well formed.

Table 12.1 pairs each check with what it rules out and, more importantly, what it does not.

| Check | Rules out | Does not rule out |
|---|---|---|
| Contiguous sequence from 1 | Deleted or dropped records within the producer's numbering | An action the producer never numbered at all |
| Non-decreasing timestamps | Clock resets, reordering, records spliced from another run | Inaccurate clocks; deliberate uniform skew |
| Dependency targets exist with lower sequence | Dangling and circular references | A missing dependency the producer never declared |
| Valid transition pairs | Tool use without allowance; completion without initiation | An allowance that was recorded but never actually evaluated |

**Table 12.1 — The four stream-local ordering checks.** The right-hand column is the teaching content. Each check is genuinely useful and each has the same shape of limit: it constrains the *stream's account of itself*, not the world the stream describes. Reading down that column produces the honest summary — these checks establish internal consistency, and internal consistency is a necessary but not sufficient condition for truth.

> **Nornyx in practice.** As implemented at the snapshot, all four checks run per mission identifier, with a distinct diagnostic each: `AN_EVT_SEQUENCE_GAP` and `AN_EVT_DUPLICATE_SEQUENCE` for contiguity, `AN_EVT_DUPLICATE_ID` for repeated event identifiers, `AN_EVT_ORDER_INVALID` for decreasing timestamps, `AN_EVT_DEPENDENCY_MISSING` for unresolvable or forward `depends_on` targets, and four pairing codes — `AN_EVT_TOOL_WITHOUT_ALLOWANCE`, `AN_EVT_ACCEPTANCE_WITHOUT_REQUEST`, `AN_EVT_COMPLETION_WITHOUT_INITIATION`, `AN_EVT_GRANT_WITHOUT_REQUEST` (`nornyx/agentic_evidence.py`). The documented summary of what this achieves is deliberately modest: per mission, the validator proves "local sequence consistency of the supplied stream" (`docs/agentic-network/06_RUNTIME_EVIDENCE.md`).

## 12.4 Local order is not distributed causality

It is tempting to read a validated, well-ordered stream as a record of what happened in what order. For one producer, on one machine, that reading is roughly defensible. Across systems it is not, and the reason is the oldest result in distributed systems.

Physical timestamps do not order events across machines, because clocks drift and no synchronization protocol removes the residual uncertainty. What *can* be ordered is the <span class="ix" data-ix="happened-before relation">happened-before</span> relation, and it is established only by explicit causal links — a message sent and received, a token passed, a dependency declared — not by comparing wall-clock readings [@lamport-clocks]. Events with no such chain between them are concurrent, and concurrency is not a measurement failure to be engineered away; it is the actual state of affairs.

The consequence for governance evidence is precise. Suppose the Ledger planner and the Ledger analyst run in different services and each produces its own evidence. Both streams validate. Both are internally ordered. A reviewer wants to know whether the analyst's exposure calculation preceded the planner's decision to escalate. The two streams' timestamps appear to answer the question. They do not: they were produced by two clocks, and a skew of a few hundred milliseconds — routine — inverts the apparent order of events minutes apart in a busy system. The only sound answer comes from a declared causal link: the planner's record must reference the analyst's record, and the reference must be part of the evidence rather than reconstructed later from times.

> **Key idea.** Ordering evidence across producers requires *causal references carried in the records*, not timestamps compared after the fact. A governance evidence model that supports cross-system order must make those references a first-class, required field on the events that need them; a model that does not should say plainly that it orders within a stream and stops there.

> **Nornyx in practice.** As implemented at the snapshot, the scope is explicitly the single stream. Ordering is validated per mission within one supplied file, one producer, one schema version; multi-producer merging and differential chunks are not supported, and continuation happens through a resume path that revalidates the complete prior stream and requires the producer, schema version, and occurrence mode to match (`nornyx/agentic/authz.py`). The documentation states the limit rather than leaving it to inference: validation "does not solve distributed causality, cannot prove events across systems happened in the claimed order, and never claims complete causal truth" (`docs/agentic-network/06_RUNTIME_EVIDENCE.md`).

## 12.5 Replay and semantic fingerprints

<span class="ix" data-ix="replay attack">Replay</span> is the reuse of a record that was valid once, in a context where it should not be valid again. In authentication protocols it is a captured credential resubmitted; in governance evidence it is a decision record submitted twice, so that one authorization appears to cover two actions. It is worth taking seriously precisely because the replayed record is *genuine*: every field is correct, every reference resolves, every binding matches. Validating harder does not help.

The detection mechanism is a <span class="ix" data-ix="semantic fingerprint">semantic fingerprint</span>: a digest computed over the record's *substantive* fields, excluding the fields that legitimately differ between two copies of the same record. The design problem is entirely in choosing which fields go in which bucket, and both mistakes are damaging.

Fields that carry <span class="ix" data-ix="transport field">*transport* identity</span> — the record's own serial number, its position in the stream, and in some designs its timestamp — must be excluded. They are assigned by the transmission, not by the event, and a producer that wanted to evade detection would simply restamp them. Include the timestamp in the fingerprint and a duplicate becomes undetectable by changing one integer.

Fields that carry *substantive* identity — the actor, the capability, the decision, the target, the zones, the digests — must be included, or genuinely different actions collapse into one fingerprint and the validator raises a false replay on legitimate work.

And one field class is easy to overlook: *occurrence identity*, the subject of the next section. Including it is what makes the fingerprint able to distinguish "the same record twice" from "the same work, done again, on purpose."

```json
{"event_id": "GOAL-001-0002", "sequence": 2, "timestamp": "2026-07-17T10:00:00Z",
 "event_type": "capability_allowed", "mission_id": "GOAL-001",
 "actor_ref": "identity.researcher.local", "capability_ref": "read_governed_context",
 "policy_decision": "allow",
 "occurrence": {"operation_id": "node.read", "occurrence_id": "task.1", "attempt": 1}}

{"event_id": "GOAL-001-0009", "sequence": 9, "timestamp": "2026-07-17T10:04:00Z",
 "event_type": "capability_allowed", "mission_id": "GOAL-001",
 "actor_ref": "identity.researcher.local", "capability_ref": "read_governed_context",
 "policy_decision": "allow",
 "occurrence": {"operation_id": "node.read", "occurrence_id": "task.1", "attempt": 1}}
```

**Listing 12.2 — Two records that a fingerprint must reject.** Abridged from a runtime-events 1.1 explicit-mode stream produced during the fact-pack audit of the repository. The three fields that differ — `event_id`, `sequence`, `timestamp` — are exactly the fields excluded from the fingerprint, so the two records fingerprint identically and the second is a replay. Change the `attempt` to `2` and the records are no longer identical in substance: they describe two attempts at one occurrence, which is legitimate.

> **Nornyx in practice.** As implemented at the snapshot, the fingerprint is a SHA-256 over the event with a small transport-field set removed. In the legacy modes the excluded set is `{event_id, sequence}`; in explicit occurrence mode `timestamp` is excluded as well, and the code records the reason in a comment: "A producer cannot evade exact replay detection merely by restamping a duplicate with a new timestamp" (`nornyx/agentic_evidence.py`). A collision raises `AN_EVT_REPLAY`. Timestamp exclusion is safe only *because* occurrence identity is present to carry the distinction the timestamp would otherwise have carried — which is why the two modes exclude different field sets. The governing sentence is worth memorizing: "Identical semantic evidence inside one attempt is replay; identical work in a new occurrence or retry attempt is not" (`docs/agentic-network/06_RUNTIME_EVIDENCE.md`).

## 12.6 The identity hierarchy: mission, operation, occurrence, attempt

We can now answer the opening scenario. Its difficulty was not integrity and not ordering; it was that the evidence model had no vocabulary for *which execution* a record belonged to. Four levels of identity supply that vocabulary, and each exists because a real question cannot be answered without it.

A <span class="ix" data-ix="mission">mission</span> is one complete governed run: the whole unit of work an agent or network was invoked to do. It is the scope within which sequence numbers are contiguous and within which a reviewer expects a coherent story.

An <span class="ix" data-ix="operation">operation</span> is a stable governed surface — a node in a graph, a tool, a step — identified consistently across every execution of it. Operations are the things policy talks about, and their identity must survive across runs, because "the executor may draft adjustments" is a statement about an operation, not about any particular execution of it.

An <span class="ix" data-ix="occurrence">occurrence</span> is one scheduled execution of an operation: one visit to a loop body, one branch of a parallel fan-out, one invocation in a sequence. Occurrences are the level at which "the same work, deliberately, again" becomes representable. Without them, a loop that legitimately runs an operation twelve times is indistinguishable from a producer emitting one record twelve times.

An <span class="ix" data-ix="attempt">attempt</span> is one try within an occurrence: the retry level. Attempts are numbered contiguously from one within their occurrence, and this is where the sharpest rule in the model lives — *a successful occurrence cannot be retried*. If an occurrence succeeded, another attempt at it is not a retry, because there is nothing left to retry; it is either a duplicate record or new work that deserves its own occurrence identifier. Making that a rule rather than a convention is what turns the opening scenario from an interpretation problem into a validation error.

<figure class="nx-fig" id="fig-12-3">
  <div class="fig-body">
    <div class="hier">
      <ul>
        <li>Mission — one complete governed run (<code>CASE-4471</code>)
          <ul>
            <li>Operation — stable governed surface (<code>draft_payment_adjustment</code>)
              <ul>
                <li>Occurrence — one scheduled execution (<code>adj.1</code>, the first adjustment)
                  <ul>
                    <li>Attempt 1 — failed (timeout)</li>
                    <li>Attempt 2 — succeeded — <em>no further attempt permitted</em></li>
                  </ul>
                </li>
                <li>Occurrence — one scheduled execution (<code>adj.2</code>, a second, intended adjustment)
                  <ul><li>Attempt 1 — succeeded</li></ul>
                </li>
              </ul>
            </li>
          </ul>
        </li>
      </ul>
    </div>
  </div>
  <figcaption><b>Figure 12.3 — The four-level identity hierarchy, worked on the opening scenario.</b> The teaching purpose is that the ambiguity in the opening scenario dissolves at the third level, not the fourth: retries and repeated work are different because they sit under different occurrences. Authorization state is scoped to the attempt, so an allowance granted in attempt 1 does not silently cover attempt 2.</figcaption>
</figure>

With the hierarchy in place, Table 12.2 does what the reviewer could not do with the raw records.

| Record pair | Differing fields | Classification | Why |
|---|---|---|---|
| Both `occurrence adj.1 / attempt 1`, identical substance | Only `event_id`, `sequence`, `timestamp` | **Duplicate (replay)** | Same execution slot, same substance: the fingerprint collides and the second record is rejected |
| `adj.1 / attempt 1` then `adj.1 / attempt 2` | `attempt` | **Retry** | Same intended work, second try inside one occurrence — permitted only if attempt 1 did not succeed |
| `adj.1 / attempt 2` (success) then `adj.1 / attempt 3` | `attempt` | **Invalid** | Retry after a successful terminal event; repeated work must open a new occurrence |
| `adj.1 / attempt 1` then `adj.2 / attempt 1` | `occurrence_id` | **Legitimate repeated work** | Two distinct executions of one operation: two adjustments, two authorizations, two records |
| `adj.1 / attempt 1` under mission `CASE-4471`, then under mission `CASE-4472` | `mission_id`, `occurrence_id` | **Separate runs** | Different governed runs entirely; no relationship is implied or checked between them |

**Table 12.2 — Classifying similar event pairs.** The reviewer in the opening scenario had rows one, two, and four collapsed into a single indistinguishable case. The table's teaching purpose is that the distinction is carried by *identity fields*, not by content, timing, or narrative — which is why adding occurrence identity to the schema was a semantic change and not a logging improvement.

> **Case study — Ledger.** Treasury re-runs the review with occurrence identity recorded. The two €50,000 records now differ in exactly one field: the first carries `occurrence adj.1, attempt 1` and the second carries `occurrence adj.1, attempt 2`. That is row two — a retry — and the surrounding stream corroborates it: between them sits a `runtime_failed` record for attempt 1. One adjustment was intended; one adjustment was made; the second record documents the retry rather than a second payment. Had the second record carried `attempt 2` while attempt 1 ended in a success terminal, validation would have rejected the stream outright rather than leaving the reviewer to notice. And had it carried `occurrence adj.2`, the honest reading would be two intended adjustments, requiring two authorizations — which the validator also checks, because allowances are scoped to the attempt. Thread C returns in Chapter 31, where the full multi-agent evidence chain is built, and in Chapter 34, where an attacker tries to exploit exactly these seams.

> **Nornyx in practice.** As implemented at the snapshot, explicit occurrence mode requires every event to carry `occurrence.operation_id`, `occurrence.occurrence_id`, and a one-based `attempt`, and enforces five rules with distinct diagnostics: an occurrence identifier may not move between operations (`AN_EVT_OCCURRENCE_OPERATION_MISMATCH`); attempts may not decrease along sequence order (`AN_EVT_ATTEMPT_ORDER_INVALID`); a successfully completed occurrence may not be retried (`AN_EVT_ATTEMPT_AFTER_SUCCESS`, whose message states the remedy — "repeated work requires a new occurrence id"); one attempt may not record both a success and a failure outcome (`AN_EVT_ATTEMPT_OUTCOME_CONTRADICTION`); and attempts must be contiguous from one (`AN_EVT_ATTEMPT_GAP`) (`nornyx/agentic_evidence.py`). Success and failure terminals are fixed, closed sets — `tool_invoked` and `handoff_completed` are among the successes, `runtime_failed` and `capability_denied` among the failures. Authorization allowances and transition state are scoped to the attempt, not the mission. The residual limit is stated as plainly as the rules: "A cooperative producer can falsely claim a new occurrence; occurrence validation proves structural consistency, not independent execution truth" (`docs/agentic-network/08_SECURITY_BOUNDARIES.md`).

> **Misconception.** *"Occurrence identity solves the duplicate-payment problem."* It solves the *evidence interpretation* problem, which is a different and smaller thing. A producer determined to make two payments look like one retry can label them that way, and a producer that makes a payment without emitting any record at all is untouched by every rule in this chapter. What the model delivers is that a *cooperative* producer can no longer accidentally produce an ambiguous record set, and that certain incoherent stories — retry after success, attempts starting at three — become mechanically impossible to tell. Chapter 13 names the boundary this sits inside.

## 12.7 Determinism of generation as a governance property

Everything above rests on an assumption stated in Chapter 8 and now cashed in: that generating artifacts from a source is a <span class="ix" data-ix="determinism!of generation">deterministic</span> function. Same inputs, byte-identical outputs, on any machine, at any time.

Determinism is usually argued for on reproducibility grounds [@reproducible-builds]. In governance it earns its place for a sharper reason: <span class="ix" data-ix="drift detection">drift detection</span> works by regenerating artifacts, comparing them to the committed ones, and declaring any difference to be drift. That procedure is sound only if a difference *can only* mean drift. Introduce one timestamp into a generated file and every regeneration differs; the gate fails on every run, and within a week someone makes it non-blocking. Introduce a subtler nondeterminism — iteration over an unordered structure, a locale-dependent sort, platform line endings, a dependency that floats to "latest" — and the gate fails *intermittently*, which is worse, because intermittent failures teach people to re-run rather than investigate. Either way the gate stops being a control and becomes noise, and the control it was protecting quietly ceases to exist.

The engineering requirements follow directly and are unglamorous: canonical serialization with sorted keys, no wall-clock values anywhere in output, sorted collections rather than iteration order, fixed line endings, explicitly pinned inputs, and no environment-dependent paths embedded in artifacts. Where an evaluation instant is genuinely needed — approvals expire, memberships have validity windows — it must be an explicit parameter that affects *whether validation passes*, never a value that appears in the output bytes.

> **Nornyx in practice.** As implemented at the snapshot, the generator writes canonical JSON with sorted keys and compact separators, forces line-feed newlines so output is byte-identical across platforms, sorts keyed collections, and emits no timestamps into any artifact (`nornyx/agentic_artifacts.py`, `nornyx/generator.py`). The fact-pack audit verified the property rather than assuming it: two successive generations of the bundled support-network contract produced byte-identical directories under `diff -r`. The evaluation instant is a separate `--as-of` parameter that governs whether the contract validates and never appears in artifact bytes, and a malformed or naive value fails closed with `AS_OF_INVALID` rather than falling back to the live clock. The drift gate is exactly the regenerate-and-compare procedure described above, run as a step of the reference continuous-integration pipeline (`scripts/agentic_network_ci.py`); the user-facing `nornyx drift` command compares every generated artifact by digest and reports each as `ok`, `changed`, `missing`, or `stray`.

> **Design checkpoint.** For your own generated governance artifacts, run the generator twice on an unchanged source, on two different machines, and compare bytes. If they differ, find the source of nondeterminism before writing any policy that depends on comparison — and note that "we normalize the diff before comparing" is a canonicalizer, with all of Chapter 8's obligations attached, not a fix.

## Summary

Content addressing binds bytes to a short name and supports exactly one claim: these bytes are those bytes. It establishes nothing about truth, producer identity, completeness, authorization, or honesty, and each of those requires a different mechanism. A lock extends binding from one artifact to many, so that a change anywhere in the reviewed set breaks a single check; it makes change visible without making it impossible. Within one producer's stream, four ordering checks — contiguity, non-decreasing timestamps, dependency grounding, and transition pairing — establish internal consistency and nothing beyond it. Across producers, order requires declared causal references, because timestamps from different clocks do not establish happened-before. Replay is detected by fingerprinting substantive fields while excluding transport identity, which is safe only when occurrence identity is present to distinguish repeated work from repeated records. The mission, operation, occurrence, and attempt hierarchy supplies that identity. All of it presupposes deterministic generation, because drift detection interprets any difference as drift, and a generator that varies makes that interpretation false.

- A digest binds content; the five claims commonly read into it need five other mechanisms.
- A lock's value is arity: one check covers source, revision, packs, schemas, records, and artifacts.
- Stream-local ordering constrains the stream's account of itself, not the world it describes.
- Cross-system order needs causal references in the records; timestamps do not supply it.
- Fingerprint substance, exclude transport, and include occurrence identity.
- A successful occurrence cannot be retried; intentional repeated work opens a new occurrence.
- Nondeterministic generation converts a drift gate into a random-number generator.

## Review questions

1. State the single claim a digest supports, and for each of the five claims it does not support, name a mechanism that would.
2. A team hashes each of its six generated artifacts separately and checks all six in CI. What does a single lock binding all six, plus the source and the schema versions, add that six independent hashes do not?
3. Two evidence streams from two services both validate cleanly. A reviewer orders their events by timestamp to reconstruct a causal chain. Explain the error, and describe the minimum change to the evidence model that would make the reconstruction sound.
4. Why must a replay fingerprint exclude the record's own sequence number? Why is excluding the timestamp safe in an occurrence-aware model and unsafe without one?
5. Classify each pair as duplicate, retry, invalid, or legitimate repeated work, and justify each from the identity fields alone: (a) same occurrence, same attempt, different event identifier; (b) same occurrence, attempt 2 following a successful attempt 1; (c) different occurrence, attempt 1 in both; (d) same occurrence, attempt 3 with no attempt 2 present.
6. A generated policy artifact contains the generation timestamp "for traceability." Trace the consequence through the drift gate, the lock, and the organization's response two weeks later.

## Exercises

1. Design the fingerprint for an evidence model of your own. List every field in your event schema and assign each to `transport` or `substantive`, with a one-line justification. Then write two records that your fingerprint must treat as identical and two it must treat as different, and check your assignment against them.
2. Take a workflow you know that contains a retry loop and a parallel fan-out. Write out the mission, operation, occurrence, and attempt identifiers for a run in which one branch fails twice and then succeeds, and the loop body executes three times. State how many distinct authorizations the run requires, and why.
3. Using the repository at the book's snapshot, generate the artifacts for a bundled agentic-network example twice into different directories and compare them byte for byte. Then edit one character of the contract source, run lock verification, and record which diagnostic code is emitted. Explain, from the lock's field list, why that particular code and not another.

## Further reading

- [@merkle] — the origin of committing to arbitrarily large content with one short digest; the primitive under every lock and manifest in this chapter.
- [@lamport-clocks] — the source of the happened-before relation and the definitive argument for why timestamps do not order distributed events.
- [@reproducible-builds] — practices for byte-identical output, transferable directly to governance artifact generation.
- [@in-toto] — how binding pipeline steps to attestations addresses the producer-identity row of Figure 12.1 that digests alone cannot.
