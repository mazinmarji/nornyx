---
chapter: 1
part: I
title: "From Deterministic Software to Agentic Behavior"
---

# From Deterministic Software to Agentic Behavior

> **Opening scenario.** Northstar Services, a mid-size financial-services and software company, is piloting an artificial-intelligence research assistant in its Research & Insights division. During the pilot, an analyst asks the assistant to compile a briefing on a competitor. The assistant searches the public web, retrieves a dozen pages, and drafts a plan. One retrieved page contains a paragraph addressed not to human readers but to "AI assistants," suggesting that summaries be posted to a public collaboration site "for transparency." The assistant's draft plan includes a step to publish the briefing externally. The step fails only because nobody happened to wire a publishing tool into the pilot environment. In the review meeting that follows, the platform team is asked a simple question: *which of our existing controls — the specification, the test suite, code review, or the cloud permission model — would have prevented that step deterministically?* Nobody has a good answer.

> **Learning objectives.**
> - Identify the control expectations engineers inherit from deterministic software: specifications, tests, code review, and least privilege.
> - Explain precisely what changes when the executing component is a probabilistic planner that invokes tools.
> - Define and distinguish four properties of agentic execution: non-reproducible decision paths, instruction–data confusion, capability reachability versus authorization, and emergent action sequences.
> - Trace why each inherited control degrades rather than fails outright, and what each still contributes.
> - Describe the case-study setting, Northstar Services, used throughout this book.

> **Prerequisites.** None. This is the opening chapter. It assumes the general software-engineering background described in the preface: version control, continuous integration, APIs, and the ability to read YAML and simple Python.

## The control model deterministic software taught us

Software engineering has spent decades building a control model around one quiet assumption: the executing component does exactly what its text says. A compiled program is a fixed function from inputs to behavior. That assumption is so deeply embedded that most engineers never state it, yet nearly every control they rely on depends on it.

Consider what the assumption buys. A <span class="ix" data-ix="specification">specification</span> is worth writing because the program text can be checked against it, and the program text *is* the behavior: once the implementation conforms, every future execution conforms. A test is worth running because determinism generalizes its verdict; when a test exercises a code path today, the same path behaves the same way tomorrow, on another machine, under another user. Code review is worth the reviewer's hours because reading the diff is reading the future behavior of the system — there is no gap between what is inspected and what will run. And <span class="ix" data-ix="least privilege">least privilege</span>, the principle that a component should hold only the authority its function requires [@saltzer-schroeder], is *computable*: from the program text one can enumerate which files are opened, which endpoints are called, which credentials are needed, and grant exactly that. Lampson's early formulation of protection domains assumed precisely this — a subject whose possible actions can be bounded in advance because its program is fixed [@lampson-protection].

The same assumption underpins operational practice. Failures are analyzed by replaying inputs, because <span class="ix" data-ix="reproducibility">reproducibility</span> makes the failure a stable object of study. Change management works because behavior changes only when an artifact changes, so controlling artifact changes controls behavior changes. Even organizational accountability rides on determinism: when an incident review asks "why did the system do X?", the answer is found in code and configuration, both of which have authors, reviewers, and timestamps.

It is worth being precise about the inheritance, because this book is about what happens when its foundation moves. Four expectations matter most:

1. **Behavior is specified.** The authoritative statement of what the system does is an artifact — code — that humans wrote and can read.
2. **Tests are evidence about the future.** A passing test is a durable claim: this path, under these inputs, produces this result, indefinitely, until the artifact changes.
3. **Review inspects the decision logic itself.** Approving a change means a qualified human has read the exact logic that will execute.
4. **Authority can be minimized statically.** The set of actions a component can take is knowable in advance, so permissions can be shaped to match it.

None of these expectations is naive. They are the accumulated engineering answer to the question "how do we trust software we did not personally write?" The problem this book addresses is that a new kind of executing component has arrived for which every one of the four expectations is weakened at once.

## When the executing component is a planner

An <span class="ix" data-ix="agentic system">agentic system</span> is a software system in which a machine-learning model — today, almost always a large language model (LLM) — selects actions at run time in pursuit of a goal, typically by invoking <span class="ix" data-ix="tool">tools</span>: functions, APIs, shell commands, database queries, or other programs. The now-standard pattern interleaves reasoning and acting: the model produces a step of reasoning, chooses a tool and arguments, observes the tool's result, and repeats until it decides the goal is met [@react]. Practical guidance from model providers describes the same loop: an agent is a model using tools in a feedback cycle, with the model deciding, at each iteration, what to do next [@anthropic-agents].

