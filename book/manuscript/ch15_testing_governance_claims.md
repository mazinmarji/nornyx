---
chapter: 15
part: III
title: "Testing Governance Claims"
---

# Testing Governance Claims

> **Opening scenario.** Forge, Northstar Services' software-development agent, has been running on the `northstar/payments-api` repository for a quarter. Its governance is written down, reviewed, and wired into continuous integration (CI). The team's control description says: *merges to protected branches require an approval from a named reviewer who is not the proposer.* The Risk & Audit chief, preparing for an external assessment, asks for the test that proves it. The team produces one: a test that constructs an approval and asserts the merge proceeds. She reads it and asks the obvious follow-up — *where is the test where the approval is missing?* There is one, in a file nobody has run for six weeks, because it imports a library the CI image no longer installs, so it has been skipping. The CI dashboard is green. It has been green throughout. In the pipeline output, between four hundred lines of passing tests, sits a single letter `s`.

> **Learning objectives.**
> - Restate a governance claim as a testable proposition, and identify the surface, mechanism, and condition each proposition binds.
> - Apply the five-test rule — allow, deny, failure, bypass, evidence — to a claimed surface, and state what each test must assert to be worth anything.
> - Distinguish a conformance suite from a unit-test suite, and explain what obligation a conformance suite transfers to an implementer.
> - Practise failure injection: making the enforcement mechanism itself fail, and asserting the system's behavior under that failure.
> - Express policy-system invariants as properties rather than examples, in particular decision determinism and monotonic composition.
> - Explain why a silently skipped test is a governance failure rather than a hygiene problem, and design a gate that makes skips fail closed.
> - Read a governance benchmark critically: what its scenarios prove, what it declares as a non-win, and what its defect findings do and do not imply.

> **Prerequisites.** Chapter 3 (the eight assurance questions), Chapter 7 (deterministic policy evaluation), Chapter 8 (composition and the silent-weakening problem), Chapter 9 (approvals as bound records), Chapter 13 (assurance tiers), and Chapter 14 (coverage inventories, bypass, and negative controls). Chapter 14's five test categories are the direct ancestor of this chapter's five-test rule.

## 15.1 A governance claim is a testable proposition

Most governance documentation is written in a register that resists testing. "Access to production is controlled." "Sensitive data is protected." "Human oversight is maintained." Each describes an intention and a posture. None can be false in any specific way, which is another way of saying none can be true in any specific way either.

A <span class="ix" data-ix="governance claim">governance claim</span>, in the sense this book uses, is different: a proposition about a system that could be shown false by a specific observation. Turning documentation into claims is mechanical once you know what to look for. Each claim binds three things, and if any of the three is unstated the sentence is not yet a claim:

1. A **surface** — the named point at which the claim applies, drawn from the coverage inventory of Chapter 14.
2. A **mechanism** — the component that makes the claim true, and its position relative to the effect.
3. A **condition** — what must hold in the deployment for the mechanism to be in the path.

"Access to production is controlled" has none of the three. "A merge to a protected branch, requested through the governed merge surface, is refused unless a valid approval record exists that names a human reviewer other than the proposer and is bound to the exact revision being merged" has all three, and consequently has a shape a test can attack. Notice how much of Chapters 9 and 14 is compressed into that sentence: *governed merge surface* is the coverage qualifier, *refused unless* is the mechanism's decision rule, and *bound to the exact revision* is a condition on the approval record.

> **Key idea.** The question "how do we test governance?" is usually unanswerable because the thing being tested is not yet a proposition. Rewriting the control description as a claim with surface, mechanism, and condition is not preparation for the testing work; it is most of the testing work. Once the claim is precise, the tests it requires are nearly forced.

## 15.2 The five-test rule

For each claimed surface, five tests are required — call it the <span class="ix" data-ix="five-test rule">five-test rule</span>. Fewer than five leaves a specific, nameable defect undetectable. The rule generalizes the categories of Figure 14.2 into an obligation.

