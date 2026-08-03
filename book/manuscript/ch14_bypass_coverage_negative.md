---
chapter: 14
part: III
title: "Bypass, Coverage, and Negative Controls"
---

# Bypass, Coverage, and Negative Controls

> **Opening scenario.** Northstar Services' Engineering Platform group has spent two months building a governed path for a single, deliberately boring operation: a support agent issuing a customer refund. The wrapped path works. A tool call arrives, a decision is evaluated, an allow or a deny is recorded, and the refund either happens or does not. The team writes a one-page summary for the Risk & Audit chief that begins, "All refund actions are governed." A reviewer from the security team reads it, opens the agent's source, and finds four lines that call the refund function directly from a retry handler, without going through the wrapper at all. Nobody wrote those four lines maliciously; they were added during a debugging session and never removed. The reviewer's question is not "why did you write this?" but something more uncomfortable: *"Your document says all refund actions are governed. What in your system would have told you that sentence was false?"* Nothing would have. The wrapped path was tested exhaustively. The unwrapped path was not tested at all, because it was not known to exist, because nothing in the design obliged anyone to write it down.

> **Learning objectives.**
> - Explain why a coverage inventory is part of a governance component's public interface rather than internal documentation.
> - Distinguish three coverage states — wrapped, unsupported, and unwrapped — and justify why a two-state model is inadequate.
> - Argue why publishing a list of surfaces a control does *not* cover increases rather than decreases the security of a deployment.
> - Identify the three structural sources of wrapper bypass: direct invocation beneath the wrapper, uncovered asynchronous paths, and surfaces introduced by framework upgrades.
> - Design negative controls: tests that prove a denial happened and that prove a bypass is either detected or explicitly declared ungoverned.
> - Rewrite an overclaimed governance statement into a precise, qualified claim, and say exactly which words carry the qualification.

> **Prerequisites.** Chapter 1 (the reachable set versus the authorized set), Chapter 3 (assertion layers and the eight assurance questions), Chapter 10 (policy decision point and policy enforcement point separation, cooperative versus independent enforcement), Chapter 11 (evidence and its producers), and Chapter 13 (the assurance tier model). This chapter uses all of those terms without re-teaching them.

## 14.1 Coverage is an interface, not a footnote

Every enforcement mechanism has a boundary, and every boundary has an inside and an outside. A network firewall covers the traffic that traverses it and nothing else. A database trigger covers the statements that reach the database and not the ones that reach a replica. A code-level policy check covers the call sites that invoke it. This is unremarkable. What *is* remarkable is how rarely the outside of the boundary is written down.

The habit is easy to explain. Engineers document what a component does, because that is what callers need. The set of things a component does not do is infinite, and enumerating an infinite set is not useful documentation. So the outside of the boundary goes unwritten, and its absence is read — by users, by reviewers, by auditors, and eventually by the engineers themselves — as absence of gaps.

For governance components this habit is not merely untidy; it is a defect, because the *purpose* of a governance component is to support a claim, and a claim has a scope. "This agent cannot issue refunds above €500 without approval" is a proposition about a system, not about a function. Whether it is true depends entirely on whether every path that reaches the refund operation passes through the component that evaluates it. A component that covers three of four paths is not seventy-five percent correct; it makes the sentence false while appearing to make it true. The scope of the claim, in other words, is not a property the component's author can leave to the reader's imagination. It has to ship with the component.

We therefore introduce a <span class="ix" data-ix="coverage inventory">coverage inventory</span>: a declared, machine-readable enumeration of the surfaces a governance component intercepts, together with the surfaces it does not intercept and the reason for each. A <span class="ix" data-ix="surface">surface</span>, in this vocabulary, is a named point of interception in a host framework — a method that gets overridden, a callable that gets wrapped — not a business operation. The inventory is not release-note prose. It is a data structure with the same status as a function signature: versioned with the component, testable, and part of what a caller is entitled to rely on.