The crucial phrase is *the model deciding*. In deterministic software, control flow is authored: a human wrote the `if` statement that routes this input to that action. In an agentic system, control flow is *generated*: the mapping from situation to action is computed at inference time by a <span class="ix" data-ix="probabilistic planner">probabilistic planner</span> — a sampling process over a learned distribution, conditioned on everything in the model's context window. The "program" that determines behavior is no longer a reviewable text. It is the combination of model weights (billions of parameters, not human-readable), a prompt (human-readable but advisory), retrieved context (often produced by external parties), tool results (produced by the environment), and sampling randomness.

Figure 1.1 contrasts the two execution models. In the deterministic pipeline, the specification-to-behavior chain is mediated entirely by artifacts that humans author, review, and version. In the agentic loop, an inference step sits at the center of the chain, and three of its four inputs — context, tool observations, and sampling noise — are not artifacts under change control at all.

<figure class="nx-fig" id="fig-1-1">
  <div class="fig-body">
    <div class="flow-col">
      <div class="flow"><div class="node">Specification</div><div class="arr">→</div><div class="node">Source code</div><div class="arr">→</div><div class="node">Build + CI</div><div class="arr">→</div><div class="node">Deterministic execution</div><div class="arr">→</div><div class="node">Predictable action</div></div>
      <div class="flow"><div class="node">Goal prompt</div><div class="arr">→</div><div class="node">Model inference (sampled)</div><div class="arr">→</div><div class="node">Tool call</div><div class="arr">→</div><div class="node">Observation joins context</div><div class="arr">→</div><div class="node">Next inference…</div></div>
    </div>
  </div>
  <figcaption><b>Figure 1.1 — Two execution models.</b> Top: the deterministic chain, in which every step from intent to action is mediated by reviewable, versioned artifacts. Bottom: the agentic loop, in which a sampled inference step chooses each action and its own future inputs. The figure's teaching purpose is to locate exactly where the inherited control model loses its grip: the middle of the bottom row is not an artifact.</figcaption>
</figure>

Nothing about this is a defect of the model. Selecting plausible actions in novel situations is the capability being purchased; a model that always did the same thing would be a lookup table. The engineering question is therefore not "how do we make the planner deterministic?" — we cannot, and would not want to — but "what must surround a non-deterministic planner so that an organization can still make deterministic statements about what its systems will and will not do?" Answering that question is the subject of this book. First, we need to be precise about what exactly has changed.

## Four properties that change the control problem

Four properties of agentic execution, taken together, distinguish the control problem from everything the deterministic inheritance prepared us for. Each is worth defining carefully, because the rest of the book builds on these definitions.

### Non-reproducible decision paths

A deterministic program's execution path can be replayed: same inputs, same branch decisions, same outcome. An agentic run generally cannot. Sampling temperature introduces explicit randomness; provider-side model updates change the distribution silently; and even at temperature zero, minute context differences — a retrieved document reordered, a timestamp in a tool result — can flip a decision. The consequence is that a run is an <span class="ix" data-ix="non-reproducible decision path">non-reproducible decision path</span>: an unrepeatable trajectory through a space of possible action sequences.

This breaks two load-bearing practices at once. Testing loses its generalization power: a passing agent test demonstrates that *one sampled trajectory* behaved acceptably, not that the path is fixed [@swebok-testing]. And incident analysis loses replay: when an agent does something harmful, rerunning it with the same inputs may produce a different, innocent trajectory, leaving investigators with nothing to study unless the original run was recorded — a theme Chapter 11 develops into the discipline of runtime evidence.

### Instruction–data confusion

A conventional program keeps an absolute distinction between code and data: input can change *which* branch executes, but cannot add new branches. An LLM has no such boundary. Instructions and data arrive through the same channel — the context window — and the model's disposition to follow instructions applies to *all* text it reads, whatever its origin. A retrieved web page, a customer email, a file comment, or a tool's error message can contain imperative sentences, and the model may act on them. This is <span class="ix" data-ix="instruction-data confusion">instruction–data confusion</span>, and its weaponized form is <span class="ix" data-ix="prompt injection">prompt injection</span>: an attacker plants instructions in content the agent will process, and the agent executes the attacker's intent with the agent's authority [@greshake-injection; @willison-injection]. Indirect injection — instructions hidden in material the agent retrieves rather than in the user's request — is ranked among the most serious risks for LLM applications [@owasp-llm].

