#!/usr/bin/env bash
set -euo pipefail
export ENABLE_DEV_PMO_API=true
python apps/nornyx-dev-pmo-portal/server.py --host 127.0.0.1 --port "${NORNYX_PMO_PORTAL_PORT:-5174}"
