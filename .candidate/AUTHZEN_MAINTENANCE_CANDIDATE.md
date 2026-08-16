# Isolated AuthZEN Maintenance Candidate

This branch is a non-publishing validation surface created under Arsoryn FD-007.

Base: `nornyx` v1.11.0 (`dca0ac676ff7a30a5b97ac6d0b4cf58c6fc07c2f`).

Added product scope: exactly the four files from merged PR #80:

- `nornyx/agentic/authzen.py`
- `tests/test_agentic_authzen.py`
- `docs/69_AUTHZEN_INTEROPERABILITY.md`
- `docs/decisions/ADR-0044-authzen-interoperability.md`

The branch also contains candidate-only CI/metadata used to validate this isolated tree. It is not a release, tag, publication, or authorization to bypass the normal Nornyx release gate.
