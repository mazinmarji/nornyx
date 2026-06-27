# Contributing

Nornyx is currently a design and MVP scaffold. Contributions should preserve these rules:

- Keep v0.1 small and interoperable.
- Prefer generators and checks over proprietary lock-in.
- Do not add destructive command execution to the default runtime.
- Treat context provenance, policy, evidence, and approval as core concepts.
- Add tests for every checker/generator behavior.
- Add docs before adding new language blocks.

## Development commands

```bash
pip install -e ".[dev]"
pytest
nornyx check examples/governed_delivery_control_plane.nyx
```