**Test 1 — Allow.** A legitimate request on the claimed surface is permitted, the protected action runs *exactly once*, and the allow decision is recorded *before* the action runs. The ordering assertion is the part usually omitted, and it is the part that matters: a system that executes the action and then records a decision has produced a log entry, not an enforcement point, and will happily record allow decisions for actions that were never going to be stopped. The exactly-once assertion catches a different defect — a retry or a duplicated wrapper that executes the effect twice under one authorization.

**Test 2 — Deny.** An illegitimate request produces a deny decision with a specific code, the protected action does not run, and *no side effect of the action exists*. Asserting the absence of a side effect requires that the action have an observable side effect to assert about; this is why governance test fixtures instrument their protected callables rather than using pure functions. As Chapter 14 argued, a test that asserts only "an exception was raised" is satisfied by any exception from any cause.

**Test 3 — <span class="ix" data-ix="failure test">Failure of the action</span>.** The request is authorized, the action runs, and the action itself raises. The system must record the failure and must *not* record a success. This test protects the evidence stream from a specific corruption: a governed run in which the record says an operation completed and the world says it did not. In the Nornyx adapters as implemented at the snapshot, the post-action observation is recorded only after the wrapped callable returns, so an action that raises produces no `tool_invoked` observation. That behavior is the thing test 3 pins.

**Test 4 — Bypass.** Either the bypass is detected and the test asserts the detection, or the bypass is undetectable and the test asserts that it runs ungoverned exactly as the coverage inventory declares. Chapter 14's worked example is the second form. This test is the one that keeps the assurance tier honest over time.

**Test 5 — <span class="ix" data-ix="evidence test">Evidence</span>.** The records produced by tests 1 through 4 form a stream that validates: the events are present, in the right order, with the right bindings, and the validator says so. This test catches the failure mode that is invisible to all four others — a system that enforces correctly and produces evidence that cannot be used. The repository's adapter suite includes a native end-to-end case that asserts the exact event sequence and then validates it, shown in Listing 15.1.

```python
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    ...
    events = recorder.stream()["events"]
    assert [event["event_type"] for event in events] == [
        "capability_requested",
        "capability_allowed",
        "tool_invoked",
    ]
    report = recorder.validate()
    assert report["status"] == "pass"
```

**Listing 15.1 — An evidence test asserts the sequence and the verdict.** From `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py`, running against the real pinned framework rather than a stub of it. Two assertions do different work: the first pins the exact event sequence a single governed invocation must produce, so a change that drops or reorders an event fails loudly; the second runs the validator, so a stream that is well-formed in this test's opinion but rejected by the actual validator also fails.

Table 15.1 states the obligation as an audit instrument. Its most useful column is the last one, which names what the absence of each test silently permits.

| Test | Must assert | Absence silently permits |
|---|---|---|
| Allow | Action runs exactly once; allow decision recorded before execution | An after-the-fact logger presented as an enforcement point; double execution under one authorization |
| Deny | Deny effect with a named code; action did not run; zero side effects | Policy evaluated and then ignored; an unrelated exception mistaken for enforcement |
| Failure | Failure recorded; no success record | Evidence asserting completion of work that failed |
| Bypass | Detection recorded, *or* ungoverned execution matching the declared inventory | Cooperative boundary drifting into an assumed mandatory one |
| Evidence | Full stream validates against the evidence contract | Correct enforcement that cannot be reconstructed or audited |

**Table 15.1 — The five-test rule per claimed surface.** The teaching purpose is diagnostic: given any governance test suite, the fastest way to find its blind spot is to sort its tests into these five rows and look for the empty one. In practice the empty rows are almost always *failure* and *bypass*. Figure 15.1 places the five tests on the enforcement path each one attacks.

