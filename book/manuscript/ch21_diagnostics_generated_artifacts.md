---
chapter: 21
part: IV
title: "Diagnostics and Generated Artifacts"
---

# Diagnostics and Generated Artifacts

> **Opening scenario.** A release at Northstar Services is blocked on a Friday afternoon. The generated `policy.yaml` that Forge's harness reads contains `deny secrets_to_llm`, and a build step that legitimately needs a token keeps tripping it. An engineer opens the generated file, deletes the line, and ships. It works, because the harness reads the generated artifact, not the contract it came from. Three weeks later somebody regenerates the artifacts for an unrelated change to an agent's skill list, and the line silently returns. Nobody notices the control came back, because nobody noticed it had gone. The repository's own drift check — a diff of `AGENTS.md` against a freshly generated copy — was green throughout, because `AGENTS.md` does not render policy rules at all. Every part of this went wrong quietly: a derived artifact was treated as authoritative, an edit to it was invisible, and the gate that was supposed to catch the edit was watching a file that could not show it.

> **Learning objectives.**
> - Explain what makes a generated artifact derived rather than authoritative, and what a system must do so that the distinction survives contact with an engineer under deadline.
> - Enumerate the real output sets of both generators, and explain why an incomplete published list is itself a governance hazard.
> - Describe the mechanisms that make generation byte-deterministic, and why determinism is a precondition for every gate in this chapter.
> - Explain forbidden-content scanning as a structural guarantee that declarations cannot smuggle execution.
> - Treat diagnostic codes as a public interface: what stability buys, and how fail-closed exit semantics let a pipeline gate on specific conditions.
> - Distinguish the two drift gates by scope and audience, and run one end to end.
> - State what a workspace check and a context pack do and do not establish.

