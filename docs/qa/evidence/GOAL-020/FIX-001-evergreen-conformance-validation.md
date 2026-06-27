# FIX-001 — Evergreen Conformance Validation

## Issue

`tests/test_evergreen_assurance.py::test_candidate_extension_requires_conformance` failed because the Evergreen Assurance validator allowed an empty `conformance` list for a `candidate` extension.

## Root cause

The helper `_string_list()` returned `True` for an empty list because Python `all([])` is `True`.

That behavior is acceptable for optional compatibility fields, but not for required extension fields.

## Fix

Added `_non_empty_string_list()` and used it for:

```text
kernel.stable_blocks
extension.provides
candidate/stable extension.conformance
```

Optional compatibility lists still use `_string_list()`.

## Expected validation

```powershell
python -m pytest -q tests/test_evergreen_assurance.py
python scripts\dev\run_quality.py
```

## Safety

Local validation only. No connectors, LLM calls, credentials, GitHub writes, deployment, or autonomous execution.
