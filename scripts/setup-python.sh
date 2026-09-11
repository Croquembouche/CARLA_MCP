#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-mcp}
if [[ "$mode" != mcp && "$mode" != all ]]; then echo 'Usage: setup-python.sh [mcp|all]' >&2; exit 2; fi
python3.10 -m venv .mcp-venv
.mcp-venv/bin/python -m pip install -r mcp_bridge/requirements-install.txt
if [[ "$mode" == all ]]; then
 test -f /opt/ros/humble/setup.bash || { echo 'Install ROS 2 Humble first' >&2; exit 1; }
 python3.10 -m venv --system-site-packages .venv
 .venv/bin/python -m pip install -r requirements-webui.txt
 npm ci
fi