> **Key idea.** A governance component's public interface has two halves. The first half says what it enforces. The second half says where it is not in the path. A component that ships only the first half has shipped a claim whose scope is unspecified, and an unspecified scope is, in practice, read as universal.

## 14.2 Three states, not two

The obvious model of coverage has two states: covered and not covered. It is inadequate, and the inadequacy is instructive.

Consider three genuinely different situations in the same integration. First, a synchronous tool-invocation path that the adapter wraps and enforces. Second, an asynchronous variant of that same path that the adapter's authors deliberately did not implement, and which therefore must never be used in a governed deployment. Third, the construction of the workflow graph itself: a surface that no adapter could meaningfully intercept, because it is the integrator who decides which nodes exist and which of them get wrapped. All three are "not the same as fully enforced," but the operational obligation each places on the deployer is different. The first requires nothing. The second requires that the deployment avoid the path or accept that actions on it are ungoverned. The third requires that the deployer *do work* — wrap each node — and be audited on whether they did.

A three-state taxonomy captures the distinction:

- <span class="ix" data-ix="wrapped surface">**Wrapped**</span> — the component is in the path; every invocation of this surface is evaluated and recorded before the underlying action runs.
- <span class="ix" data-ix="unsupported surface">**Unsupported**</span> — the component is deliberately not in the path, by decision of its authors. Using this surface produces ungoverned action, or fails, but never governed action.
- <span class="ix" data-ix="unwrapped surface">**Unwrapped**</span> — the surface is owned by the caller. The component cannot intercept it; whether governance applies depends on integration work the deployer performs, and the deployer carries the obligation.

The Nornyx framework adapters implement exactly this taxonomy as implemented at the snapshot. Listing 14.1 shows the data structure. Note what the type system enforces: a surface's status is drawn from a closed enumeration, so there is no way to express "partly covered"; the reason field is a string that the component's authors must actually fill in; and `as_dict` sorts its output, so two inventories with the same content serialize to the same bytes, which is what makes the inventory diffable in a pipeline.

```python
class SurfaceStatus(Enum):
    WRAPPED = "wrapped"
    UNSUPPORTED = "unsupported"
    UNWRAPPED = "unwrapped"


@dataclass(frozen=True)
class SurfaceCoverage:
    surface: str
    framework: str
    status: SurfaceStatus
    reason: str = ""


@dataclass(frozen=True)
class CoverageInventory:
    """A closed set of declared surfaces and their wrap status.

    Never implies whole-application coverage (ADR-0040): it names exactly the
    surfaces an adapter declares, for the stated framework only.
    """

    entries: tuple[SurfaceCoverage, ...]

    def wrapped(self) -> tuple[SurfaceCoverage, ...]: ...

    def as_dict(self) -> dict:
        """Deterministic, JSON-serializable representation (sorted for reproducibility)."""
```

**Listing 14.1 — The coverage inventory as a typed, closed structure.** Excerpted from `adapters/nornyx-agentic-adapters/src/nornyx_agentic_adapters/coverage.py`. The module's own docstring states the design intent plainly: "unsupported and unwrapped surfaces are named, not hidden, and the inventory never implies whole-application coverage." The `entries` field is canonicalized to a fresh tuple at construction, so a caller who builds the inventory from a list and later mutates that list cannot alter what the component declares.

Table 14.1 shows the inventory that ships with the CrewAI adapter as implemented at the snapshot. Six surfaces are declared; exactly one is wrapped.

| Surface | Status | Declared reason (abridged) |
|---|---|---|
| `tool_invocation` | wrapped | Synchronous tool execution wrapped via a `crewai.tools.BaseTool._run` override, reached through `Crew.kickoff()`'s native executor. Covers the sync `_run` path only. |
| `async_tool_invocation` | unsupported | The adapter overrides only the synchronous `_run` and does NOT override `_arun`; the inherited method raises, so the wrapped action never executes and no `tool_invoked` observation is recorded. |
| `agent_invocation` | unsupported | No public, stable hook fires on agent invocation distinct from tool-level interception. |
| `task_invocation` | unsupported | Same rationale as agent invocation. |
| `delegation` | unsupported | The framework's coworker delegation is implemented via its own internally generated tools; wrapping it would depend on undocumented internals. |
| `handoff` | unsupported | The framework has no distinct handoff concept or public hook separate from delegation. |

