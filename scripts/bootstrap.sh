#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
nornyx check examples/governed_delivery_control_plane.nyx
pytest