The deterministic inheritance offers no analogue. There is no input to a compiled accounting system that adds a "wire money to this account" branch. In an agentic system, *every* input is potentially a branch. The opening scenario is exactly this property: a paragraph on a public web page functioned as code. Chapter 6 treats injection formally as a problem of authority and context provenance; for now, the essential observation is that any control expressed *as text the model reads* is delivered over the same forgeable channel as the attack.

### Capability reachability versus authorization

In deterministic software, the set of actions a program can take is approximately the set its code invokes, so "what it can do" and "what we decided it may do" are kept close by construction. In an agentic system these sets come apart. The planner can, in principle, invoke any tool wired into its process, with any arguments it can generate — and, through general-purpose tools such as a shell or an HTTP client, reach far beyond anything enumerated at design time. Call the set of actions the agent can physically perform its <span class="ix" data-ix="reachability">reachable set</span>, and the set someone actually decided it should perform its <span class="ix" data-ix="authorization">authorized set</span>. Figure 1.2 shows the relationship: the reachable set is defined by integration accidents — what happens to be linked in, what credentials the process holds — while the authorized set exists, in most early deployments, only in people's heads.

<figure class="nx-fig" id="fig-1-2">
  <div class="fig-body">
    <div class="zones">
      <div class="zone" data-name="Reachable set — everything wired into the agent process">
        <div class="node">web.search</div>
        <div class="node">web.fetch</div>
        <div class="node">http.post (any endpoint)</div>
        <div class="node">file.write</div>
        <div class="node">shell (via a helper tool)</div>
        <div class="zone" data-name="Authorized set — what anyone actually decided">
          <div class="node">web.search (approved sources)</div>
          <div class="node">summarize</div>
          <div class="node">file to internal store</div>
        </div>
      </div>
    </div>
  </div>
  <figcaption><b>Figure 1.2 — Reachability versus authorization.</b> The outer box is determined by integration: every tool, credential, and side effect physically available to the agent process. The inner box is determined by intent. The teaching purpose of this figure is the gap between the boxes: in an ungoverned deployment that gap is invisible, unversioned, and crossed at the planner's discretion.</figcaption>
</figure>

The gap matters because permissions in existing infrastructure attach to the *process*, not to the *decision*. The agent process legitimately needs broad credentials — it must read the repository, call the model API, write files — so identity and access management (IAM) grants them to the process as a whole, and every action the planner samples inherits them. Least privilege, as inherited, minimizes the outer box. It says nothing about which actions inside the outer box are authorized for which purposes under which conditions. Chapter 5 makes this distinction — capability versus permission versus authority — precise.

### Emergent action sequences