**Table 14.1 — One wrapped surface out of six.** The declared coverage inventory of the CrewAI adapter (`crewai_adapter.py`, `COVERAGE_INVENTORY`). The teaching point is the ratio. A reader who assumed that "the CrewAI adapter governs CrewAI" would be wrong in five of six respects, and the inventory is the only artifact in the system that says so.

The companion LangGraph adapter declares five surfaces: synchronous node invocation is wrapped; asynchronous nodes, remote or distributed execution, and subgraph or prebuilt tool-node internals are unsupported; and graph topology is *unwrapped*, with the declared reason that the caller owns graph construction and must wrap each governed node explicitly. That single `unwrapped` entry is the whole justification for a three-state model. It is not a gap the adapter's authors could close; it is an obligation transferred to the integrator, and naming it transfers the obligation visibly.

## 14.3 Why publishing your gaps is security information

The instinct to suppress an unsupported-surface list is strong, and it is worth taking seriously rather than dismissing. The argument for suppression goes: an attacker who reads "asynchronous invocation is not intercepted" has been handed a bypass. Why write the attacker's reconnaissance report for them?

The argument fails on three counts.

First, the asymmetry is backwards. An attacker who has code execution near the agent, or who can influence which code path the agent takes, discovers uncovered paths by trying them; this costs minutes. A *defender* who wants to know which paths are uncovered must read the source of a governance component they did not write, understand a framework's dispatch internals, and reason about which of several entry points the component intercepts. Withholding the inventory imposes hours of work on the defender to save the attacker minutes. That trade is never favorable.

Second, the audience that matters most is neither attacker nor defender but the deployer making a decision. The person choosing whether to route a €50,000 payment adjustment through a cooperative in-process control needs to know the shape of the control's boundary in order to decide whether that tier of assurance is adequate for that consequence (Chapter 13). Denying them the inventory does not make the boundary smaller; it makes the decision uninformed.

Third — and this is the deepest reason — the inventory is what makes the positive claim *meaningful*. "Tool invocations are governed" is an unfalsifiable sentence if nobody says which invocations count as tool invocations. "The synchronous `_run` path is wrapped; the asynchronous `_arun` path is not, and raises rather than executing" is falsifiable, and can therefore be tested, reviewed, and relied upon. Precision about the boundary is not a concession extracted from a governance vendor. It is the thing that converts marketing into engineering.

> **Misconception.** *"An unsupported-surface list is an admission of incompleteness that a competitor without such a list does not have to make."* The competitor has exactly the same gaps and has merely not enumerated them. The comparison a buyer should make is not "declared gaps versus no declared gaps" but "boundary knowable versus boundary reverse-engineered." A governance component that cannot state its own scope has not solved the scope problem; it has moved it to its users, who are worse placed to solve it.

## 14.4 Bypass is an architectural fact

<span class="ix" data-ix="bypass">Bypass</span> is the execution of a governed operation along a path that does not traverse the enforcement point. It is not, in the general case, an attack. It is the default behavior of any system in which the enforcement point is a wrapper rather than a chokepoint, and it arises through three distinct structural mechanisms.

**Direct invocation beneath the wrapper.** A cooperative enforcement point wraps a callable. The callable still exists. Any code in the same process that holds a reference to it can call it, and nothing in the language, the runtime, or the framework prevents that. The wrapper is a convention about how the callable *should* be reached, enforced by nothing except the discipline of the integrating code. The opening scenario is precisely this: a retry handler that called the refund function directly. In Chapter 10's vocabulary, the policy enforcement point was not on the path; it was merely one of several paths.

