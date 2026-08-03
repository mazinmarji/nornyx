---
chapter: 29
part: VI
title: "Continuous Integration and Delivery Gates"
---

# Continuous Integration and Delivery Gates

> **Opening scenario.** Forge's merge lane on `northstar/payments-api` fails at 10:47 with exit code 2. Not 1 — 2. The platform engineer who wired the pipeline knows what that means before opening the log: the build did not conclude that the policy said no; it concluded that it *could not establish what the policy is*. Someone has committed a hand-edit to a generated artifact, and the lock no longer matches the contract that supposedly produced it. The engineer's counterpart at a partner company, reviewing the same design a week earlier, had asked the question this chapter answers: "You have a contract, a checker, a generator, a lock, and an evidence validator. None of them can stop anything. So where does the stopping actually happen?" The answer is the pipeline. Continuous integration (CI) is where a Tier 1 toolchain borrows enforcement it does not itself possess — and the loan comes with conditions worth reading closely.

> **Learning objectives.**
> - Enumerate the governance gates a pipeline should run — check, generate-and-drift, lock verification, evidence validation, workspace check — and state what each one proves and with which exit code it fails.
> - Read the Nornyx repository's own CI as a reference design: candidate-identity verification, a version matrix with a Windows job, network-blocked wheel smoke tests, machine-checked zero-skip detection, public-boundary scanning, and a byte-compare drift gate.
> - Explain how release governance can fail closed: trusted publishing with no stored token, a strict tag-format eligibility gate, tag-to-version binding, and version locations enforced by tests.
> - Connect these mechanisms interpretively to supply-chain frameworks without claiming a level or a certification.
> - State precisely what the repository does *not* apply to itself, and why shipping a control and self-applying it are different commitments.

> **Prerequisites.** Chapter 12 (locks and content addressing), Chapter 13 (assurance tiers), Chapter 15 (the five-test rule, zero-skip gates, and the six-layer pipeline sketch of Figure 15.2), Chapter 18 (profiles, modules, and the two lock structures), Chapter 20 (evidence validation), Chapter 21 (drift gates and diagnostic codes), and Chapter 28 (the authoring lifecycle whose merge and lock stages this chapter operationalizes). Chapter 15 sketched the pipeline as six layers of obligation; this chapter builds it from real parts.

## 29.1 Where a design-time tool borrows enforcement

Everything Nornyx produces is advisory until something refuses to proceed. The checker exits nonzero; the drift gate exits nonzero; the lock verifier exits nonzero — and a developer at a terminal can read the message and run the next command anyway. The component that converts those exit codes into consequences is the pipeline: a CI system configured so that a red gate blocks a merge, and a blocked merge blocks a deployment. This is the precise sense in which Chapter 13's Tier 1 claims become operationally meaningful — not because the toolchain gained enforcement power, but because an organization *arranged its delivery path* so that the toolchain's verdicts sit on it.

That arrangement rests on a small interface: the <span class="ix" data-ix="exit-code contract">exit-code contract</span>. Nornyx's governance surfaces distinguish three outcomes — success (0), a governance failure (1), and an inability to establish the governance state at all: parse failures, malformed evaluation instants, and lock failures exit 2 **[implemented]**. The distinction is not cosmetic. Exit 1 means "the policy was evaluated and said no"; exit 2 means "no trustworthy evaluation happened." A pipeline may reasonably route the two differently — a policy denial goes back to the author, an integrity failure goes to whoever owns the artifacts — and a pipeline that folds them together will eventually treat "I could not read the lock" as an ordinary test failure to be retried until it goes away. The opening scenario's engineer routed on the code, which is why the incident took minutes instead of an afternoon.

> **Key idea.** A <span class="ix" data-ix="governance gate">governance gate</span> is a pipeline step whose failure blocks a consequence, whose verdict comes from a deterministic tool, and whose meaning is written down. All three clauses matter. A step that fails without blocking is a report; a step that blocks on a nondeterministic verdict is a flake generator that trains people to re-run; and a step whose meaning is undocumented gets deleted during the next pipeline cleanup by someone who cannot say what it was for.

## 29.2 The gate set

Table 29.1 assembles the gates this part of the book has been accumulating, each with the command that implements it at the snapshot, what a green result actually proves, and what it cannot prove. Every row is **[implemented]** as a tool behavior; assembling them into one pipeline is the adopting organization's work, for which the repository supplies documented recipes **[guidance]**.

| Gate | Command | A green result proves | It does not prove |
|---|---|---|---|
| Contract validity | `nornyx check <contract> --as-of <instant>` | The contract parses, references resolve, composed schemas and structural checks pass, and time-dependent records (approvals, exceptions, evidence freshness) are valid *at the pinned instant* | That any rule means what its wording suggests (Chapter 28), or that anything enforces it |
| Artifact drift | `nornyx drift <contract> --out <dir>` | Every committed generated artifact matches a fresh regeneration by content hash — none changed, missing, or stray | That the contract producing them was ever reviewed; drift compares bytes, not intent |
| Network lock | `nornyx agentic-network lock-check <contract> --artifacts <dir> --lock <lock>` | The contract digest, pack identities and hashes, schema versions, per-record digests, and per-artifact hashes all match the lock | Who wrote the lock; a hostile local writer can regenerate a consistent one — repository history review carries that (Chapter 12) |
| Evidence validity | `nornyx agentic-network evidence-validate <contract> --events <file> --strict` and `nornyx evidence validate <path> --as-of <instant>` | Supplied records conform to the locked contract revision: bindings, ordering, occurrence rules, human-only grants | That the records are complete or true; validation proves conformance of what was supplied, nothing more (Chapter 20) |
| Workspace consistency | `nornyx workspace-check --manifest <manifest>` | Every member repository's copy of each canonical policy equals the canonical rule set | Anything about members not listed in the manifest, or about rules the manifest does not declare |

**Table 29.1 — The governance gate set, with each gate's honest scope.** The right-hand column is the one to keep: a pipeline description that lists only the middle column is the raw material of the overclaims Chapter 14 catalogued. Note the `--strict` flag on evidence validation — without it the command reports a failing status but exits zero **[implemented]**, a deliberate affordance for exploratory use that becomes a silent hole if copied into a pipeline unmodified.

Two of these gates deserve a demonstration rather than a description, because their failure modes are the ones pipelines exist to catch.

The drift gate's characteristic catch is the *hand-edited artifact* — a change to `policy.yaml` or `AGENTS.md` that never went through the contract, which is to say a policy change that skipped review. Chapter 28 showed the transcript: one appended comment line, `[CHANGED] policy.yaml`, exit 1. The lock gate's characteristic catch is subtler: the *stale pair*, where contract and artifacts are each internally fine but no longer each other's. Listing 29.1 shows both directions against the repository's bundled support-network example.

```text
$ # Tamper with one generated artifact, keep the contract:
$ nornyx agentic-network lock-check support_network.nyx \
    --artifacts artifacts --lock nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z
{ "status": "fail", "diagnostics": [ {
    "code": "AN_LOCK_ARTIFACT_MISMATCH",
    "message": "On-disk artifact 'capability_matrix.json' does not match the locked hash." } ] }
# exit 1

$ # Restore the artifacts, edit one word of the contract instead:
$ nornyx agentic-network lock-check support_network.nyx \
    --artifacts artifacts_clean --lock nornyx.agentic_network.lock --as-of 2026-07-17T00:00:00Z
# diagnostics include:
#   AN_LOCK_SOURCE_STALE      — the contract digest no longer matches the lock
#   AN_LOCK_RECORD_MISMATCH   — the edited record's digest changed
#   AN_LOCK_ARTIFACT_MISMATCH — every regenerated artifact now differs
# exit 1
```

**Listing 29.1 — The lock gate fails closed in both directions.** Abridged real transcripts produced against package 1.11.0 on `examples/agentic_network_support/support_network.nyx`. The diagnostic names matter operationally: `AN_LOCK_ARTIFACT_MISMATCH` alone means the artifacts were touched; `AN_LOCK_SOURCE_STALE` means the contract moved past its lock, which is a different team's problem. A one-word edit to a delegation's purpose string was enough to trip the second case, because the lock binds per-record content digests, not just file names — the sensitivity is the feature.

Between the artifact drift gate and the lock, there is a third determinism check that costs almost nothing and belongs in the same family: generate twice and compare bytes. The repository's reference workflow does exactly this — regenerate into a second directory and compare with a recursive directory diff, failing on any differing, missing, or extra file **[implemented]**. It proves a property neither of the other gates proves: that generation itself is deterministic *in this environment*, on this operating system, with these dependency versions. Chapter 12 argued that byte-determinism is what makes hash comparison meaningful at all; this step is where the argument gets checked rather than assumed.

## 29.3 The reference pipeline, read closely

The Nornyx repository's own CI workflow is worth reading as a design document, because several of its choices answer assurance questions that most pipelines never ask. Figure 29.1 lays out the flow; the paragraphs after it take up the five choices that generalize.

<figure class="nx-fig" id="fig-29-1">
  <div class="fig-body">
    <div class="layers">
      <div class="layer authority" data-note="git rev-parse HEAD must equal the PR head SHA">Candidate identity — check out and verify the exact proposed revision</div>
      <div class="layer" data-note="Python 3.10–3.13 on Linux, plus a full Windows job">Matrix — prove the advertised support range, not one interpreter</div>
      <div class="layer" data-note="build wheel · install into fresh venv · socket-level network guard · smoke outside all source roots">Ship-shape — is the thing under test the thing that ships?</div>
      <div class="layer" data-note="pinned frameworks asserted; JUnit-parsed skip count must be 0; test count must be nonzero">Zero-skip — a skipped governance test fails the build</div>
      <div class="layer authority" data-note="check → resolve → generate → regenerate + byte-compare → lock + lock-check → evidence-validate --strict ×2 → audit package">Governance chain — the reference agentic-network gate sequence</div>
      <div class="layer" data-note="lint · public-boundary marker scan · compatibility-migration check · benchmark must self-report GO">Repository hygiene — content and compatibility boundaries</div>
    </div>
  </div>
  <figcaption><b>Figure 29.1 — The continuous-integration governance flow, as layered obligations.</b> Drawn from the repository's <code>.github/workflows/ci.yml</code> and <code>scripts/agentic_network_ci.py</code> at the snapshot. The two authoritative bands are the ones a governance reader should not let a pipeline drop: candidate identity, because every later verdict is a statement about a specific revision, and the governance chain, because it is where the gate set of Table 29.1 actually runs. The teaching purpose is that a governance pipeline is not a list of tools but a chain of custody: each band assumes the one above it held.</figcaption>
</figure>

**Candidate identity comes first.** Every job checks out the pull request's head commit explicitly and then *verifies* it: `test "$(git rev-parse HEAD)" = "${{ github.event.pull_request.head.sha }}"` **[implemented]**. This one-line step closes a gap most pipelines carry unexamined — the assumption that what the runner checked out is what the reviewer will approve. Every subsequent verdict in the run is a claim about a revision, and this step is what pins which one. It is the pipeline-side twin of Chapter 9's exact revision binding: an approval bound to `9f3c1a7` is only meaningful if the checks that informed it also ran on `9f3c1a7`.

**The matrix proves the advertised range.** The test job runs on Python 3.10 through 3.13, with a comment in the workflow stating the intent: prove the advertised requires-python range, "not just one version." A separate job repeats the full test, build, and wheel-smoke sequence on Windows **[implemented]**. For a governance toolchain this is not portability hygiene; it is claim discipline. Chapter 12 showed that generated artifacts force line-feed newlines precisely so output is byte-identical across platforms — a determinism claim that is only evidence-backed because a Windows runner regenerates and re-hashes the same bytes.

**The wheel smoke is network-blocked, and the block is itself tested.** Several jobs build the candidate into a wheel, install it into a fresh virtual environment, and run smoke checks from outside every source directory — so a green result cannot secretly depend on the working tree. The interesting part is the guard: the harness installs a hook into the environment that intercepts socket use, logs any attempt to a file, and fails the run if the file is non-empty; and before trusting the guard, it runs a self-test that deliberately triggers it and checks that the expected evidence appears **[implemented]**. That last clause is Chapter 15's failure-injection discipline applied to the pipeline's own instrumentation: a negative control for the negative control. "The wheel makes no network calls" is thereby a tested claim rather than an architectural hope — scoped, as always, to the paths the smoke exercises.

**Skips are machine-checked to zero.** Chapter 15 presented the mechanism in full (Listing 15.3): the framework-adapter jobs assert the exact pinned framework versions, parse their own JUnit-format results, and fail if any test skipped *or if the test count is zero* **[implemented]**. In this chapter's terms the point is placement: the zero-skip check is a gate about the *pipeline's evidentiary integrity*, not about the code, and it belongs in the same band as candidate identity — both defend the meaning of every other green check.

**The governance chain is one script with a documented step list.** The quality job runs the reference agentic-network workflow: check, governance resolve, generate, regenerate-and-byte-compare, lock and lock-check, external evaluation import, threshold validation, two framework demonstration paths, strict evidence validation of both resulting streams, a human-approval and revision-binding inspection, and finally assembly of an `audit-package/` directory containing the lock, the artifacts, the evaluation report, the evidence reports, and a manifest — exiting nonzero on any failure **[implemented]**. The audit package is the step pipelines most often lack: the run does not merely pass, it *deposits the object a reviewer would need* to re-examine the pass. The documentation publishes the whole thing as a copy-paste job for adopters and notes that it needs no secrets **[guidance]**.

Alongside these, the quality job runs a <span class="ix" data-ix="public-boundary scan">public-boundary scan</span> — a marker-based check that no private downstream platform, product, or customer identifiers appear anywhere in the public repository **[implemented]**. It is a governance gate over *content* rather than behavior, and it earns its place in the list because it demonstrates the pattern at its most general: a written boundary policy, a deterministic scanner, a CI step that fails closed, and a test file that pins the scanner's own behavior.

> **Case study — Forge.** Northstar's Engineering Platform assembles Forge's pipeline on `northstar/payments-api` from these parts, in three lanes with deliberately different failure meanings. The *proposal lane* runs on every Forge-opened pull request: candidate-identity verification, then `nornyx check` on the delivery contract at a pinned instant, then `nornyx drift` over the committed `.nornyx/` directory, then the project's ordinary tests, then a zero-skip assertion over the governance test modules. Exit 1 anywhere returns the work to Forge with the diagnostic; humans are not paged. The *merge lane* runs when a human requests merge to a protected branch: everything in the proposal lane, plus lock verification, plus validation of the evidence stream Forge's harness produced for the change, plus the workspace check against `northstar-governance` — and its failures page the platform team, because a red merge lane means either a policy refused or an integrity failure, and both need a person. The *release lane* fires only from a published release whose tag matches the exact version convention, and is described in Section 29.4. The design decision worth copying is the routing: the same gate can appear in two lanes with different consequences, and the lane — not the gate — decides who is interrupted. The 10:47 failure in the opening scenario was the merge lane doing exactly what it was built to do: a developer had "fixed" a generated `policy.yaml` by hand to unblock a test, the drift gate flagged the changed artifact, and the lock check exited 2 — blocking the merge lane entirely, which is Forge's declared fail-closed posture. Chapter 30 follows what happens next.

## 29.4 Release governance

A release is the pipeline's highest-consequence action, and the repository's release machinery is built around a single principle: *no step trusts an assertion it can instead verify, and no credential exists to steal.*

Publication uses <span class="ix" data-ix="trusted publishing">trusted publishing</span>: the workflow authenticates to the package index by an OpenID Connect (OIDC) identity token minted for that specific workflow run, and the index verifies the workflow's identity directly — "no API token stored anywhere," as the workflow's own header puts it **[implemented]**. The security consequence is structural rather than procedural. There is no long-lived secret whose leak enables publication from anywhere; the only thing that can publish is the registered workflow, in the registered repository, running in a named deployment environment — and that environment can be configured to require a human reviewer before the job runs, which the release documentation notes "matches Nornyx's own 'human approval before release' posture."

Eligibility is a *positive* gate. Publication fires only on a published release whose tag matches the anchored pattern `^v[0-9]+\.[0-9]+\.[0-9]+$` exactly — not "anything that is not an adapter tag," but a whitelist of one shape, so a prerelease suffix, an adapters tag, or an unrelated tag is excluded by construction. Listing 29.2 shows the check, which is short enough to quote whole.

```yaml
check-core-tag:
  # Only a 'release' event has a tag_name to evaluate; workflow_dispatch has
  # none, so it is correctly excluded from ever setting eligible=true.
  if: github.event_name == 'release'
  runs-on: ubuntu-latest
  outputs:
    eligible: ${{ steps.check.outputs.eligible }}
  steps:
    - name: Verify the release tag matches the core vX.Y.Z convention exactly
      id: check
      run: |
        tag="${{ github.event.release.tag_name }}"
        if [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
          echo "eligible=true" >> "$GITHUB_OUTPUT"
        else
          echo "eligible=false" >> "$GITHUB_OUTPUT"
        fi
```

**Listing 29.2 — The strict tag-format eligibility gate.** From `.github/workflows/release.yml` at the snapshot. Two design details reward attention. The comment records *why* manual dispatch can never publish: it has no tag to evaluate, so eligibility defaults closed rather than being explicitly denied — absence of qualification, not presence of a block. And the gate is a separate job whose output the publish job requires, so the eligibility decision is visible in the run graph rather than buried in a conditional.

The adapters distribution goes one step further with <span class="ix" data-ix="tag-to-version binding">tag-to-version binding</span>: its tag must match `adapters-vX.Y.Z` *and* that version must equal the adapter package's own declared version at the exact commit the tag targets. A mismatch — tagging `adapters-v0.2.1` while the package still declares `0.2.0` — sets eligibility false with an explicit error, "fails closed rather than publishing" **[implemented]**. The workflow also states a boundary that reads like one of Chapter 16's non-goals: it "never creates, moves, or repairs tags." The version string a user will install under is thereby bound to the version string the code declares, at the revision the tag names — a three-way binding in exactly Chapter 12's sense, enforced at the moment of highest consequence.

The last layer is the least glamorous and catches the most common failure: <span class="ix" data-ix="version-location enforcement">version locations enforced by tests</span>. The package version appears in seven equality-enforced locations — the build metadata, the package's own `__version__`, the repository manifest, the versioning document, the README's install pin, and two test fixtures — and four named test files collectively fail if any of them disagree **[implemented]**. The release process document also records the rules "that bite": published versions are immutable, so a wrong build means bumping and releasing again, never overwriting; and artifacts are built by the workflow, never uploaded by hand, so the artifact provably corresponds to the tag. Even the release workflow's own policy has a regression test — a test file exists whose subject is the workflow configuration itself **[implemented]** — which is the self-referential move this book keeps returning to: the control on the release is treated as code, and code gets tests.

## 29.5 Reading the pipeline through supply-chain frameworks

The mechanisms above were built as engineering choices, but they land on territory that supply-chain security frameworks have mapped, and the mapping is worth making — interpretively, in this book's standing sense: these are observations about conceptual correspondence, not claims of any level, attestation format, or certification.

