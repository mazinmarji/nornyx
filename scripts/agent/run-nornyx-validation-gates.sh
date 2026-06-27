#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q
python -m nornyx.cli check examples/governed_delivery_control_plane.nyx
python -m nornyx.cli check examples/email_triage.nyx
python -m nornyx.cli check examples/self_healing.nyx
python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli generate examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan
