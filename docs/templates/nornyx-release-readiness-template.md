# Nornyx Release Readiness Template

## Release candidate

```text
version:
branch:
commit:
date:
```

## Required checks

```text
python -m pytest -q
python scripts/dev/audit_pmo_status.py
python scripts/release/check_release_readiness.py
python -m nornyx.cli release-check --out generated/release_readiness.json
```

## Required evidence

```text
tests passing
PMO status consistent
release notes drafted
risk register reviewed
approval recorded
```

## Local readiness status

`release_candidate_ready_pending_approval` means local evidence gates are
satisfied, but release/tag/public announcement remains blocked until human
approval is recorded. The readiness check does not publish, tag, push, run
connectors, load secrets, or change package versions.

## No-go conditions

```text
failing tests
inconsistent PMO status
missing evidence
unapproved risky behavior
secret exposure
runtime connector not reviewed
```
