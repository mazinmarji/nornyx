# Reference CI

`scripts/agentic_network_ci.py` is a documented executable workflow, safe to
run without credentials or internet access once dependencies are installed.
No external system is modified. It exits nonzero on any violation.

```text
python scripts/agentic_network_ci.py --out dist/agentic-network-ci
python scripts/agentic_network_ci.py --out dist/agentic-network-ci --wheel
```

Steps performed:

1. (`--wheel`) build the candidate wheel and install it into a clean venv;
   all later Nornyx steps run from that installation;
2. `nornyx check` on the support contract;
3. `nornyx governance resolve` (profile + module resolution);
4. `nornyx agentic-network generate` (deterministic controls);
5. regenerate and byte-compare (generated-artifact drift gate);
6. `nornyx agentic-network lock` + `lock-check`;
7. `nornyx eval-import promptfoo` on the supplied results fixture;
8. `nornyx eval-run --strict` (threshold + dataset integrity validation);
9. the safe CrewAI demonstration path (deterministic harness);
10. the safe LangGraph demonstration path (real `StateGraph` when installed);
11. `nornyx agentic-network evidence-validate --strict` for both evidence
    streams;
12. `nornyx governance explain` (human approval + revision binding view);
13. assemble `audit-package/` (lock, artifacts, eval report, evidence
    reports, demo summary, manifest);
14. nonzero exit on any failure.

## Copy-paste GitHub Actions job

```yaml
agentic-network-governance:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: {python-version: "3.12"}
    - run: python -m pip install build langgraph
    - run: python scripts/agentic_network_ci.py --out dist/agentic-network-ci --wheel
    - uses: actions/upload-artifact@v4
      with:
        name: agentic-network-audit-package
        path: dist/agentic-network-ci/audit-package
```

The job needs no secrets. `langgraph` is optional: without it the
demonstration uses the deterministic harness path for that framework.