<figure class="nx-fig" id="fig-15-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Request</div><div class="arr">→</div><div class="node">Decision ✋</div><div class="arr">→</div><div class="node">Record</div><div class="arr">→</div><div class="node">Action</div><div class="arr">→</div><div class="node">Observation</div></div>
      <div class="flow"><div class="node">T1 allow</div><div class="node">T2 deny ⛔</div><div class="node">T3 action raises</div><div class="node untrusted">T4 bypass</div><div class="node">T5 stream validates</div></div>
    </div>
  </div>
  <figcaption><b>Figure 15.1 — Where each of the five tests attacks the enforcement path.</b> Top row: the evaluate–record–execute–observe sequence a governed invocation follows. Bottom row: the point each required test probes. Tests 1 to 3 walk the path from left to right; test 4 attacks the path's *existence* by going around it (dashed styling); test 5 attacks the output rather than the path. The teaching purpose is that these are five different attacks, not five degrees of the same one.</figcaption>
</figure>

## 15.3 Conformance suites

A unit test asks whether *this* implementation behaves correctly. A <span class="ix" data-ix="conformance suite">conformance suite</span> asks whether *any* implementation of a stated contract behaves correctly, and is written against the contract rather than against the code. The distinction matters in governed systems because the interesting components have multiple implementations: several framework adapters against one authorization interface; several evidence producers against one evidence schema; several enforcement points against one decision semantics.

Three properties separate the two. A conformance suite is written in the contract's vocabulary, so it runs against implementations its author never saw. It is *complete with respect to the claims* — every claim has at least one test that fails when the claim is violated. And it is versioned with the contract, so "conforms to version 1.2" has a definite meaning.

The Nornyx repository does not use the word "conformance" for its framework-adapter tests, and it is worth being careful here, because the same word is used in that repository for something else entirely: a static, declaration-level check that a contract's declared adapter blocks are safely configured, which produces a report proving that nothing was executed. That is a different artifact with a different purpose, and treating one as evidence about the other would be a category error. What plays the conformance role for the framework adapters is the pairing of the coverage inventory with a behavioral test suite: the inventory states the claims, and the tests establish them. An implementer of a new adapter for a third framework inherits the obligation directly — declare an inventory, then satisfy the five-test rule for every entry marked wrapped.

> **Design checkpoint.** If you maintain a governance interface with more than one implementation, ask: could a second team implement this interface from the specification alone, and could you tell — mechanically, without reading their code — whether they got it right? If not, you have a specification and a reference implementation, but no contract. The conformance suite is what makes the difference.

## 15.4 Failure injection

The five-test rule exercises the mechanism. <span class="ix" data-ix="failure injection">Failure injection</span> exercises what happens when the mechanism itself is broken, absent, or lying. It answers the sixth of the eight assurance questions from Chapter 3 — *what happens when the enforcing component fails?* — and it is the discipline most consistently missing from governance test suites, because it requires deliberately breaking the thing you are proud of.

Four injection classes cover most of the useful ground.

**Break the decision path.** Make the policy engine raise instead of returning a decision. The correct behavior is that the protected action does not run: the failure of an authorization component must never be interpreted as authorization. As implemented at the snapshot, the Nornyx adapter enforcement boundary gives this behavior structurally — an unexpected error from evaluation or from recording propagates before the action is reached — and the adapter test suite contains cases for both.

**Break the evidence path.** Make the recorder raise, or make it silently drop events. Two questions matter and they have different right answers depending on the deployment's tier: does the action still run, and does anyone find out? A system that continues executing governed actions after its recorder dies has quietly converted itself from a governed system into an ungoverned one with a reassuring history.

**Break the artifacts.** Corrupt a lock file, edit a generated artifact by hand, point the system at a policy bundle whose content hash does not match its declaration. Fail-closed behavior here has a visible cost: the pipeline stops. The Nornyx toolchain, as implemented at the snapshot, gives lock and parse failures a distinct exit code rather than folding them into ordinary policy failures, which lets a pipeline distinguish "the policy said no" from "I could not establish what the policy is." Those two states must never share a code path.