The SLSA framework organizes supply-chain integrity around build provenance: knowing what was built, from what sources, by which build system, and hardening the build platform against tampering [@slsa]. The candidate-identity verification, the built-from-the-same-commit wheel discipline, and the tag-to-version binding are all provenance-flavored controls in this sense — they bind the published artifact to a specific revision through verified steps. What the repository does *not* produce is a signed provenance attestation in any standard format; the binding lives in workflow configuration and test enforcement, not in a verifiable statement that travels with the artifact. In-toto's contribution is the vocabulary for that gap: a supply chain as a layout of named steps, each producing signed link metadata that a verifier can check end to end [@in-toto]. The reference pipeline has the *steps* and even assembles an audit package; it does not sign links. Sigstore supplies the piece the release workflow does use — OIDC-verified workload identity in place of stored credentials — which is the same keyless-trust idea that underpins its signing infrastructure, applied here to publication rather than to signatures [@sigstore].

The reproducible-builds discipline maps onto the byte-compare gates: the practice of making builds bit-for-bit repeatable so that independent parties can verify a binary against its source [@reproducible-builds]. Nornyx's timestamp-free, canonically ordered, line-feed-normalized generation is this discipline applied to governance artifacts, and the regenerate-and-compare CI step is its verification. And the Secure Software Development Framework provides the practice-level frame for the rest — protecting the software (branch and release controls), verifying it (the test matrix, the zero-skip gates), and responding to what verification finds [@nist-ssdf]. A team asked by a security review "where are you on SSDF" can answer with rows of Table 29.1 mapped to practices; a team asked "what SLSA level are you" should decline the question's framing unless it has done the specific work each level names.

> **Misconception.** *"Our pipeline compares hashes and uses OIDC publishing, so we have a SLSA level."* Levels in that framework attach to specific, named requirements about provenance generation and build-platform hardening, assessed as a whole — not to the presence of individual practices that resemble them. The honest sentence is the interpretive one: "our pipeline implements provenance-style bindings at these named points, and produces no standard attestation." It is less impressive and survives the follow-up questions.

## 29.6 The gap between shipping a control and living under it

There is one observation about this repository that an honest chapter must make, because the repository's own audit materials make it: Nornyx does not run its full drift-gate discipline against a self-governing contract of its own. There is no root `nornyx.nyx` describing the Nornyx project, and no committed generated directory for such a contract that a `nornyx drift` step could gate **[implemented]** — verified by inspection at the snapshot. What CI does instead is adjacent: it checks the flagship bundled *example* contract on every run, executes the byte-compare drift gate against the agentic-network *example*, and enforces self-consistency through a battery of meta-tests over documentation, manifest metadata, README commands, and release-workflow policy. The recipe the documentation urges on adopters — commit the generated directory, gate every build on `nornyx drift` — is not applied to the repository that publishes the recipe.

It would be easy to score this as hypocrisy and move on, and that would waste the lesson. The gap is real, and the reasons it exists generalize to every organization that builds governance tooling.

First, *shipping a control and applying it to yourself are different commitments with different costs*. A shipped control must work; a self-applied control must be *lived with* — every contract edit now requires regeneration, every pipeline change risks blocking the project's own merges, and the maintainers pay the fail-closed tax daily rather than recommending it. Organizations systematically underestimate this second cost because they price it at the first one.

Second, self-application is the strongest cheap evidence a control vendor can offer. Chapter 16 read the project's no-go audit as assurance culture; a self-governing contract would be the same kind of evidence about the drift gate — not proof of correctness, but proof that the makers accept the constraint they sell. Its absence is a fact a procurement review is entitled to weigh, and the repository's own audit-honesty makes the weighing easy: the gap is discoverable from the repository, not concealed by it.

Third, the gap has a *shape* worth learning to recognize elsewhere: the control exists, the recommendation exists, the demonstration exists — against an example — and the last step, turning the control on where it would constrain its own authors, is the one not taken. When you evaluate any governance product, ask the vendor precisely this question and expect the answer to be partial. Then ask it of your own platform team, whose deployment pipeline for the policy engine is, in most organizations, governed more loosely than anything the policy engine governs.