**Uncovered asynchronous paths.** Modern agent frameworks expose synchronous and asynchronous variants of the same logical operation. An adapter that wraps one and not the other creates a bypass that is invisible in code review, because the two call sites look almost identical. Whether this bypass is dangerous depends on what the uncovered variant does when reached. The safest design makes the uncovered variant *fail* rather than silently succeed: in the CrewAI adapter as implemented at the snapshot, the governed tool does not override the asynchronous method, and the framework's inherited implementation raises, so the wrapped action never executes and no observation is recorded. The path is uncovered, but it is uncovered loudly. A test named `test_async_arun_fails_closed_and_records_nothing` runs against the real pinned framework and asserts exactly that.

**New surfaces after a framework upgrade.** This is the mechanism that produces bypass in systems that were fully covered yesterday. A framework minor release adds a new execution entry point, a new node type, a new tool-dispatch mechanism. The adapter does not wrap it, because it did not exist when the adapter was written. Coverage silently drops without any change to the governed system's own code. This is <span class="ix" data-ix="drift!framework-adapter">framework-adapter drift</span>, one of the drift categories introduced in Chapter 2, and it is the reason a governance integration cannot honestly claim coverage against a version range it has not tested. The Nornyx adapter package addresses this by pinning frameworks exactly rather than permissively — CrewAI at `==1.15.4` and LangGraph at `==1.2.2` — and by enforcing those pins at *import time*, not merely declaring them in package metadata: importing the adapter module against an unexpected framework version raises a configuration error rather than proceeding with unknown coverage. The package's own documentation gives the rationale directly: the pins "name the only version of each framework this package has been tested against. A wider range is not claimed until new test evidence supports it."

Figure 14.1 puts the four paths of the Gateway comparison side by side. The dashed arrows are the ungoverned ones.

<figure class="nx-fig" id="fig-14-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Planner</div><div class="arr dashed">⇢</div><div class="node">Native tool call</div><div class="arr dashed">⇢</div><div class="node untrusted">Refund API</div></div>
      <div class="flow"><div class="node">Planner</div><div class="arr">→</div><div class="node">Governed wrapper ✋</div><div class="arr">→</div><div class="node">Decision + record</div><div class="arr">→</div><div class="node">Refund API</div></div>
      <div class="flow"><div class="node">Retry handler</div><div class="arr dashed">⇢</div><div class="node untrusted">Underlying callable</div><div class="arr dashed">⇢</div><div class="node untrusted">Refund API</div></div>
      <div class="flow"><div class="node">Planner</div><div class="arr">→</div><div class="node authority">External gateway ⛔</div><div class="arr">→</div><div class="node">Refund API</div></div>
    </div>
  </div>
  <figcaption><b>Figure 14.1 — Four paths to the same operation.</b> Row 1: the ungoverned baseline. Row 2: the cooperative wrapped path, where the enforcement point sits between planner and effect. Row 3: the bypass path — the same underlying callable reached directly, with the wrapper still installed and still irrelevant. Row 4: an independent enforcement point placed where the operation must traverse it, an architectural extension beyond the current repository. The teaching purpose is to show that rows 2 and 3 coexist in one deployment: installing row 2 does not remove row 3.</figcaption>
</figure>

> **Case study — Gateway.** Engineering Platform's comparison now has its third path. Rows 1 and 2 of Figure 14.1 were built in the previous phase: the framework-native ungoverned call, and the same workflow with each tool constructed through the supported adapter. The team now adds row 3 deliberately — a code path that reaches the refund callable without constructing a governed tool at all — and writes it into the comparison as a *control*, not a defect to be fixed. The decision table gains a row whose "coverage" cell reads *none*, whose "evidence" cell reads *none*, and whose "assurance tier" cell reads *not applicable: no governed decision occurred*. The reviewer's question from the opening scenario now has an answer: the system tells you the sentence "all refund actions are governed" is false, because the comparison contains a path where it is false and the team put it there on purpose. Row 4, the mandatory gateway, remains a design on paper; it is what the team will need if the residual risk of row 3 turns out to be unacceptable for high-value refunds. Chapter 26 takes up what that path would require.

