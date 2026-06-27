# Smart Prompts for Codex / Claude / Review Agents

## Implement next safe compiler slice

```text
You are implementing Nornyx v0.1 safely.
Read manifest.json, README.md, docs/01_LANGUAGE_SPEC_v0_1.md, docs/12_COMPILER_MVP_PLAN.md, and examples/governed_delivery_control_plane.nyx.
Goal: implement one small compiler/checker/generator improvement.
Constraints:
- Do not add arbitrary shell execution.
- Do not add live LLM calls.
- Preserve existing examples and tests.
- Add tests for new behavior.
Run:
- nornyx check examples/governed_delivery_control_plane.nyx
- pytest
Output:
- changed files
- patch summary
- test evidence
- risk note
```

## Review Nornyx security model

```text
Act as a security reviewer for Nornyx.
Audit docs/05_SECURITY_MODEL.md, docs/10_EXTENSION_PROTOCOLS_MCP_A2A.md, nornyx/*.py, and examples/*.nyx.
Focus on context poisoning, prompt injection, connector misuse, excessive agency, unapproved self-modification, evidence tampering, and supply-chain risk.
Output:
- critical issues
- high/medium/low risks
- recommended safe patches
- acceptance checklist
```

## Extend language spec

```text
Act as a programming-language architect.
Extend docs/01_LANGUAGE_SPEC_v0_1.md with one new block only.
Candidate blocks: guardrail, capability, identity, authority, incident_response, containment, supply_chain, memory_policy.
For the selected block, provide:
- semantics
- syntax
- checker rules
- generated artifacts
- examples
- risks
Do not change implementation unless explicitly requested.
```