**Break time.** Supply a malformed or ambiguous evaluation timestamp. The tempting implementation falls back to the system clock; the fail-closed implementation refuses. The Nornyx command-line interface, at the same snapshot, takes the second option: a malformed or naive `--as-of` value produces `AS_OF_INVALID` and a nonzero exit rather than a silent substitution of the live clock. This matters more than it first appears, because approval expiry, delegation validity, and revocation effectiveness are all evaluated against that instant. A silent fallback to "now" turns an expired approval into a valid one at exactly the moment when someone was trying to reason about a specific past state.

> **Case study — Forge.** The team from the opening scenario rebuilds its suite around the five-test rule, and the results are uncomfortable in an instructive way. The merge surface has an allow test and — after they write it — a deny test. It has no failure test, so nothing prevented a state in which the pipeline recorded a successful merge for a merge that aborted. It has no bypass test, and writing one takes ten minutes and reveals that a maintainer with repository write access can push directly to the protected branch, so the claim's real scope is "merges performed through the governed lane," not "merges." Failure injection produces the sharpest finding: with the policy artifacts deliberately corrupted, the pipeline's merge lane fails — correctly — but a second workflow that publishes a release candidate does not consult the artifacts at all and keeps running. Forge's control description is revised in three places. None of the revisions changes any code; they change what the organization believes it has.

## 15.5 Property-style invariants for policy systems

Example-based tests establish that a system behaves correctly on the cases someone thought of. Policy systems have <span class="ix" data-ix="policy invariant">invariants</span> that are better stated as universals over inputs, in the style of property-based testing: assertions of the form "for all contracts and all requests, …". Two properties carry most of the weight, and both correspond to failure modes that example tests systematically miss.

**<span class="ix" data-ix="determinism!of policy decision">Determinism</span>.** For a fixed contract, a fixed request, and a fixed evaluation instant, the decision is identical — same effect, same code, same basis — on every evaluation, on every machine, in every process. This property is what makes a decision reviewable, reproducible in an incident reconstruction, and comparable across a policy change. It is easy to lose accidentally: a policy engine that reads the system clock, iterates an unordered set, or consults an environment variable has lost it without any test failing. Two design choices in the Nornyx toolchain, both as implemented at the snapshot, exist to preserve it. First, the authorization engine reads no wall-clock time at all: the evaluation instant is a mandatory field of the evaluation context, and all temporal semantics — expiry, validity windows, revocation effectiveness — are computed against that supplied value. Second, generated artifacts and locks are timestamp-free and canonically ordered, so identical resolution inputs produce byte-identical outputs, which is what allows a pipeline to detect drift by comparing hashes at all.

**<span class="ix" data-ix="monotonic composition">Monotonic composition</span>.** Adding a governance layer never widens authority. If composing a base profile with an additional module changes any decision, it changes it from allow to deny or from allow to approval-required, never in the other direction. This is the executable form of Chapter 8's silent-weakening problem: without the property, a lower-priority module that happens to be loaded later can quietly relax a control that a higher authority set, and no diff review will notice because the two artifacts individually look fine. In the Nornyx governance layer as implemented at the snapshot, composition merges by ordered union rather than by overwrite, a conflicting scalar field is a hard error rather than a last-writer-wins resolution, and the categories of actor that can never hold approval authority are unioned back into every composition regardless of what any pack declares. Those are three mechanisms serving one property.

Listing 15.2 sketches the two properties as tests. They are illustrative rather than drawn from the repository, but they are the shape the property should take in any policy system.

```python
# Illustrative — not drawn from the repository.

@given(contract=contracts(), request=requests(), instant=instants())
def test_decision_is_deterministic(contract, request, instant):
    a = evaluate(contract, request, at=instant)
    b = evaluate(contract, request, at=instant)
    assert (a.effect, a.code, a.basis) == (b.effect, b.code, b.basis)


@given(base=contracts(), overlay=modules(), request=requests(), instant=instants())
def test_composition_never_widens_authority(base, overlay, request, instant):
    before = evaluate(base, request, at=instant)
    after = evaluate(compose(base, overlay), request, at=instant)
    assert not (after.effect is ALLOW and before.effect is not ALLOW)
```

