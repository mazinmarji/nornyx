## Nornyx 1.3.0

`pip install --upgrade nornyx`

### New: reference a policy instead of copying it

A policy can now reference the one canonical definition rather than copy its rules:

```yaml
policies:
  - name: SafeDeliveryPolicy
    ref: ../governance/nornyx.workspace.yaml#SafeDeliveryPolicy   # single source
```

- `ref` is `<path>#<PolicyName>`, resolved at load time from a local `.nyx`
  contract **or** a workspace manifest (both shapes supported), relative to the
  contract.
- The reference compiles into inline `rules`, so the **checker, generator, and
  drift gate all see a normal policy** — no new top-level block, the frozen v0.1
  language surface is unchanged, and it's fully backward compatible.
- Clear errors for a missing source, a missing policy, a malformed ref, or
  setting both `ref` and `rules`.

The canonical rules live in **one place**: edit them there and every referencing
contract is updated. Nothing to copy means nothing to drift — the language-native
complement to `nornyx workspace-check`. See the bundled `org_policies.nyx` and
`governed_service.nyx` examples (`nornyx examples`).

### Notes
- Backward compatible — contracts without any `ref` are untouched.
- The Nornyx **language/schema** version is unchanged (still 1.0); this is a
  package release.

**Full changelog:** https://github.com/mazinmarji/nornyx/blob/main/CHANGELOG.md
