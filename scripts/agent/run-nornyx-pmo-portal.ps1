$ErrorActionPreference = "Stop"
$env:ENABLE_DEV_PMO_API = "true"
if (-not $env:NORNYX_PMO_PORTAL_PORT) { $env:NORNYX_PMO_PORTAL_PORT = "5174" }
python apps/nornyx-dev-pmo-portal/server.py --host 127.0.0.1 --port $env:NORNYX_PMO_PORTAL_PORT
