# Risk Register

| Risk | Severity | Mitigation |
|---|---:|---|
| Overreach as a full general-purpose language | High | Keep v0.1/v1.0 focused on control-plane language |
| Becomes verbose YAML | Medium | Add concise syntax and generator value |
| Weak enforcement of policies | High | Clearly separate declared policy from runtime-enforced policy |
| Unsafe connector execution | High | Capability manifests, sandboxing, signed connectors, no arbitrary exec by default |
| LLM hallucinated syntax | Medium | Strong examples, checker diagnostics, LSP |
| Adoption friction | High | Generate standard artifacts and preserve existing stacks |
| Ecosystem burden | High | Interop-first, plugin architecture |
| Eval gaming | Medium | Eval integrity, holdouts, adversarial rotations |
| Context poisoning | High | Provenance, taint, authority order, channel separation |
| Self-improvement regression | High | Proposal-only loops, eval gates, human approval |
| Name legal conflict | Medium | Formal trademark clearance before public launch |
