# Nornyx AI Pattern Lifecycle

## Purpose

The AI Pattern Lifecycle helps Nornyx convert scattered AI development ideas into reusable engineering assets.

It addresses the problem where teams chase:

```text
prompts
Claude/Codex commands
agent tricks
repo templates
skills folders
workflow hacks
video/post recommendations
```

Instead of chasing tricks, Nornyx should let teams capture, evaluate, promote, and deprecate patterns.

## Lifecycle

```text
idea
→ experimental_pattern
→ evaluated_pattern
→ candidate_profile
→ stable_profile
→ deprecated_pattern
```

## Status meanings

| Status | Meaning |
|---|---|
| `experimental` | Interesting idea, not proven |
| `evaluated` | Tested in at least one controlled setting |
| `candidate` | Reusable and documented, but not default |
| `stable` | Approved for normal use |
| `deprecated` | Kept for history but not recommended |

## Pattern types

```text
prompt
context
agent_workflow
harness
eval
evidence
tool_integration
portal_renderer
security_guardrail
```

## Minimum fields

```text
id
name
type
status
problem
solution
applicability
non_goals
validation
evidence
risks
failure_modes
promotion_criteria
```

## Example

```nyx
pattern ContextAuthorityOrder:
    type: context
    status: candidate
    problem: "Agents treat chat notes as more authoritative than architecture docs."
    solution: "Declare explicit source authority order."
    applies_when:
        - repo has multiple context sources
        - architecture docs exist
    non_goals:
        - solve factual correctness of all docs
    validation:
        - nornyx check
        - context authority conflict test
    evidence:
        - docs/qa/evidence/GOAL-005/
    risks:
        - outdated authoritative docs still mislead
    promotion:
        require eval_pass
        require human_review
```

## Best practice

A Nornyx pattern must state where it works and where it does not.

Avoid universal claims like:

```text
this is the best prompt
this always improves agents
this replaces all workflows
```

Prefer:

```text
this pattern improved this class of tasks under this harness and these evals
```

## Relationship to profiles

Stable patterns can be bundled into profiles:

```text
ai_coding
regulated
legacy_upgrade
nornyx_language
telecom_ops
```

A profile should reference stable or candidate patterns, not random ideas.

## Relationship to Nornyx language

This is optional extension material, not mandatory beginner syntax.

The language core remains small.

Pattern lifecycle helps the ecosystem mature without bloating the core.
