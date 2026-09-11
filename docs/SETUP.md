# Installation

Use the companion CARLA repository's `carlab/SETUP.md` to build the matched native simulator first. The validated layout is `/mnt/simulations/carla`, `/mnt/simulations/UnrealEngine5_carla`, `/mnt/simulations/venvs/carla`, `/mnt/simulations/bin`, and this repository at `/mnt/simulations/control-center`. Runtime process management and native fingerprint checks currently expect that layout.

Install ROS 2 Humble using its Ubuntu 22.04 instructions, including `ros-humble-rosbag2-py` and standard sensor/navigation/TF messages. Install Python 3.10 venv support, Node.js/npm, Git LFS and the native CARLA Python module into the companion build's venv. Run `scripts/setup-python.sh all`, then `./run.sh`. A full dependency inventory is retained, but system ROS packages should be installed through ROS, not pip.

The copied `systemd/*.service` files describe the workstation's native deployment. Review paths and mount prerequisites before installing them into `~/.config/systemd/user/`, then use `systemctl --user daemon-reload` and `systemctl --user enable --now carla-control-center.service carla-mcp.service`. Only the control center should tick a synchronous simulation. Do not run a second owner against the same CARLA instance.

For MCP-only use, run `scripts/setup-python.sh mcp`, set `CARLA_WEBUI_URL` to the existing server URL, then run `./run-mcp.sh`. The MCP service communicates over HTTP and does not need a local CARLA engine. See `docs/mcp.md` for client configuration and transport security.

Git LFS is required for the map/mesh/texture/recording snapshot. `git lfs pull` restores these files; `git lfs fsck` checks local LFS objects. If storage is limited, use Git LFS include/exclude patterns to omit historical recording/source-export directories, but fetch all `static/**`, map annotations and current configuration data needed by the UI. Never replace active runtime data blindly with an older snapshot.