**Listing 15.2 — Two invariants stated as properties.** Illustrative — not drawn from the repository. The first property fails on any engine that consults ambient state; the second fails on any composition scheme where a later layer can overwrite an earlier restriction. Note that the second property is stated as an implication in one direction only: narrowing is permitted, widening is not. Getting that asymmetry right in the assertion is the whole exercise.

A third property is worth stating even though it is harder to generate inputs for: *decisions must not depend on request-supplied data that the policy did not declare*. An engine that authorizes based on fields the caller controls, rather than on declared concepts resolved from the contract, has an injection surface. The Nornyx authorization engine, as implemented at the snapshot, constrains this by construction — its own documentation notes that it authorizes declared concepts only and never parses raw shell commands, file paths, uniform resource locators, or tool arguments — and the adapters mirror it by building request bindings from static adapter configuration rather than from framework call arguments. Chapter 22 develops the adapter side of that discipline.

## 15.6 Silent skips are a governance failure

Return to the opening scenario's single letter `s`. In ordinary software engineering a skipped test is a minor hygiene issue, and every large suite has some. In a governance suite it is something else, and the difference is worth stating precisely rather than as an exhortation.

A governance test suite is not primarily a defect-detection instrument. It is the *evidence* that a claim holds — the thing you hand an auditor, cite in a control description, and rely on when deciding a deployment's assurance tier. Under that reading, a skipped test does not merely fail to detect a defect. It converts a supported claim into an unsupported one within the <span class="ix" data-ix="assurance pipeline">assurance pipeline</span> *while leaving every downstream artifact unchanged*. The dashboard is green, the control description still says what it said, the tier assignment still stands, and the only trace of the change is one character in a log nobody reads. This is the exact structure of a silent weakening, transplanted from policy composition into the assurance pipeline.

The failure is especially likely in agent-framework testing, because the frameworks are heavy optional dependencies. The idiomatic pattern — import the framework or skip the module — is the right default for a matrix that must also run without extras. Unmodified, it is also a mechanism for producing a green pipeline that tests none of the integration.

The repository's answer is to keep the idiom and add a <span class="ix" data-ix="zero-skip gate">zero-skip gate</span>. The framework-specific test modules do use the skip-if-absent idiom, so they are skipped in the extras-free build matrix. But the dedicated framework jobs then forbid skips mechanically. Listing 15.3 shows the gate.

```yaml
- name: Record the CrewAI version and forbid silent skips
  run: python -c "import crewai; print('crewai', crewai.__version__); assert crewai.__version__ == '1.15.4', crewai.__version__"
- name: Native CrewAI adapter tests (no skips permitted)
  run: |
    python -m pytest tests/test_crewai_adapter.py tests/test_crewai_adapter_missing_dependency.py \
      -v -rs --junitxml=crewai-native-results.xml
    # Fail closed if ANY focused CrewAI test skipped (e.g. crewai silently
    # absent): deterministic skip check, not a printed version string.
    python -c "import xml.etree.ElementTree as ET, sys; suites = ET.parse('crewai-native-results.xml').getroot().findall('.//testsuite'); skipped = sum(int(s.get('skipped', 0)) for s in suites); tests = sum(int(s.get('tests', 0)) for s in suites); print('crewai-native tests', tests, 'skipped', skipped); sys.exit(1 if (skipped or not tests) else 0)"
```

**Listing 15.3 — A machine-checked zero-skip gate.** From `.github/workflows/ci.yml`, the `adapter-crewai-native` job. Three details are load-bearing and each corresponds to a way the naive version fails. The framework version is asserted rather than printed, because a printed version string is only a control if a human reads it. The verdict is parsed from the run's own JUnit-format Extensible Markup Language (XML) report rather than from console output, because console text is not a machine-checkable artifact. And the gate fails when the test count is *zero* as well as when the skip count is nonzero, which catches the more embarrassing failure of a collection pattern that silently matches nothing. The companion LangGraph job applies the same discipline to that framework's pinned version.

