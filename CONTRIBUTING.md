# Contributing

Nornyx is a released public package (`pip install nornyx`) with a stable
contract-language surface. Contributions should preserve these rules:

- Keep the stable language surface small and interoperable.
- Prefer generators and checks over proprietary lock-in.
- Do not add arbitrary or destructive command execution to Nornyx: it checks
  contracts and generates artifacts; external systems execute and enforce.
- Treat context provenance, policy, evidence, and approval as core concepts.
- Add tests for every checker/generator behavior.
- Add docs before adding new language blocks.

Start with the [documentation map](docs/README.md) for what is authoritative,
and the [public boundary policy](docs/public-boundary-policy.md) for what
belongs in this public repository.

## Claims about identity and conformance

Contributions may describe what Nornyx does. They must not assert authority the
project has not established — no trademark registration, no certification, no
endorsement, and no claim that a published artifact carries provenance it does
not carry. The controlled vocabulary is in
[`docs/NYX_FORMAT_AND_CONFORMANCE.md`](docs/NYX_FORMAT_AND_CONFORMANCE.md);
`tests/test_identity_claims_boundary.py` enforces it against the repository's
own documentation. Independent implementations of Nornyx semantics are a goal
of the project — see [`TRADEMARKS.md`](TRADEMARKS.md).

## Development commands

```bash
pip install -e ".[dev]"
pytest
nornyx check examples/governed_delivery_control_plane.nyx
```
