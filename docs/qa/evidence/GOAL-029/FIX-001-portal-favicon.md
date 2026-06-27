# FIX-001 — Developer PMO Portal Favicon

## Issue

Browser console showed:

```text
:5174/favicon.ico:1 Failed to load resource: the server responded with a status of 404 (File not found)
```

## Root cause

The local PMO portal did not serve a favicon route. Browsers request `/favicon.ico` automatically even when the app does not explicitly reference one.

## Fix

The portal now serves a small built-in SVG favicon from:

```text
/favicon.ico
/favicon.svg
```

## Safety

Static response only.

No Git writes, LLM calls, external network calls, credentials, or runtime command execution.

## Validation

```powershell
python -m pytest -q tests/test_nornyx_dev_pmo_portal_favicon.py
```
