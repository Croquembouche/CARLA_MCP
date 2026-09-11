#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-mcp}
if [[ "$mode" != mcp && "$mode" != all ]] || [[ $# -gt 1 ]]; then echo 'Usage: setup-python.sh [mcp|all]' >&2; exit 2; fi
command -v python3.10 >/dev/null || { echo 'Install Python 3.10 and python3.10-venv first' >&2; exit 1; }
unset PYTHONHOME PYTHONPATH
if [[ "$mode" == all ]]; then
 test -f /opt/ros/humble/setup.bash || { echo 'Install ROS 2 Humble using docs/SETUP.md first' >&2; exit 1; }
 command -v npm >/dev/null || { echo 'Install Node.js 20 or newer and npm first' >&2; exit 1; }
 node -e 'if (Number(process.versions.node.split(".")[0]) < 20) process.exit(1)' || { echo 'Node.js 20 or newer is required by package-lock.json' >&2; exit 1; }
 (set +u; source /opt/ros/humble/setup.bash; python3.10 -c 'import bootstrap; import carla, rclpy, rosbag2_py; from sensor_msgs.msg import Image; from nav_msgs.msg import Odometry; from tf2_msgs.msg import TFMessage') || { echo 'Build/install the custom CARLA Python API and ROS packages listed in docs/SETUP.md first' >&2; exit 1; }
fi
python3.10 -m venv .mcp-venv
.mcp-venv/bin/python -m pip install -r mcp_bridge/requirements-install.txt
.mcp-venv/bin/python -m pip check
if [[ "$mode" == all ]]; then
 python3.10 -m venv .venv
 .venv/bin/python -m pip install -r requirements-webui.txt
 npm ci
 .venv/bin/python -m pip check
 (set +u; source /opt/ros/humble/setup.bash; .venv/bin/python -c 'import app; print("WebUI imports and browser dependency paths OK")')
fi
