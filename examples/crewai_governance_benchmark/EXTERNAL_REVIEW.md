# External review

This benchmark exists to be argued with. If it convinced you of something it did
not actually demonstrate, that is a defect in the benchmark and we would rather
hear it than not.

Run it first — see `REVIEWER_QUICKSTART.md` — then answer whichever questions
below you have an opinion about. Partial answers are useful. Blunt answers are
more useful.

**No reviewer data is collected by anything in this repository.** The benchmark
writes only local files and makes no network call. Send your answers wherever you
prefer: a GitHub issue, a pull request against this file, or privately.

---

## The questions

### 1. Was Nornyx's purpose clear *before* you ran anything?

From the README and this example's docs alone, could you state what Nornyx does
and what it does not do? If you had to run the code to find out, what should have
told you sooner?

### 2. Was installation straightforward?

Specifically: did the Python version requirement (3.10–3.13, not 3.14) bite you?
Did the fact that `nornyx-agentic-adapters` is not on PyPI cause confusion? Did
anything fail without telling you why?

### 3. Did the A/B comparison appear fair?

This is the question that matters most. Consider:

- Both variants run real `Agent`/`Task`/`Crew`/`Crew.kickoff()` with the same
  scripted offline model and the same shared business callables.
- The baseline keeps its own application-level validation (the refund
  auto-approval limit), and S18 exists specifically to show the baseline
  refusing something on its own.
- The baseline executes prohibited actions for an ordinary reason: the tool was
  attached to the agent and nothing else was asked.

Is that a fair baseline, or is it a strawman? If you think it is rigged, name the
scenario and say how you would build it instead.

### 4. Did the side-effect ledger convincingly prove prevention?

The core claim is that a denied action's business callable never ran — evidenced
by counters on a single monotonic clock rather than by an exception message. Did
you check it directly (`REVIEWER_QUICKSTART.md` §1 and §3)? Did you believe it?
Is there a way the ledger could report zero while the work actually happened?

### 5. Were any Nornyx claims unsupported by the evidence?

Read `benchmark.md` and `dashboard.html` adversarially. Flag any sentence that
claims more than the run established — particularly anywhere the report implies
coverage of a surface the adapter declares `unsupported`, or implies that
validated evidence means the recorded events are *true*.

### 6. Which limitation would prevent production adoption?

Candidates the benchmark already surfaces:

- enforcement is cooperative, so the S15 bypass works
- only synchronous CrewAI tool invocation is a wrapped surface
- one exact CrewAI version is supported (`==1.15.4`)
- the two evidence defects in `FINDINGS.md`
- the adapter package is not published

Which of these is actually disqualifying for you, and which are acceptable? Is
there a limitation we did not list that matters more than the ones we did?

### 7. Which additional framework or integration would be most valuable?

LangGraph is declared pending. Would that be the right next one for your work, or
would something else (LlamaIndex, AutoGen, OpenAI Agents SDK, a plain
function-calling loop, an MCP server boundary) be more useful?

### 8. Would you use this in a real project? Why or why not?

The honest answer is the useful one. If "no", the reason is more valuable than
the verdict — is it maturity, coverage, ergonomics, the contract authoring
burden, the fact that it does not attest runtime truth, or something else?

---

## Things worth attacking specifically

If you want to go looking for problems, these are the seams:

- **The `GovernedInvocationTool` wrapper.** It catches `AdapterDenied` and mints
  a mission id per invocation. Does that wrapper weaken the enforcement claim, or
  is it what a real integration would have to do anyway? (`enforce` still raises
  before the action; the wrapper only decides what CrewAI sees afterwards.)
- **The composed guards.** Zone-crossing and data-share checks run inside the
  adapter's action rather than at a separate wrapped surface. Is that a fair
  representation of "governed", or is it doing work the adapter does not do?
- **Stage separation.** Binding-stage (S05) and load-stage (S12) preventions are
  reported apart from runtime-stage ones. Is that separation honest, or is it
  slicing the numbers to look better?
- **The pinned `decision_at`.** Every temporal check happens at a fixed instant.
  Does that hide any time-dependent failure a real deployment would hit?
- **The contract itself.** `contract/remediation_network.nyx` was written for this
  benchmark. Does it declare an unrealistically convenient set of capabilities,
  zones, and gates?