## 14.5 Negative controls as first-class tests

The bypass path in Figure 14.1 is not something you discover by testing that the system works. It is something you discover by testing that the system's *limits* are where you say they are. This calls for a category of test that most engineering cultures underweight.

A <span class="ix" data-ix="negative control">negative control</span> is a test whose passing condition is that something did *not* happen, or that something failed in a specified way. The name is borrowed from experimental science, where a negative control is the sample that must show no effect; if it shows an effect, the instrument is measuring something other than what the experimenter thinks. The analogy holds precisely. A governance test suite full of positive tests measures whether the happy path works. Only negative controls measure whether the enforcement is doing anything at all.

Three kinds of negative control matter for governed agentic systems, and they are not interchangeable.

**Proving a denial happened.** The naive <span class="ix" data-ix="denial test">denial test</span> asserts that a call raised an exception. This is weak evidence, because an exception can be raised by an argument-validation error, a missing dependency, a network timeout, or an assertion in code unrelated to policy. A denial test must assert the mechanism, not the symptom: that a decision was evaluated, that its effect was deny with a specific decision code, that the decision was recorded, and — the load-bearing assertion — that the protected action produced *zero side effects*. In the Nornyx adapter suite the enforcement boundary evaluates, records the decision, and only then executes the action, so a denial test can assert both the recorded decision and the untouched effect. A test that checks only "an exception was raised" would pass on a system whose policy engine had been replaced by `raise RuntimeError`.

**Proving a bypass is detected.** Where the architecture allows the enforcement point to observe that something reached the protected resource without a decision, a negative control asserts that detection. Independent enforcement points can do this; cooperative in-process wrappers generally cannot, because the wrapper only runs when it is called.

**Proving a bypass is declared.** Where detection is impossible, the honest negative control is different in kind: it asserts that the bypass exists, behaves as documented, and is named in the coverage inventory. This sounds paradoxical — a test that asserts the system can be bypassed — and it is the most valuable test in the suite, for reasons the next section develops.

Figure 14.2 arranges the categories against what each one rules out.

<figure class="nx-fig" id="fig-14-2">
  <div class="fig-body">
    <table class="fig-table">
      <tr><th>Test category</th><th>Passing condition</th><th>Failure it rules out</th></tr>
      <tr><td>Positive (allow)</td><td>Action runs exactly once; allow decision recorded first</td><td>Enforcement blocks legitimate work; decision recorded after the effect</td></tr>
      <tr><td>Negative (deny)</td><td>Deny decision with a named code; zero side effects</td><td>Policy evaluated but not enforced; enforcement without a decision</td></tr>
      <tr><td>Negative (failure)</td><td>Action raises; no success observation recorded</td><td>Evidence claims completion of work that did not complete</td></tr>
      <tr><td>Negative (bypass, detected)</td><td>Ungoverned access produces a detection record</td><td>Silent circumvention of a mandatory enforcement point</td></tr>
      <tr><td>Negative (bypass, declared)</td><td>Ungoverned path runs ungoverned, exactly as the inventory says</td><td>A cooperative boundary silently becoming an assumed mandatory one</td></tr>
    </table>
  </div>
  <figcaption><b>Figure 14.2 — Five test categories and what each rules out.</b> The teaching purpose is that these are not degrees of thoroughness but distinct falsifiers: a suite can be exhaustive in one row and empty in another, and the empty row is where the false claim lives. Chapter 15 turns this table into an obligation per claimed surface.</figcaption>
</figure>

## 14.6 A worked study: the test that proves the boundary

The Nornyx adapter package contains a test that is unusual enough to be worth reading in full. It asserts that the package can be bypassed.