Finally, even when every individual action is defensible, the *sequence* may not be. A planner composes actions: read this file, then summarize it, then post the summary. Each step can be individually authorized — reading internal documents is fine, posting to the support portal is fine — while the composition (posting an internal document's contents externally) violates a rule nobody wrote down because nobody imagined the sequence. These are <span class="ix" data-ix="emergent action sequence">emergent action sequences</span>: behaviors that exist only at the level of composition, generated at run time, drawn from a combinatorial space no test suite can enumerate.

Deterministic systems have composition bugs too, but their compositions are authored and therefore reviewable. An agentic system's compositions are sampled. Controls that evaluate one action at a time — a per-call permission check, a content filter on one message — are structurally blind to them. Governing sequences requires state: knowing what has already flowed where, which boundaries have been crossed, what this data is tainted by. That requirement drives much of Part II's architecture, in particular trust zones (Chapter 6) and evidence with ordering semantics (Chapter 12).

## Why the inherited controls degrade

With those four properties in hand, we can revisit the inherited control model and see exactly where each expectation bends. The point is not that the old controls are useless — every one of them survives in some form — but that each silently changes from a *guarantee* into a *sample*, an *advisory input*, or a *perimeter*, and organizations that do not notice the change are operating with less assurance than they believe. Table 1.1 summarizes the shift.

| Inherited control | Deterministic assumption | What actually changes | What survives |
|---|---|---|---|
| Specification | The spec constrains behavior via code that implements it | The nearest analogue — the prompt — is advisory input to a sampler, delivered in-band with untrusted data | Specifying *tools and integrations* still constrains the reachable set |
| Testing | A passing test binds future executions of the same path | A passing agent test is one sampled trajectory; behavior is a distribution, and the distribution shifts with model updates | Testing the *deterministic surroundings* (tools, checks, gates) retains full force |
| Code review | Reading the diff is reading the future behavior | The decision logic is model weights; reviewers can read prompts and tool code, not the mapping from situation to action | Review of tool implementations, permissions, and policy artifacts remains decisive |
| Least privilege | Grants can be shaped to code's enumerable needs | Grants attach to the agent process; every sampled action inherits them; per-decision authority is unexpressed | Minimizing the process grant still shrinks the outer (reachable) box |
| Replay and debugging | Failures reproduce from inputs | Trajectories are non-reproducible; the run must be *recorded* to be studied | Recording, if trustworthy, restores post-hoc analysis (Part III) |

**Table 1.1 — How the inherited control model degrades under agentic execution.** Each control changes character rather than disappearing; the danger is applying the old confidence to the new character.

Two rows deserve emphasis. First, the specification row: teams routinely respond to agent incidents by writing more elaborate instruction files and system prompts. Those artifacts have real value — they shift the model's behavioral distribution in the intended direction — but they are *requests*, honored probabilistically, and they share a channel with adversarial text. Listing 1.1 shows the kind of artifact involved.

```text
# AGENTS.md (excerpt from a typical repository)

- Never send customer data or credentials to external services.
- Always run the full test suite before proposing a merge.
- Do not modify files under auth/ or crypto/ without human sign-off.
- Use only the tools listed in this file.
```

**Listing 1.1 — An instruction file is advice, not a control.** Illustrative — not drawn from the repository. Every line expresses a genuine governance intent, and a capable model will usually honor them. But the file is consumed as context by a sampler: nothing checks it, nothing enforces it, nothing records whether it was followed, and a sufficiently persuasive piece of retrieved text competes with it on equal terms.

Second, the testing row: it is tempting to answer distributional behavior with more tests — larger evaluation suites, adversarial prompts, red-team batteries. These are necessary and this book will use them (Chapter 15 treats testing governance claims in depth). But evaluation of a distribution yields statistical confidence, not the per-execution certainty the deterministic inheritance trained organizations to expect. A 99.9% policy-adherence rate on an evaluation suite is a strong result and still means an agent taking ten thousand actions a day crosses the line ten times.

> **Key idea.** Agentic systems do not remove the need for deterministic control; they relocate it. The planner cannot be made deterministic, so the determinism must live *around* the planner — in the components that decide whether a proposed action may proceed, record what was decided, and prove it afterward. Everything in this book follows from taking that relocation seriously as an engineering problem.

## Northstar Services: the setting for this book

Abstract properties become design problems only inside a concrete organization, so this book follows one: **Northstar Services**, a fictional mid-size financial-services and software company of roughly four thousand staff, regulated in both the European Union and the United States. Northstar's divisions — Customer Operations, Treasury, Engineering Platform, Research & Insights, and Risk & Audit — will each eventually host governed agentic systems. Its chief technology officer sponsors an "AI delivery" program; its Risk & Audit chief has set one condition that shapes the entire book: *no agentic system reaches production until its controls are demonstrable* — not asserted, demonstrated. Northstar's engineering conventions are ordinary: GitHub-style repositories, continuous integration (CI) on every pull request, immutable release tags, a central identity provider for humans, and an organization-wide governance repository named `northstar-governance`.

Figure 1.3 places the two threads this chapter seeds within the organization. Five case-study threads run through the book in total; the other three (a multi-agent Treasury workflow, a framework-integration comparison, and an enterprise policy hierarchy) begin in Parts II and V.

<figure class="nx-fig" id="fig-1-3">
  <div class="fig-body">
    <div class="hier">
      <ul>
        <li>Northstar Services
          <ul>
            <li>Customer Operations</li>
            <li>Treasury</li>
            <li>Engineering Platform
              <ul>
                <li>Forge — software-development agent (Thread B)</li>
              </ul>
            </li>
            <li>Research &amp; Insights
              <ul>
                <li>Atlas — research assistant (Thread A)</li>
              </ul>
            </li>
            <li>Risk &amp; Audit — requires demonstrable controls</li>
          </ul>
        </li>
      </ul>
    </div>
  </div>
  <figcaption><b>Figure 1.3 — Northstar Services and the first two case-study threads.</b> The teaching purpose of the figure is orientation: Atlas and Forge live in different divisions, face different risks, and will need different controls, yet both answer to the same Risk &amp; Audit requirement — which is what will eventually force a common governance discipline.</figcaption>
</figure>

> **Case study — Atlas.** Atlas is the research assistant from the opening scenario: a single agent in Research & Insights. Its intended charter is narrow. It may search an approved allowlist of sources, retrieve and summarize documents, and file summaries to an internal store. It may not publish externally, purchase anything, disclose confidential data, or invoke tools nobody approved. Notice that this charter is already a statement about the *authorized set* of Figure 1.2 — and that in the pilot, it existed only as intentions and an instruction file. The near-miss happened precisely in the gap between the reachable and the authorized. Atlas returns in Chapter 5, where its identity and capabilities are made explicit; in Chapter 7, where its charter becomes evaluable policy; in Chapter 10, where a denial is enforced; and in Chapters 11, 20, and 36, where its actions leave evidence an auditor can reconstruct.

> **Case study — Forge.** Forge is Engineering Platform's AI development system, being piloted on the repository `northstar/payments-api`. Its intended charter is more consequential than Atlas's: Forge may read the repository, propose changes on branches, run tests, and open pull requests — but merging to protected branches, deploying to production, publishing releases, touching secrets, destructive changes, and edits to security-sensitive paths such as `auth/` and `crypto/` must all require a named human approval, with the proposer never approving their own change. Forge's risks are not about retrieved web pages; they are about *authority over the software supply chain itself*. Forge returns in Chapter 2, where its scattered controls drift into a live incident; in Chapter 9, where approvals become bound records; in Chapters 15, 29, and 30, where its governance is tested, wired into CI, and treated in full depth.

The two threads are deliberately different. Atlas's dominant hazards are instruction–data confusion and the reachability gap — an agent that reads the hostile internet and could act beyond its charter. Forge's dominant hazards are authority and accountability — an agent whose *legitimate* actions, wrongly sequenced or wrongly approved, alter production software. A governance discipline must serve both, which is why this book insists on general concepts before any particular mechanism.

## Toward a deterministic governance boundary

Where does this leave the engineer? The four changed properties do not merely weaken individual controls; they dissolve the place where control used to live. In deterministic software, the program text was simultaneously the specification of behavior, the object of review, the basis for testing, and the source of the permission inventory. In an agentic system, that single load-bearing artifact is gone, and organizations improvise replacements: instruction files here, prompt fragments there, a CI check, an approval form, a guardrail service — each partial, each in a different format, none authoritative. Chapter 2 examines the predictable result of that improvisation, which we will call the governance gap, and gives its failure modes a taxonomy.

The constructive direction can be stated now, because it follows directly from this chapter's analysis. If the planner is irreducibly probabilistic, then the deterministic statements an organization needs — "this agent cannot publish externally," "no production change merges without a bound human approval" — must be made true by components *other than the planner*: components that are themselves ordinary deterministic software, with specifications, tests, reviews, and minimized privileges. The discipline this book develops is the engineering of that surrounding structure: a <span class="ix" data-ix="governance boundary">deterministic governance boundary</span> — an explicit, versioned, testable model of who may act, on what, under which conditions, with what evidence, and under whose accountability. Chapter 3 establishes what such a boundary can and cannot guarantee, and Chapter 4 lays out its core vocabulary and its relationship to neighboring technologies.

A note on tooling. From Part IV onward, this book grounds the discipline in Nornyx, an openly inspectable contract language and toolchain that implements the design-time and cooperative-runtime layers of governance as executable, versioned artifacts. Nornyx is used as a concrete case study — including a case study in honest limits, because a governance layer that overstates its guarantees is itself a risk. Until then, no Nornyx knowledge is needed, and every concept in Parts I–III stands independent of any product.

> **Misconception.** *"Better models will make this chapter obsolete: a sufficiently aligned model will not need external control."* Model improvement genuinely reduces the frequency of undesired actions, and alignment work matters. But frequency is not the issue; *guarantee structure* is. An organization's obligation — to a regulator, an auditor, a customer, or its own risk office — is typically of the form "X cannot happen without Y," and no statistical disposition, however good, has that form. A model that follows instructions 99.99% of the time still offers no component that *decides*, no record of what was decided, and no evidence to show afterward. Alignment shifts a distribution; governance makes and proves commitments. The two are complements, not substitutes — a point Chapter 2 develops in detail.

## Summary

Deterministic software gave engineering a control model whose every element — specification, testing, review, least privilege, replay — leans on the assumption that program text fixes behavior. Agentic systems replace the authored control flow with a probabilistic planner invoking tools, and four properties follow: decision paths are non-reproducible, instructions and data share one forgeable channel, the reachable action set silently exceeds the authorized one, and harmful behavior can emerge from sequences of individually acceptable actions. Under those properties each inherited control degrades in character — from guarantee to sample, from enforcement to advice — while remaining valuable within its reduced scope. The engineering response is not to make the planner deterministic but to relocate determinism into an explicit governance boundary around it.

- Specifications, tests, review, and least privilege all assume program text fixes behavior; agentic execution breaks that assumption in four distinct ways.
- Prompts and instruction files are advisory context, not controls: unverified, unenforced, unrecorded, and in-band with untrusted data.
- Reachability is set by integration; authorization is set by intent; ungoverned deployments never represent the difference.
- Sequences, not just actions, are the unit of harm — and sequences are sampled from a space tests cannot enumerate.
- Northstar Services, with its Atlas and Forge pilots, is the recurring setting in which these problems become concrete design work.

## Review questions

1. State the four control expectations inherited from deterministic software, and for each, identify the specific agentic property (from this chapter's four) that most directly undermines it.
2. Explain the difference between the reachable set and the authorized set of an agent's actions. Why does process-level least privilege bound only one of them?
3. A team responds to an agent incident by adding three paragraphs to the system prompt and re-running their evaluation suite, which passes. Using this chapter's vocabulary, describe exactly what assurance they have gained — and what they have not.
4. Why is a harmful emergent action sequence harder to control with per-action checks than a harmful single action? What information would a control need in order to see the sequence?
5. In the opening scenario, the publish step failed only because no publishing tool was wired in. Classify that outcome: was it enforcement of the authorized set, minimization of the reachable set, or luck? Justify your classification.
6. The Risk & Audit chief demands controls that are "demonstrable, not asserted." Give one example each of an asserted control and a demonstrable control from your own engineering experience.

## Exercises

1. **Inventory the gap.** Choose a real or hypothetical agent deployment (a coding assistant with repository access is a good default). Enumerate its reachable set as concretely as you can: every tool, credential, filesystem scope, and network capability the process holds. Then write down the authorized set as the deploying team would state it. Present the two sets in the style of Figure 1.2 and mark the three gap items you consider most dangerous.
2. **Advice versus control.** Take Listing 1.1 and, for each of its four lines, answer: (a) what component, if any, could *deterministically* enforce this rule today, outside the model? (b) what evidence would exist afterward that the rule held? Where your answer to (a) is "none," sketch in one sentence what such a component would have to observe and decide.
3. **Trajectory non-reproducibility.** Design (on paper) an experiment to measure decision-path variance for a tool-using agent: fixed goal, fixed toolset, N repeated runs. Define what you would record per run, how you would decide that two trajectories are "the same decision path," and what variance result would convince you that replay-based debugging is infeasible for this system.

## Further reading

- [@react] — the reasoning-and-acting loop that defines the execution model this chapter analyzes; read it to see how deliberately the planner is placed in the control-flow seat.
- [@anthropic-agents] — a practitioner's account of agent architectures, useful for calibrating which patterns (workflows versus autonomous loops) concentrate the risks described here.
- [@saltzer-schroeder] — the classic statement of least privilege and fail-safe defaults; the vocabulary of Parts I–II repeatedly returns to it.
- [@greshake-injection] — the paper that demonstrated indirect prompt injection against deployed LLM applications; the empirical basis for this chapter's instruction–data confusion property.
- [@owasp-llm] — a maintained catalogue of LLM application risks; useful as a checklist counterpart to this chapter's conceptual framing.