> **Assurance boundary.** Run the eight questions against the claim "Forge's merge lane fails closed on governance-artifact drift." What is guaranteed: a merge attempted *through the lane* is blocked when the drift or lock gate exits nonzero. Which component enforces it: the CI system and the branch-protection rule requiring the check — not Nornyx, which only supplies the exit code. What evidence proves it: the run logs, the required-check configuration, and a negative test that submits a deliberately drifted artifact and observes the block. What assumptions are required: that branch protection is on, that the required-checks list names these gates, that administrators do not merge past a red check. How it can be bypassed: repository administrators, force-push permissions, a lane that does not exist for direct pushes — all outside the governance layer and taken up in Chapter 30's bypass analysis. What happens when the enforcing component fails: a CI outage blocks everything, which is the fail-closed cost made visible. Which tier: the *decision* is Tier 1 evidence; the *blocking* is the platform's, and inherits the platform's assurance, not the contract's. What remains unproven: everything about what Forge does off the delivery path.

## 29.7 Design rules for governance pipelines

Compressing the chapter into rules a team can apply in a week:

1. **Route on the exit-code contract.** Treat "policy said no" (1) and "could not establish the policy" (2) as different incidents with different owners. Never retry exit 2.
2. **Verify candidate identity first.** Every gate verdict is about a revision; pin which one before running anything, and bind approvals to the same revision the checks ran on.
3. **Gate the full artifact set by hash, and prove determinism in-pipeline.** Regenerate-and-byte-compare costs seconds and is the premise of every other hash comparison.
4. **Make evidence validation strict in lanes with consequences.** The exploratory default that exits zero on failure must not survive the copy-paste into the merge lane.
5. **Machine-check the absence of skips wherever a governance claim is tested.** A skipped claim test silently converts a supported claim into an unsupported one (Chapter 15).
6. **Assemble an audit package on every governed run.** A pass that deposits its lock, artifacts, reports, and manifest can be re-examined; a bare green check mark cannot.
7. **Prefer identity-based publication with positive eligibility gates.** No stored token, a whitelist tag shape, tag-to-version binding, and version locations under test.
8. **Apply your own controls to yourself, and where you do not, say so.** The gap will be found; the only choice is whether it is found in your documentation or in your incident review.

> **Design checkpoint.** Take your current delivery pipeline and mark, for each of the eight rules, one of: *holds*, *holds partially*, *does not hold*, *cannot tell*. The last category is the finding: a pipeline whose governance properties cannot be determined from its configuration is a pipeline whose properties will be determined during an incident.

## Summary

A design-time governance toolchain acquires operational force only where a pipeline routes its exit codes into consequences, and the exit-code contract — success, governance failure, integrity failure — is the narrow interface that makes routing possible. The gate set is small and specific: contract validation at a pinned instant, full-artifact drift comparison by hash, lock verification that fails closed in both the tampered-artifact and stale-contract directions, strict evidence validation, and cross-repository workspace checks. The repository's own CI adds the disciplines that defend the gates' meaning: verified candidate identity, a version matrix with a Windows job that makes cross-platform determinism a tested claim, network-blocked wheel smokes whose guard is itself failure-injected, machine-checked zero-skip detection, a public-boundary content scan, and a reference governance chain that ends by assembling an audit package. Release governance stacks identity-based trusted publishing with no stored token, a positive tag-format eligibility gate, tag-to-version binding that fails closed, and seven version locations enforced by four test files — with the release workflow's own policy under regression test. These mechanisms correspond recognizably to the concerns of supply-chain frameworks — provenance, verifiable steps, keyless identity, reproducibility, secure-development practices — without amounting to any level or certification, and the correspondence should be stated exactly that carefully. Finally, the repository does not run its recommended drift-gate discipline against a self-governing contract of its own, and the gap teaches more than it embarrasses: shipping a control and living under it are different commitments, self-application is the cheapest strong evidence a toolmaker can offer, and the question "do you apply this to yourselves?" belongs in every evaluation — including of your own platform team.