```python
def test_bypass_calling_the_raw_action_directly_skips_enforcement_entirely(
    authorizer: Authorizer,
) -> None:
    """ADR-0040 cooperative Tier 2: bypassing the adapter bypasses enforcement.

    Nothing in this package prevents an integrator from invoking the
    underlying work callable directly, without ever constructing a governed
    tool or evaluating a Decision. This test makes that boundary explicit
    rather than implicit.
    """
    calls: list[Any] = []

    def action() -> str:
        calls.append(1)
        return "ran with no authorization check whatsoever"

    # The reviewer identity does not hold this capability — if this ran
    # through make_governed_tool it would be denied. Called directly, it just
    # runs, because nothing enforces anything outside the governed wrapper.
    result = action()
    assert result == "ran with no authorization check whatsoever"
    assert calls == [1]
```

**Listing 14.2 — A test that asserts its own component can be bypassed.** From `adapters/nornyx-agentic-adapters/tests/test_crewai_adapter.py`. The test constructs an identity that does *not* hold the relevant capability, so the same action routed through the governed tool would be denied; it then calls the action directly and asserts that it runs.

Read as a piece of test engineering, this file is strange. It exercises no product code. Its assertions cannot fail as long as Python calls functions. A coverage tool would report it as contributing nothing, and under most review conventions it would be deleted.

Read as a piece of *claim* engineering, it does something no other test in the suite does. Consider what changes if it is removed. The suite still proves that governed tools evaluate, record, and enforce, and that denials produce no side effects. What it no longer contains is any executable statement of the boundary's shape — and boundaries that exist only in prose migrate. A future maintainer reads "the adapter governs tool invocation," reasonably concludes that the adapter is a mandatory interception layer, and designs a deployment on that assumption. Nothing in the repository contradicts them. With the test present, the contradiction is a file that runs on every pull request and must be discussed if anyone proposes changing it.

There is a second, subtler function. The test defines what would count as a *change* to the boundary. Suppose a future version added an import hook that intercepted direct calls; that version would break this test. Breaking it would be correct, because the boundary moved — but it would force an explicit decision, a changelog entry, and a revised claim, rather than an unannounced widening of what the component appears to promise. The test is a pinned assertion about the assurance tier the component supports, expressed in the only language a continuous-integration system understands.

The same discipline appears at the level of the whole system in the repository's A/B governance benchmark, which runs one workflow twice — once as an ordinary agent application, once with every tool constructed by the supported adapter — across nineteen scenarios. Scenario S15 is a deliberate unwrapped-tool bypass, and the benchmark documentation states its status without hedging: "S15 executes under governance on purpose — enforcement is cooperative, and a tool that never enters the adapter is never evaluated." The benchmark's rule is that S15 and one other scenario "are controls, not wins" and count toward no prevention metric. Such a <span class="ix" data-ix="declared non-win">declared non-win</span> is the benchmark equivalent of Listing 14.2: scoring it would measure the wrong thing, and omitting it would hide it. Chapter 15 treats the benchmark's method in detail.

> **Assurance boundary.** What is guaranteed by the adapter package as implemented at the snapshot: for the declared wrapped surfaces, a decision is evaluated and recorded before the protected action runs, and on any non-allow decision the action does not run. What is not guaranteed: that the wrapped surface is the only way to reach the action, that all framework paths are covered, that the caller's identity was authenticated, or that a recorded event corresponds to something that actually happened in the world. The boundary is cooperative by construction, and the coverage inventory plus the bypass test are the artifacts that say so in a form a machine can check.

## 14.7 Qualifying a claim precisely

Everything above converges on a writing problem. Governance claims are consumed as sentences — in architecture documents, security questionnaires, control descriptions, and audit responses — and the difference between a defensible sentence and an indefensible one is usually five or six words.

