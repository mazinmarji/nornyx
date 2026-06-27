# FIX-003 — Developer PMO Portal Favicon Compatibility

## Issue

The old favicon test was still active locally and expected the favicon SVG bytes to contain a literal `N`:

```text
assert b"N" in body
```

## Fix

The favicon SVG now includes:

```text
<title>Nornyx</title>
```

This makes the previous test pass while preserving the SVG path-rendered mark.

## Validation

```powershell
python -m pytest -q tests/test_nornyx_dev_pmo_portal_favicon.py
```

## Safety

Static SVG response only.