- Exit 1 and exit 2 are different incidents with different owners.
- Candidate identity verification is the pipeline-side twin of exact revision binding.
- `--strict` is the difference between an evidence report and an evidence gate.
- A green run should deposit an audit package, not just a check mark.
- Positive eligibility gates: publication is permitted by matching a shape, not by failing to match a blocklist.
- The last step of dogfooding — constraining the control's own authors — is the step to ask every vendor about.

## Review questions

1. A pipeline retries any failed governance step up to three times before paging. Using the exit-code contract, explain which failures this policy handles acceptably and which it converts into a silent hazard, with one concrete scenario for the latter.
2. The lock-check in Listing 29.1 produced `AN_LOCK_SOURCE_STALE` alongside `AN_LOCK_RECORD_MISMATCH` and ten artifact mismatches after a one-word contract edit. Explain why a lock that binds per-record digests produces this cascade, and why a reviewer should read the *source-stale* diagnostic first.
3. The wheel-smoke's network guard runs a self-test that deliberately triggers it before the real smoke runs. Name the Chapter 15 discipline this instantiates, and describe the specific false confidence that a guard without a self-test can produce.
4. The core release gate is a positive whitelist (`^v[0-9]+\.[0-9]+\.[0-9]+$`) rather than a blocklist of known-bad tag shapes. Give two tag shapes that a plausible blocklist would miss and the whitelist excludes by construction.
5. Explain the difference between "our pipeline byte-compares regenerated artifacts" and "our builds are reproducible" in the sense of the reproducible-builds discipline. What additional commitments does the second sentence carry?
6. Construct the strongest defense you can of the repository's decision not to maintain a self-governing contract, and then state the single piece of evidence its absence denies to an evaluator that nothing else in the repository supplies.

## Exercises

1. **Build the minimal governance lane.** For a repository with a `.nyx` contract (create one with `nornyx init` if needed), write a CI job that: verifies candidate identity, runs `nornyx check --as-of` with a pinned instant, regenerates and runs `nornyx drift` over a committed output directory, and uploads the drift report as a build artifact. Then commit a hand-edit to one generated file on a branch and confirm the lane blocks with the diagnostic naming the file. Record the total wall-clock cost of the lane and state whether it is small enough to run on every pull request.
2. **Audit your own release path.** For one package your team publishes anywhere (an internal registry counts), answer in writing: what credential can publish it, where is that credential stored, what tag or version shapes can trigger publication, what binds the published version string to the source revision, and how many locations declare the version — and what detects their disagreement. Compare each answer against Section 29.4 and produce a ranked list of the three cheapest improvements.
3. **Find your dogfooding gap.** Identify every control your platform team ships to other teams (linting rules, deployment gates, policy checks, security scanners). For each, determine whether the shipping team's own repositories are subject to it, and classify the gaps using Section 29.6's shape: control exists / recommendation exists / demonstrated on an example / not self-applied. Write the one-paragraph disclosure you would add to your documentation for the largest gap — or the migration plan if writing the disclosure turns out to be more embarrassing than closing the gap.

## Further reading

- [@slsa] — the supply-chain levels framework; read the level requirements to see precisely why Section 29.5 declines to claim one.
- [@nist-ssdf] — secure-development practices; the natural vocabulary for presenting Table 29.1 to a security-assessment audience.
- [@in-toto] — supply chains as layouts of verifiable steps with signed link metadata; the formal version of what the audit package gestures at.
- [@sigstore] — keyless signing and OIDC workload identity; the trust model behind publication with no stored token.
- [@reproducible-builds] — bit-for-bit build verification as a community practice; the discipline the byte-compare gates borrow, and the standard for what "reproducible" should be allowed to mean.