The mechanics of <span class="ix" data-ix="claim qualification">claim qualification</span> are not stylistic. A precise claim names four things: the *surface* on which it holds, the *mechanism* that makes it hold, the *conditions* under which the mechanism is in the path, and the *assurance tier* the resulting claim supports. Any claim missing one of the four is either doing less work than it appears to or is false. Table 14.2 works through four common <span class="ix" data-ix="overclaim">overclaims</span> from real governance documents, reduced to their essential form.

| Overclaim | Precise rewrite | Which words carry the qualification |
|---|---|---|
| "All tool calls by this agent are governed." | "Tool calls that reach the agent through the wrapped synchronous invocation surface are evaluated and recorded before execution; asynchronous invocation is declared unsupported and fails rather than executing; direct invocation of the underlying callable is ungoverned." | *reach through the wrapped … surface*; the explicit disposal of the two other paths |
| "The system prevents unauthorized refunds." | "For refund operations issued through the governed tool, an operation without a matching authorization produces a recorded deny decision and no side effect on the refund ledger. Refunds issued by code paths outside the governed tool are not evaluated." | *issued through the governed tool*; *and no side effect*; the second sentence, which is the whole claim |
| "Our evidence proves the agent complied with policy." | "The evidence stream, when it validates, proves that the supplied records are internally consistent and bound to a specific contract revision. It does not prove that the records are complete or that the events described occurred." | *supplied*; *when it validates*; the entire second sentence |
| "The adapter supports CrewAI." | "The adapter is tested against CrewAI 1.15.4 exactly, enforces that pin at import time, and declares one wrapped surface out of six; no coverage is claimed for any other version." | *tested against … exactly*; *enforces that pin at import time*; *one of six* |

**Table 14.2 — Overclaims and their precise rewrites.** The rewrites are longer, and length is not the point: each added clause is answering one of the eight assurance questions from Chapter 3 that the original left open. The teaching purpose is that qualification is compositional — you can generate the rewrite mechanically by asking, for each claim, which surface, which mechanism, under which conditions, and at which tier.

Two failure modes deserve names, because both are common and neither is dishonest in intent.

The first is the <span class="ix" data-ix="scope elision">scope elision</span>: dropping the surface qualifier because in the author's mental model there is only one surface. "All tool calls are governed" is very often written by someone who has never used the asynchronous path and does not think of it as existing. The remedy is procedural rather than moral: derive the surface list from the coverage inventory, not from memory.

The second is the <span class="ix" data-ix="tier inflation">tier inflation</span>: writing a cooperative-enforcement result in language borrowed from mandatory enforcement. "Prevents," "blocks," and "cannot" are mandatory-enforcement verbs. A cooperative in-process control earns "evaluates," "denies," "records," and "does not execute the wrapped action" — all of which are true, and none of which imply that no other path exists. Chapter 13's tier vocabulary exists precisely so that this distinction has words. Note that the same discipline appears inside the repository's own decision records, which observe that the word "guarantee" is deliberately avoided because a design-time tier does not guarantee runtime behavior and an independent-enforcement tier is not delivered by the toolchain alone.

> **Design checkpoint.** Before publishing any governance claim, run it against four questions and keep the answers with the claim: (1) Which surfaces, named from the inventory, does it cover? (2) What mechanism makes it hold, and where does that mechanism sit relative to the effect? (3) What must be true of the deployment for the mechanism to be in the path? (4) Which assurance tier does the resulting claim support, and does the verb in your sentence match that tier? If any answer is "I would have to check," the claim is not ready to ship.

## Summary

A governance component's coverage is part of its interface. Published as a typed, machine-readable inventory, it converts an unfalsifiable claim into a testable one; withheld, it leaves the scope of every downstream claim to the reader's imagination, which reliably defaults to "everything." Coverage needs three states rather than two, because a surface the component's authors declined to wrap and a surface the integrator must wrap themselves place different obligations on different people. Bypass follows from architecture rather than from malice: any wrapper can be called around, asynchronous variants of wrapped operations are easy to miss, and framework upgrades introduce surfaces that no existing adapter covers. The engineering response is negative controls — tests that prove a denial produced no effect, that a failure produced no success record, and that a known bypass runs exactly as declared. The repository's own bypass test, which asserts that its component can be circumvented, is the clearest available example of a claim being pinned rather than asserted. Finally, all of this reaches the outside world as sentences, and a precise governance sentence names its surface, its mechanism, its conditions, and its tier.

