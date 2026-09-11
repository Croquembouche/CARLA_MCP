#!/usr/bin/env bash
set -e
unset PYTHONHOME PYTHONPATH
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
export PYTHONNOUSERSITE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
exec .venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8095 --workers 1 --no-access-log
