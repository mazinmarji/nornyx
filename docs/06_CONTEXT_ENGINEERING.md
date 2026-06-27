# Context Engineering in Nornyx

Context is not a prompt blob. It is a governed artifact.

## Context dimensions

- source;
- trust level;
- freshness;
- authority;
- taint;
- token budget;
- relevance;
- compression policy;
- provenance hash;
- retention policy.

## v0.2 context pack hardening

The scaffold creates a JSON context pack with:

- file paths;
- SHA-256 hashes;
- byte size;
- provenance source URI;
- channel metadata;
- trust level;
- taint labels;
- authority rank;
- whether the source may define policy.

Repo files are local evidence/reference inputs. They are not executable
instructions by themselves.

## Trust boundary rules

- Untrusted channels cannot define policy.
- Untrusted channels cannot request privileged tool use.
- Higher-authority repo context wins over lower-authority context on conflict.
- Authority rank is metadata until a later enforcement goal adds runtime policy.

## Authority order

Context blocks may declare an `authority` list. Earlier patterns have higher
authority:

```yaml
contexts:
  - name: RepoContext
    include:
      - "docs/**/*.md"
      - "tests/**/*.py"
    authority:
      - "docs/01_LANGUAGE_SPEC_v0_1.md"
      - "tests/**/*.py"
```

Matching files receive `channel: authoritative_repo`, an `authority_rank`, and
`may_define_policy: true`. Other repo files remain trusted reference material
but do not define policy.

## Future context blocks

```yaml
context_playbook:
  evolve_after_harness_run: true
  preserve_authoritative_facts: true
  reject_noisy_summaries: true
  require_versioned_updates: true
```

## Future problem: context supply-chain attacks

As agents increasingly rely on repo docs, tickets, webpages, and connector content, malicious context becomes equivalent to malicious dependencies. Nornyx should treat context as a supply-chain asset.