- Coverage inventories are versioned interface elements, not release notes; wrapped, unsupported, and unwrapped are operationally distinct.
- Publishing uncovered surfaces helps defenders and deployers far more than it helps attackers, and is what makes the positive claim falsifiable.
- Bypass arises structurally from direct invocation, uncovered asynchronous paths, and post-upgrade surfaces; exact framework pins enforced at import time bound the third.
- A denial test must assert the decision, the code, and the absence of side effects — never merely that an exception was raised.
- Where a bypass cannot be detected, the honest control is a test asserting that it exists and behaves as documented.
- Precise claims are compositional: surface, mechanism, conditions, tier. Mandatory-enforcement verbs applied to cooperative controls are the most common form of overclaim.

## Review questions

1. Explain why a two-state coverage model (covered/uncovered) is insufficient, using the distinction between an asynchronous surface the adapter's authors declined to wrap and a graph-construction surface the integrator owns. What different obligation does each impose, and on whom?
2. State the strongest version of the argument that publishing an unsupported-surface list aids attackers, then give the three counterarguments from Section 14.3. Which of the three would you use with a sceptical security officer, and why?
3. A colleague proposes replacing the repository's bypass test with a paragraph in the README saying the same thing. Give two concrete things the test provides that the paragraph does not.
4. Distinguish "the enforcement point denied the action" from "the action raised an exception." Design the minimum set of assertions that separates them, and name one defect each assertion catches.
5. A framework releases a minor version adding a new tool-dispatch entry point. Trace what happens to (a) the coverage inventory, (b) the truth of the claim "tool invocations are governed," and (c) the deployment, in a system that pins the framework exactly versus one that accepts a range.
6. Rewrite the following as a precise claim, and list the words carrying each qualification: "Our platform ensures agents cannot access production databases."

## Exercises

1. **Write the inventory you do not have.** Take an agent integration you can read — your own, or an open-source example — and produce a coverage inventory in the three-state form. For every entry, write the *reason* field as if a reviewer will challenge it. Then count: how many surfaces did you discover in the process that you had not previously thought about? Which of them are reachable in your current deployment?
2. **Build a bypass control.** For one wrapped operation in that integration, write two tests: one asserting the governed path denies an unauthorized request with zero side effects, and one asserting that calling the underlying operation directly runs it ungoverned. Then write the three-sentence claim that both tests jointly support, using the qualification structure of Table 14.2.
3. **Audit four claims.** Collect four governance sentences from real material — a vendor datasheet, a security questionnaire response, an internal architecture document, a compliance control description. For each, identify which of the four qualification elements is missing, and rewrite it. Where a rewrite requires information you do not have, record the question you would need answered; that list is the beginning of a supplier-assessment questionnaire.

## Further reading

- [@schneider-enforceable] — establishes formally which security policies a reference monitor can enforce by observing execution; the theoretical counterpart to this chapter's practical claim that enforcement holds only where the monitor is in the path.
- [@saltzer-schroeder] — the "complete mediation" principle states this chapter's thesis in one phrase; reading the original clarifies why partial mediation is a different property, not a weaker version of the same one.
- [@swebok-testing] — standard vocabulary for test design; useful for placing negative controls within a broader test taxonomy rather than treating them as an ad hoc category.
- [@owasp-agentic] — catalogues agentic-system threats including tool misuse and control circumvention; read alongside Section 14.4 to see how bypass appears in an industry threat catalogue.
- [@nornyx-repo] — the coverage inventory, the bypass test, and the A/B benchmark's declared controls are all readable in the repository, and reading them is more instructive than reading about them.
