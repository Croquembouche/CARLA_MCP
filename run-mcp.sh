#!/usr/bin/env bash
set -euo pipefail
unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
exec .mcp-venv/bin/python -m mcp_bridge.server "$@"
