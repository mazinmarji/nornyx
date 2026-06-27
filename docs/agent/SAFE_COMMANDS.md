# Safe Commands for Nornyx Agent Work

## Safe local commands

```powershell
python -m pytest -q
python -m pytest -q tests/test_parser_checker.py
python -m nornyx.cli --help
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli profiles
python scripts\dev\run_quality.py --profile fast
python scripts\dev\run_quality.py --profile standard
python scripts\dev\audit_pmo_status.py
python scripts\dev\check_triage_candidates.py
python scripts\dev\check_requirement_triage.py
python scripts\dev\score_evidence.py docs\qa\evidence\GOAL-000
```

## Ask before running

```text
network calls
package installs
large file deletion
git push
git reset --hard
deployment
publishing
production data access
```

## Denied by default

```text
secret access
credential printing
production writes
automatic PR merge
automatic GitHub token use
unapproved connector calls
```