> **Prerequisites.** Chapter 8 (composition, canonicalization, and semantic identity), Chapter 15 (testing governance claims), Chapter 17 (the contract's blocks), Chapter 18 (profiles, modules, locks, digests). Chapter 8's argument that determinism is a prerequisite for meaningful drift detection is assumed here and applied.

## 21.1 Derived artifacts and the authority they do not have

A <span class="ix" data-ix="generated artifact">generated artifact</span> is a projection of a source into a form some consumer already knows how to read. The contract is the governed source; `AGENTS.md` is what a coding agent reads; `policy.yaml` is what a harness reads; a capability matrix is what a reviewer reads. Projection is valuable precisely because the consumers are heterogeneous and were not designed for the source. It is also where authority quietly leaks, because every one of those consumers reads the *projection*, and the projection is a file an engineer can edit.

The distinction the system must maintain is between authority and readership. The contract holds authority: it is what review approves, what the lock binds, and what a claim refers to. The generated files hold readership: they are what runs. Where those two diverge, the running system is governed by something nobody approved. The opening scenario is not an exotic attack; it is the most natural thing in the world for an engineer to do at five o'clock on a Friday, and a governance design that relies on nobody doing it has not designed anything.

Three mechanisms, applied together, make the distinction hold. **Labelling** puts the fact in the artifact: the generated `AGENTS.md` opens with the line "This file is generated. Edit the `.nyx` source instead." **[implemented]** Labelling is weak on its own — it informs the conscientious and is invisible to a search-and-replace — but it is cheap and it removes the excuse. **Determinism** makes the projection a function, so that "did anyone edit this?" becomes a computation rather than an investigation (Section 21.3). **Gating** makes the computation consequential by running it where it can stop a merge (Section 21.5). Remove any one and the other two degrade: determinism without a gate is a property nobody checks; a gate without determinism is a random alarm that teams learn to override; labelling without either is a comment.

Figure 21.1 puts the two roles side by side.

<figure class="nx-fig" id="fig-21-1">
  <div class="fig-body">
    <div class="layers">
      <div class="layer authority" data-note="reviewed, locked, referenced by every claim">Contract (<code>.nyx</code>) — authority</div>
      <div class="layer" data-note="deterministic function of the contract; carries a generated-file header">Generated artifacts — <code>AGENTS.md</code>, <code>policy.yaml</code>, declarations, manifest</div>
      <div class="layer" data-note="reads the projection, never the contract">Consumers — coding agents, harnesses, reviewers, peer systems</div>
      <div class="layer untrusted" data-note="an edit here changes behavior without changing anything reviewed">Hand edits to a generated file</div>
    </div>
  </div>
  <figcaption><b>Figure 21.1 — Authority above, readership below.</b> Only the top band is authoritative; the middle band is what actually runs. The dashed bottom band is the failure this chapter closes: an edit that changes system behavior while leaving every reviewed artifact untouched. The teaching purpose is to locate the gate — it belongs between the middle and top bands, comparing them, not anywhere further down.</figcaption>
</figure>

> **Key idea.** A derived artifact is safe exactly to the degree that its divergence from the source is *computable and gated*. Everything else — file permissions, naming conventions, code-review vigilance, header warnings — reduces the probability of divergence without making it detectable.

## 21.2 What is actually generated

Two generators exist in the repository, and their output sets are worth stating exactly, because a published summary that omits artifacts is a governance hazard in its own right.

The core generator, `nornyx generate`, writes from one contract: **[implemented]**

1. `AGENTS.md`, carrying the project intents and agent profiles;
2. one `skills/<SafeName>/README.md` per declared skill, with names sanitized into safe path segments;
3. six block projections — `context.yaml`, `harness.yaml`, `policy.yaml`, `evals.yaml`, `trace.yaml`, and `goals.yaml`;
4. when the contract declares goals, one `task_packets/<GOAL-ID>.md` per goal plus a `goal_ledger.md`;
5. `evidence_contract.md`;
6. `nornyx_generation_manifest.json` under schema `nornyx.generation_manifest.v0.1`, listing sorted source blocks, sorted artifact paths, and a SHA-256 for every artifact.

The project's own README summarizes this set as "`AGENTS.md` · `skills/` · `harness.yaml` · `policy.yaml` · `evals.yaml` · `context.yaml` · `evidence_contract.md`" — seven entries. The generator writes those seven and also `trace.yaml`, `goals.yaml`, the task packets, the goal ledger, and the manifest. On the delivery-control-plane example the manifest reports eleven artifacts; on the goals-heavy roadmap example it reports twenty-two. The gap between seven and twenty-two is not a documentation nit. A reader who takes the README as the artifact inventory and writes a gate over those seven files has built the opening scenario's gate: green while `trace.yaml` or a task packet drifts. This is why Section 21.5's user-facing gate reads its file list from the *manifest* rather than from any human's list.

> **Misconception.** *"The README lists the artifacts, so the README is the inventory."* Prose summaries drift from code the same way copied policies drift from their source, and for the same reason: nothing binds them. The authoritative inventory is the generation manifest, because the generator writes it in the same pass that writes the artifacts. If you need a list a gate can trust, take it from the machine-produced one.

The agentic-network generator, `nornyx agentic-network generate`, writes exactly ten files: nine declarations — `network_manifest.json`, `identity_manifest.json`, `capability_matrix.json`, `trust_zone_map.json`, `delegation_policy_bundle.json`, `handoff_manifest.json`, `runtime_evidence_contract.json`, `a2a_declaration.json`, `mcp_capability_declaration.json` — plus `agentic_generation_manifest.json`. **[implemented]** Running it on the bundled support network reports `"artifact_count": 10` with exactly those names. The count is fixed rather than data-dependent: a network with no delegations still gets a delegation bundle, empty. A fixed set is easier to gate on and easier to review, because a missing file is unambiguous rather than possibly meaning "there was nothing to say."

Two of those ten deserve a note that Chapter 27 develops. The `a2a_declaration.json` and `mcp_capability_declaration.json` files describe protocol participation, and each carries the mandatory pair `execution_mode: contract_only` and `live_connector_execution: false`. They are "**declarations, not runtimes**" (`docs/agentic-network/05_PROTOCOL_DECLARATIONS.md`) — statements about what an identity may advertise, containing no endpoint, credential, or transport information whatsoever. Section 21.4 shows the mechanism that keeps that true.

## 21.3 Determinism, and the scan that keeps declarations inert

Every gate in this chapter rests on generation being a *function*: same input, same bytes, on any machine, at any time. Three mechanisms deliver it.

Newlines are forced to line-feed on every write, so a Windows checkout and a Linux runner produce identical files. Ordering is imposed rather than inherited: artifact path lists and hash lists are sorted, and the agentic generator sorts keyed records within each collection and renders canonical JSON — sorted keys, compact separators, no ASCII escaping — before hashing. And nothing carries a timestamp; the agentic declarations are described in the tutorial as "canonical, timestamp-free JSON declarations," and rerunning generation "produces byte-identical output." **[implemented]**

That last property is directly observable. Generating the support network twice into different directories and running `diff -r` produces no output. It holds across different `--as-of` values too, which is worth understanding because `--as-of` looks like it ought to affect the result. It supplies the instant at which the *contract* is validated before generation runs. The artifacts contain no timestamps, so the flag cannot change their bytes — but it can change whether they are written at all. Generating the support network as of `2026-08-03` fails, because an approval the contract depends on has expired by then:

```text
AN_APPROVAL_EXPIRED: Approval evidence is expired or stale.
EVIDENCE_STALE: Evidence is stale or has an invalid freshness interval.
APPROVAL_EXPIRED: Approval has expired.
```

No output directory is created. That is the fail-closed posture applied to generation: an expired governance dependency does not produce artifacts with a warning attached, it produces no artifacts.

The same fail-closed instinct guards a different risk. The declaration files are meant to be *inert* — descriptions a reviewer or a peer system can read, containing nothing that could be executed, dialled, or authenticated with. Nothing about the file format enforces that; a `purpose` string is a string, and a determined author could put a hostname in it. So the generator scans every rendered value before writing. **[implemented]**

<span class="ix" data-ix="forbidden-content scanning">Forbidden-content scanning</span> works on two axes. On keys, each key is split on non-alphanumeric boundaries and case-folded, and any segment matching a set of twenty-six transport, credential, or execution terms — `endpoint`, `host`, `port`, `url`, `uri`, `token`, `secret`, `credential`, `password`, `command`, `shell`, `session`, `bearer`, `ip`, and their plurals among them — fails with `AN_ARTIFACT_FORBIDDEN_FIELD`. Four adjacent-segment pairs are also rejected: `api key`, `key material`, `private key`, and `access key`. Segment matching rather than substring matching is what lets legitimate reviewed fields such as `execution_mode` and `agent_key` survive. On values, any string containing a scheme separator or beginning with a transport scheme, and any bare IPv4 literal, fails with `AN_ARTIFACT_FORBIDDEN_VALUE`; exactly one pattern is exempted, the repository's own schema-identifier namespace, which is a name resolved locally and never fetched.

The check is observable in one edit. Changing a delegation's `purpose` in the support contract to `Delegate refunds; see https://runbooks.internal/refunds for steps.` produces:

```text
AN_ARTIFACT_FORBIDDEN_VALUE: Generated declarations must not contain URLs or
                             transport references.
```

and, again, no output directory. **[implemented]**

Two things are worth drawing out. The scan runs on the *rendered artifacts*, not on the contract, so it catches anything that reaches an output file regardless of which declaration field carried it. And it is deliberately blunt — a genuinely useful runbook reference in a purpose string is rejected along with an attacker's callback host. That is the correct trade for this artifact class: a declaration whose contents can never be dialled is a much stronger thing to hand to a peer system than one that merely usually cannot, and the cost of the false positive is that authors put runbook links in documentation instead.

> **Assurance boundary.** Determinism and content scanning bind *bytes*. They establish that the artifacts on disk are the ones this contract produces and that they contain no transport or credential material. They establish nothing about who ran the generator, whether the contract they came from was wise, or whether a consumer actually obeys the artifacts. The repository is explicit about the last of these for the lock and the same reasoning applies here: "A hostile local writer can regenerate a consistent lock — detecting unauthorized regeneration is a repository control (git history and human review), not a lock property."

## 21.4 Diagnostics as an interface

Most tools treat error messages as output for humans. A governance tool cannot, because its output is read by pipelines that must decide whether to proceed, and a pipeline cannot branch on prose.

Nornyx's <span class="ix" data-ix="diagnostic code">diagnostic codes</span> are upper-snake strings — `UNKNOWN_POLICY_REFERENCE`, `PACK_MONOTONICITY_CONFLICT`, `AN_LOCK_SOURCE_STALE`, `AN_EVT_ATTEMPT_AFTER_SUCCESS` — and there is no numeric scheme. **[implemented]** They are organized into namespaces by prefix, and the governance interface documentation lists them as a stability commitment: `PACK_*`, `RULE_*`, `GOVERNANCE_*`, `APPROVAL_*`, `EVIDENCE_*`, `SOD_*`, `EXCEPTION_*`, `CHANGE_*`, `ARCH_*`, and `AN_*`.

The design gains three things over numbers. A code is self-describing in a log, so an operator who has never seen `AN_LOCK_ARTIFACT_UNEXPECTED` can guess what happened before reading any documentation. A prefix carries routing information, so a pipeline can treat every `AN_EVT_*` as an evidence problem and every `PACK_*` as a composition problem without an enumeration. And a namespace can be extended without renumbering, which matters because the alternative — a registry of numbers that must be centrally allocated — creates exactly the coordination cost that leads teams to reuse codes.

What makes codes an *interface* rather than a convention is that consumers may depend on specific ones. A team that has a bounded, reviewed exception can write a pipeline step that tolerates one named condition and nothing else — "fail on any diagnostic except `PACK_NOT_RESOLVED`, which we accept for this repository until the org pack lands" — and that step remains correct when new diagnostics are added, because a new code is not the tolerated one. That property only holds if codes are stable, which is why the interface documentation commits to it: public behavior "will not be removed without a changelog deprecation notice lasting at least two package minor releases and six months."

The second half of the interface is exit semantics, and they are deliberately coarse. Exit `0` means valid or nothing to check; exit `1` means a governance diagnostic, an invalid pack, invalid evidence, or an unresolved identity; exit `2` is reserved for the classes a caller must never confuse with a policy result — a contract that would not parse, a malformed `--as-of`, or a lock path, encoding, schema, set, hash, or semantic failure. **[implemented]** Three buckets are enough for a pipeline to distinguish "the governance said no" from "the governance could not be evaluated," and separating those two is the whole point: an unparseable contract that exited `1` would be indistinguishable from a policy denial, and a pipeline that treated both as "blocked" would give a broken toolchain the appearance of a working control.

A malformed `--as-of` exiting `2` rather than falling back to the system clock is the same principle at the level of a single flag. Silent fallback would produce a result — a plausible, wrong, unreproducible one — and Chapter 19's temporal-explicitness argument says a governance tool must never manufacture a temporal input the caller failed to supply.

## 21.5 Two drift gates

<span class="ix" data-ix="drift!gate">Drift</span>, in the sense Chapter 2 defined, is the divergence between what a system's controls say and what they do. For generated artifacts it has an exact form: the committed files no longer equal what the contract produces. The repository implements two gates against it, with different audiences and different scopes, and confusing them is a common mistake.

The **development baseline gate** protects the *generator*. It regenerates two fixed example contracts into a temporary directory and compares the resulting generation manifests against committed baseline files under `tests/fixtures/generated_drift/`, using the schema `nornyx.generated_drift_baseline.v0.1`; an `--update` path re-baselines deliberately. **[implemented]** Its question is "did a change to Nornyx alter what Nornyx emits?" — a regression check on the tool, run by the tool's own maintainers, with the baselines under review like any other fixture.

The **user-facing full-artifact gate**, `nornyx drift <contract> --out <dir>`, protects the *user's repository*. It regenerates the contract into a throwaway directory and compares **every** artifact by SHA-256, taking the file list from the generation manifest, and reports each as `ok`, `changed`, `missing`, or `stray` under the schema `nornyx.repo_drift_report.v0.1`. Any divergence exits nonzero. **[implemented]**

The second gate exists because of a documented failure. Nornyx's own recommended pattern once told users to diff `AGENTS.md` against a fresh copy — and `AGENTS.md` does not render policy rules, so a change to `policy.yaml` passed green. The repository's multi-repository case study records this as a real bug that gave a "false sense of safety." The failure reproduces exactly. Deleting `deny secrets_to_llm` from a generated `policy.yaml` and then diffing `AGENTS.md` against a freshly generated one produces no difference at all: the naive gate stays green while a control has been removed from the file the harness reads.

Figure 21.1 shows what the full gate does instead.

<figure class="nx-fig" id="fig-21-1">
  <div class="fig-body">
    <div class="flow">
      <div class="node">contract (.nyx)</div>
      <div class="arr">→</div>
      <div class="node">regenerate to temp dir</div>
      <div class="arr">→</div>
      <div class="node">generation manifest<br/>(authoritative file list + sha256)</div>
      <div class="arr">→</div>
      <div class="node">compare every artifact<br/>against committed dir</div>
      <div class="arr">→</div>
      <div class="node">ok / changed / missing / stray</div>
      <div class="arr deny">⛔</div>
      <div class="node">exit 1 — merge blocked</div>
    </div>
    <div class="flow">
      <div class="node untrusted">naive gate: diff AGENTS.md only</div>
      <div class="arr dashed">⇢</div>
      <div class="node untrusted">green while policy.yaml drifts</div>
    </div>
  </div>
  <figcaption><b>Figure 21.1 — The full-artifact drift gate, and the gate it replaced.</b> The upper flow takes its file list from the machine-written manifest, so no human's inventory can omit an artifact. The lower dashed flow is the documented failure: a single-file diff cannot detect drift in files it never reads. The teaching purpose is that a gate's coverage is a property of its *inventory*, not of its diligence.</figcaption>
</figure>

Listing 21.1 is the whole cycle run against the bundled delivery example: generate, hand-edit, catch, regenerate, pass.

```bash
$ nornyx generate governed_delivery_control_plane.nyx --out generated
$ nornyx drift governed_delivery_control_plane.nyx --out generated ; echo "EXIT=$?"
Nornyx repo drift gate (full output)
Status: pass
Contract: governed_delivery_control_plane.nyx
All generated artifacts match the committed output.
EXIT=0

$ sed -i '/deny secrets_to_llm/d' generated/policy.yaml       # the Friday-afternoon edit
$ nornyx drift governed_delivery_control_plane.nyx --out generated ; echo "EXIT=$?"
Nornyx repo drift gate (full output)
Status: drift
Contract: governed_delivery_control_plane.nyx
  [CHANGED] policy.yaml
Fix: regenerate and re-copy artifacts (e.g. `nornyx generate <contract> --out <dir>`).
EXIT=1

$ nornyx generate governed_delivery_control_plane.nyx --out generated
$ nornyx drift governed_delivery_control_plane.nyx --out generated ; echo "EXIT=$?"
Status: pass
All generated artifacts match the committed output.
EXIT=0
```

**Listing 21.1 — A full drift-gate transcript.** Observed output, abridged only by removing repeated headers. The `--json` form of the same run emits a `nornyx.repo_drift_report.v0.1` document listing all eleven artifacts with per-artifact statuses, ten `ok` and one `changed`. Note what the final step did *not* do: it did not restore the deleted rule as a policy decision. It restored the projection of a rule that was never removed from the contract, which is the only place the rule ever lived.

The transcript makes the chapter's central asymmetry concrete. The gate cannot tell you whether the edit was malicious, expedient, or accidental, and it does not try. It tells you that a file which claims to be derived is not derived any more, and it refuses to let that state merge. Motive is a review question; divergence is a computation.

> **Case study — Forge.** Northstar's Engineering Platform wires exactly this into the merge lane for `northstar/payments-api`. The pipeline regenerates Forge's control artifacts and runs the full drift gate on every pull request, before the tests and before any approval step, on the reasoning that a run whose control artifacts are not the reviewed ones has nothing worth testing. On a Tuesday, a contributor under release pressure edits the generated `policy.yaml` directly — the same edit as this chapter's opening scenario — and pushes. The gate reports `[CHANGED] policy.yaml` and exits nonzero; the merge lane closes. The contributor's options are now the honest ones: change the contract, so that the loosening is reviewed as a policy change with the diff a reviewer expects to see; or file a bounded exception with an owner and an expiry, as Chapter 9 requires. What is no longer available is the third option they took in the opening scenario. Forge's thread continues in Chapter 29, where this gate joins lock verification and evidence validation in a full pipeline, and in Chapter 30, where the whole delivery contract is developed.

## 21.6 Above the repository: workspace checks

A within-repository gate cannot see a policy that is supposed to be identical across five repositories. The workspace layer addresses precisely that gap, and Chapter 8 introduced it; what belongs here is the mechanism.

`nornyx workspace-check` reads a `nornyx.workspace.yaml` manifest that declares canonical policies once and lists member contracts. For each member it compares the named policy against the canonical rule set — not textually, but as a *normalized set*, with every rule reduced to `deny <token>` or `require <token>` form, so that the shorthand `rules:` list and the explicit `deny:`/`require:` sub-blocks compare equal. **[implemented]** Statuses are per member and per policy: `ok`, `drift` (with sorted `missing` and `extra` lists), `missing` when the member does not declare the policy at all, `contract_missing`, and `synced`. The report schema is `nornyx.workspace_report.v0.1`; exit is `0` for pass or synced, `1` on drift, `2` on a manifest error.

Running it across two member repositories where one has lost a rule produces the diagnosis directly:

```text
{"status": "drift",
 "canonical_policies": {"SafeDeliveryPolicy": ["deny secrets_to_llm",
                                               "require human_approval_before_merge",
                                               "require tests_if_code_changed"]},
 "members": [{"path": "service-a/nornyx.nyx",
              "policies": [{"policy": "SafeDeliveryPolicy", "status": "ok"}]},
             {"path": "service-b/nornyx.nyx",
              "policies": [{"policy": "SafeDeliveryPolicy", "status": "drift",
                            "missing": ["deny secrets_to_llm"], "extra": []}]}]}
```

**Listing 21.2 — A workspace check finding a missing rule.** Observed `--json` output, exit code 1. The `missing` list is the diagnosis rather than a hint: it names the exact rule that diverged, which is what makes the report actionable in a pull-request comment.

The `--write` <span class="ix" data-ix="surgical write mode">surgical write mode</span> is the interesting design decision. It rewrites *only* the matched policy's rule block, replacing the `rules:`/`deny:`/`require:` sub-blocks with one canonical `rules:` block while preserving comments and every other block in the file. Re-running the check above with `--write` reports status `synced`, restores `deny secrets_to_llm` to the drifted member in the file's existing style, and a subsequent check exits `0`. **[implemented]**

What it refuses to do matters more than what it does. If a member does not declare the policy at all, or the member's contract file is missing, sync leaves it alone: "sync edits existing policies, it does not invent new blocks or files" (`nornyx/workspace.py`). The distinction is between repairing a *divergence* and making a *decision*. Restoring a rule to a policy that already exists is mechanical — the canonical set is the reviewed one and the member is meant to match it. Creating a policy block in a repository that never had one is an editorial act about what that repository is governed by, and a synchronization tool should not make it silently at three in the morning.

## 21.7 Context packs, and metadata that says what it is

The last generated artifact in this chapter is the one most likely to be over-read. `nornyx context-build` produces a <span class="ix" data-ix="context pack">context pack</span> under schema `nornyx.context_pack.v0.1`: an inventory of the repository files a declared context admits, with, for each entry, the file's SHA-256 and byte count, its taint label and channel, a trust level, an authority rank and the glob pattern that assigned it, a `may_define_policy` flag, and a provenance record naming the source type, a `repo://` URI, the repository root, and the digest again. **[implemented]** Content embedding is off by default, which keeps the pack smaller and avoids duplicating the repository into an artifact that may travel further than the repository does.

Everything in that entry is verifiable. A digest and a byte count are facts about a file; a `repo://` URI and a root are facts about where it was read from. The pack is a genuinely useful evidence input: it says which files a context admitted at a moment, and it binds each of them by digest, so a later reviewer can tell whether the file an agent read is the file that is there now.

The `authority_rank` field is where over-reading starts, and the artifact heads it off in its own body. Every pack carries a `rules` list, and the third entry is:

> "Authority rank is advisory metadata until a later enforcement goal."

**[implemented]** The two companions are equally direct: "Context pack content is evidence/reference input, not executable policy," and "Untrusted channels cannot override policy, approvals, or tool permissions."

That first sentence is a small piece of exemplary engineering honesty and worth generalizing. A rank ordering over context sources looks exactly like a conflict-resolution rule — higher-ranked source wins — and a reader who assumes it is one will build an argument on top of it: *the security model beats the untrusted web page because the pack ranks it higher.* Nothing in the toolchain enforces that. The rank is computed and recorded; whether any consumer honours it is entirely up to the consumer. Shipping the caveat inside the artifact, next to the field, is the same technique as the evidence report's embedded limitations in Chapter 20: the claim boundary travels with the data, so a reviewer who reads only the artifact still reads the boundary.

> **Design checkpoint.** For every derived artifact your system produces, write down four things: what computes it, whether the computation is deterministic, which gate compares it against its source and where that gate runs, and what a consumer is entitled to conclude from a field that looks like a policy but is only metadata. If any answer is "we rely on people not editing it," you have a convention, not a control.

## Summary

Generated artifacts are projections: they are what runs, and the contract is what was approved. Keeping those two aligned needs three mechanisms together — a label in the artifact, a deterministic generator, and a gate that makes divergence consequential — and any one alone degrades. Both of the repository's generators are byte-deterministic through forced line-feeds, imposed ordering, canonical JSON, and the absence of timestamps; the agentic generator emits a fixed set of exactly ten files and scans every rendered value so that a declaration cannot carry an endpoint, a credential, a command, a URL, or an IP literal. Diagnostics are an interface, not messages: stable upper-snake codes in prefixed namespaces let a pipeline tolerate one named condition and nothing else, and a three-value exit contract keeps "governance said no" distinguishable from "governance could not be evaluated." Two drift gates exist for two audiences — a baseline gate protecting the generator, and a full-artifact gate protecting the user's repository, which takes its file list from the generation manifest precisely because a hand-written inventory once missed the file that mattered. Above the repository, workspace checks compare normalized rule sets and repair divergences surgically while refusing to invent policies. And a context pack states in its own body that its authority ranking is advisory, which is how a claim boundary should travel.

- Authority lives in the contract; readership lives in the artifacts.
- Determinism turns "did anyone edit this?" into a computation.
- Take your gate's file inventory from the machine, not from prose.
- Stable diagnostic codes let a pipeline gate on a specific condition without an enumeration of all others.
- Exit `2` exists so a broken toolchain never impersonates a working control.
- Sync repairs divergence; it does not make editorial decisions.

## Review questions

1. Labelling, determinism, and gating are described as mutually dependent. For each pair, describe a concrete failure that occurs when the third is absent.
2. The project README lists seven generated artifacts; the generator writes eleven to twenty-two depending on the contract. Explain precisely how a gate built from the README's list fails, and what the manifest changes.
3. Why does `--as-of` never change a generated artifact's bytes, yet routinely change whether generation succeeds? What does that tell you about where the flag sits in the pipeline?
4. Forbidden-content scanning rejects a genuine runbook URL in a `purpose` field. Argue for and against relaxing this to a warning, and state which artifact class your answer depends on.
5. Give a concrete pipeline requirement that stable diagnostic codes make expressible and that a numeric scheme or prose messages would not. Then state what breaks if the code is renamed.
6. `workspace-check --write` restores a missing rule but will not create a missing policy block. State the principle behind the asymmetry and give one case where you would want the opposite behavior — and what you would have to add to make it safe.

## Exercises

1. Using the repository at the book's snapshot, reproduce Listing 21.1 end to end. Then repeat the experiment three more ways: delete a whole generated file, add an unexpected file to the output directory, and edit a task packet. Record the status the gate reports in each case (`changed`, `missing`, `stray`) and the exit code, and explain why a gate that only compared *existing* files would miss two of the three.
2. Write a continuous-integration step that runs the full drift gate, the agentic lock check, and evidence validation, and that must fail the build on any governance denial while distinguishing a toolchain failure from a policy failure. Use the documented exit-code contract, and state what your step does on exit `2` that it does not do on exit `1`.
3. Take the bundled support-network contract and introduce a forbidden value in a field of your choosing — a hostname, an IPv4 literal, or a key whose name contains a forbidden segment. Record the diagnostic code, confirm that no output directory is created, and then write a two-paragraph note for your own team on what the inertness of a declaration file does and does not guarantee to a peer system that consumes it.

## Further reading

- [@reproducible-builds] — the definitions and techniques behind byte-identical output, which every gate in this chapter presupposes.
- [@merkle] — content-addressed comparison, the primitive under the per-artifact digests in both manifests.
- [@slsa] — build-provenance levels, useful for locating where "this artifact was generated from this source" sits relative to "this artifact was generated by an authorized builder."
- [@sre-book] — the operational argument for gates that fail closed and for alerts a team does not learn to ignore.
- [@nornyx-repo] — the generators (`nornyx/generator.py`, `nornyx/agentic_artifacts.py`), the two drift gates (`nornyx/generation_drift.py`, `nornyx/repo_drift.py`), and the workspace layer (`nornyx/workspace.py`).
