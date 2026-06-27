#!/usr/bin/env bash
set -euo pipefail

if [ ! -f examples/nornyx_roadmap_goals.nyx ]; then
  echo "Missing examples/nornyx_roadmap_goals.nyx"
  exit 1
fi

if [ ! -d docs/goals ]; then
  echo "Missing docs/goals"
  exit 1
fi

python -m nornyx.cli check examples/nornyx_roadmap_goals.nyx
python -m nornyx.cli goal-plan examples/nornyx_roadmap_goals.nyx --out generated/nornyx_goal_plan

echo "Nornyx goal readiness check passed"