Two properties of the surrounding pipeline matter as much as the gate. The framework jobs install the *real* pinned frameworks rather than stubs, so the tests exercise the dispatch machinery the adapter claims to intercept; the only deterministic substitute is the language model, replaced by a scripted offline implementation. And several jobs build the candidate package from the same commit, install it as a wheel into a fresh environment, and run the smoke tests from outside every source directory, so a passing result cannot depend on an importable working tree. Both answer one question: is the thing under test the thing that ships?

<figure class="nx-fig" id="fig-15-2">
  <div class="fig-body">
    <div class="layers">
      <div class="layer authority" data-note="fails the build on any drift">Artifact integrity — regenerate, compare every generated file by hash, verify the lock</div>
      <div class="layer" data-note="closed schemas, references, structural checks">Contract validation — check the contract at a pinned evaluation instant</div>
      <div class="layer" data-note="allow · deny · failure · bypass · evidence">Claim tests — the five-test rule per wrapped surface</div>
      <div class="layer" data-note="real pinned frameworks, zero-skip gate, fresh-env wheel smoke">Integration reality — is the thing under test the thing that ships?</div>
      <div class="layer" data-note="validate the produced stream, strict mode">Evidence validation — the run's own records must validate</div>
      <div class="layer" data-note="lock, artifacts, reports, manifest">Audit package — assemble what a reviewer will read</div>
    </div>
  </div>
  <figcaption><b>Figure 15.2 — A governance continuous-integration pipeline as six layers of obligation.</b> Each band answers a different assurance question, and a pipeline missing a band is not a faster pipeline but a weaker claim. The ordering is deliberate: artifact integrity comes first because every later result is a statement about a specific artifact set, and evidence validation comes near the end because it consumes the records that the claim tests produce. The repository's reference workflow instantiates every band, including a regenerate-and-byte-compare drift gate and an assembled audit package. Chapter 29 turns this figure into a concrete pipeline design.</figcaption>
</figure>

## 15.7 The governance benchmark as claim-testing methodology

The repository contains an A/B <span class="ix" data-ix="governance benchmark">governance benchmark</span> that is worth studying less for its results than for its method. One customer-support and financial-remediation workflow is run twice: once as an ordinary agent application, and once with the same agents, tasks, model, inputs, business rules, and business callables, differing only in that each tool is constructed through the supported adapter. Nineteen scenarios run across both arms. The whole thing runs offline and exits nonzero unless every clause of its own contract holds and the complete evidence stream validates.

Four methodological choices in that design are transferable to any governance claim-testing effort.

**Prevention is proved by side effects, not by exceptions.** The benchmark's central instrument is a <span class="ix" data-ix="side-effect ledger">side-effect ledger</span>: every business tool writes to it, and every governance decision is stamped on the same monotonic clock. That single design decision makes three things checkable rather than asserted. First, a denied scenario must hold attempts and completions at exactly zero and an allowed scenario at exactly one. Second — and this is the clever part — the k-th entry into a business callable must be preceded by the k-th recorded decision, which defeats <span class="ix" data-ix="decision reuse">decision reuse</span>: a system that authorizes once and then executes three times passes a naive "decision before first execution" check and fails this one. Third, an authorized action that then fails must produce zero completions and no success observation, which is the failure test of Section 15.2 applied at whole-system scale. Figure 15.3 works one interleaving through the ledger's rules.

<figure class="nx-fig" id="fig-15-3">
  <div class="fig-body">
    <table class="fig-table">
      <tr><th>Tick</th><th>Ledger entry</th><th>Verdict rule</th></tr>
      <tr><td>1</td><td>decision #1 recorded (allow)</td><td>—</td></tr>
      <tr><td>2</td><td>business callable attempt #1</td><td>attempt k must follow decision k ✓</td></tr>
      <tr><td>3</td><td>completion #1</td><td>allowed ⇒ exactly one completion ✓</td></tr>
      <tr><td>4</td><td>decision #2 recorded (deny)</td><td>—</td></tr>
      <tr><td>5</td><td><i>no attempt, no completion</i></td><td>denied ⇒ attempts and completions = 0 ✓</td></tr>
      <tr><td>6</td><td>business callable attempt #2</td><td>attempt 2 has no decision 2 available ✗ — decision reuse</td></tr>
    </table>
  </div>
  <figcaption><b>Figure 15.3 — One monotonic ledger makes prevention checkable.</b> Decisions and effects are stamped on the same clock, so a claim about prevention becomes an arithmetic property of an interleaving rather than an inference from a caught exception. Row 6 shows the defect that a naive ordering check misses: the reuse of an earlier authorization for a later effect. The teaching purpose is that the instrument, not the assertion, is what makes the claim strong.</figcaption>
</figure>

**Scenarios are reported separately and never summed.** The nineteen scenarios span five stages — load, binding, runtime, bypass, and application — and the benchmark refuses to aggregate them into a single score. This is not modesty. A summary number across heterogeneous scenarios invites exactly the tier inflation Chapter 14 warned about, because it lets a strong result in one stage compensate for an absent control in another.

**Non-wins are declared.** Two scenarios are explicitly excluded from every prevention metric. Scenario S15 is a deliberate unwrapped-tool bypass that "runs in both variants," on the stated grounds that enforcement is cooperative and a tool that never enters the adapter is never evaluated. Scenario S18 is a request refused by the application's own business rule in both arms, so crediting the governance layer for it would be crediting a control the baseline already had. The benchmark's own words are the right standard: these "are controls, not wins." Any comparison of a governed and an ungoverned system needs both kinds of declared non-win — one for what governance cannot reach, one for what the baseline already handled — or its numbers are measuring the experimental setup rather than the system.

**Defects found are reported with their consequence scoped.** Building the benchmark surfaced three real defects in the audited packages, all since fixed with regression tests: a correctly refused non-human approval emitted an event that the evidence validator rejected, so exercising a headline guarantee made the stream unvalidatable; a delegated capability's success observation omitted the authorizing delegation, so delegation and validatable evidence were mutually exclusive on that path; and a legacy directory claimed the supported package's import name, so the two could not coexist in one process. The finding that matters for this chapter is the scoping sentence attached to them: none of the three ever changed an enforcement result — every decision in every run was correct and every prevented callable stayed at zero side effects — but each one blocked a clean *evidence* claim.

That distinction is the sharpest available illustration of Chapter 3's assertion layers. Enforcement and evidence are separate layers with separate failure modes, and a system can be entirely correct in the first while being unable to demonstrate anything in the second. An organization that tests only enforcement will never find these defects, and will discover them at the worst possible moment: when an auditor asks for the stream.

> **Assurance boundary.** A benchmark of this shape supports claims of the form "in these nineteen scenarios, on this pinned toolchain, the governed arm prevented the effect and the ungoverned arm did not." It does not support "the governed system prevents this class of action," because the scenario set is finite and chosen by the people who built the system. Its committed results directory is described as a snapshot of one run, not a continuously verified claim. Treat a benchmark as a worked method, and re-run it in your own environment before citing its numbers as evidence about yours.

## Summary

Testing governance begins before any test is written, by rewriting control descriptions as propositions that bind a surface, a mechanism, and a condition. Each claimed surface then owes five tests — allow, deny, failure, bypass, evidence — and the two that are almost always missing, failure and bypass, are the two that keep a claim's scope honest. Conformance suites generalize this obligation across implementations of one contract. Failure injection extends it to the mechanism itself, asking what the system does when its decision path, evidence path, artifacts, or notion of time is broken; fail-closed is a design commitment with a visible cost, and the cost is the point. Some invariants are better stated as properties than examples, especially decision determinism and the rule that composing a layer never widens authority. A silently skipped test is not a hygiene problem but a silent weakening of the assurance pipeline, which is why zero-skip gates deserve to be machine-checked rather than eyeballed. And a well-built benchmark shows what a rigorous claim test looks like at system scale: prevention proved by a monotonic side-effect ledger rather than by caught exceptions, scenarios reported separately, non-wins declared, and defects reported with their consequence honestly scoped.

- A claim without a surface, a mechanism, and a condition is not yet testable; making it testable is most of the work.
- The five-test rule per surface names five distinct falsifiers, not five degrees of thoroughness.
- Failure injection answers "what happens when the enforcing component fails?" — the assurance question suites most often skip.
- Determinism and monotonic composition are universals over inputs and should be tested as properties.
- A skipped governance test leaves the claim, the control description, and the tier assignment unchanged while removing their support.
- Declared non-wins and honestly scoped defect findings are what distinguish a benchmark from a demonstration.

## Review questions

1. Take the sentence "sensitive customer data is never sent to external model providers" and rewrite it as a governance claim binding a surface, a mechanism, and a condition. Then list the five tests it obliges, saying for each what specific observation would falsify the claim.
2. Explain why the allow test must assert that the decision was recorded *before* the action ran. What defect passes an allow test that omits the ordering assertion?
3. Distinguish a conformance suite from a unit-test suite along the three properties given in Section 15.3. Why does the distinction matter more for a governance interface than for, say, a data-parsing library?
4. A team's evaluation timestamp handling falls back to the system clock when the supplied value is malformed. Construct a concrete scenario in which this fallback turns a correct denial into an incorrect allow, and identify which artifact the resulting evidence would misrepresent.
5. State the monotonic-composition property precisely, including its asymmetry. Give an example of a composition scheme that violates it while looking correct in a code review of either layer alone.
6. The benchmark's three findings "never affected an enforcement result" but blocked a clean evidence claim. Using Chapter 3's assertion layers, explain why an organization can be simultaneously well protected and unable to demonstrate it — and say which stakeholder is harmed by that state.

## Exercises

1. **Sort the suite.** Take an existing test suite for a system with any authorization boundary and sort every test into the five rows of Table 15.1. Report the counts. For each empty or nearly empty row, write one test that fills it, and record whether writing that test revealed a defect, a missing claim, or neither. The exercise is finished when you can state, for each claimed surface, which row is weakest and why.
2. **Inject four failures.** For one governed operation, run the four injection classes of Section 15.4: break the decision path, break the evidence path, corrupt an artifact, and supply a malformed evaluation instant. Record for each: did the protected action still run, was anything recorded, did any pipeline stage fail, and would an operator have noticed within an hour? Write the results as a short table and mark the rows where the observed behavior differs from the behavior your control description implies.
3. **Design a declared non-win.** Design a two-arm comparison for a control you actually operate — governed arm and ungoverned arm, same workload. Before running anything, write down two scenarios you will declare as non-wins: one the governance layer cannot reach, and one the baseline already handles. Then state, in one sentence each, what a reader may and may not conclude from the comparison's headline numbers.

## Further reading

- [@swebok-testing] — placing conformance testing, negative testing, and fault injection in a standard taxonomy; useful for arguing this chapter's obligations to a test-engineering audience in their own vocabulary.
- [@schneider-enforceable] — the formal boundary between policies a monitor can enforce and policies it cannot; read it to see which of your claims are testable in principle before worrying about test design.
- [@clark-wilson] — separation of duties and well-formed transactions as integrity controls; the intellectual ancestor of the maker–checker claims a governance suite must test.
- [@reproducible-builds] — determinism as an engineering practice rather than an aspiration; the byte-identical-output discipline underlying the drift gates in Figure 15.2.
- [@sre-book] — production discipline around failure injection and the operational cost of fail-closed design; a useful counterweight to purely security-driven arguments for stopping the pipeline.
