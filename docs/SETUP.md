# Installation

Choose **MCP-only** to connect an MCP client to an existing WebUI server. Choose **full WebUI + MCP** to run the simulator-control application on this machine. The adapter alone does not require CARLA, ROS, Node, a GPU, or the large asset snapshot.

## MCP-only installation

These commands use Python 3.10 on Ubuntu 22.04. Install `git` and `python3.10-venv` first. Use a writable directory of your choice; the example uses your home directory. Skip LFS download for this adapter-only checkout:

```bash
mkdir -p "$HOME/src"
GIT_LFS_SKIP_SMUDGE=1 git clone --branch main https://github.com/Croquembouche/CARLA_MCP.git "$HOME/src/CARLA_MCP"
cd "$HOME/src/CARLA_MCP"
bash scripts/setup-python.sh mcp
export CARLA_WEBUI_URL=http://127.0.0.1:8095
./run-mcp.sh
```

Replace `CARLA_WEBUI_URL` with the existing WebUI server address if it is on another machine. The default transport is stdio: it waits for MCP protocol messages, so a terminal that appears idle is normal. Configure your client to launch the absolute `run-mcp.sh` path instead of typing messages into that terminal. See [the connection guide](mcp.md) for client configuration, SSH forwarding, timeout settings and optional bearer authentication.

To serve local Streamable HTTP instead:

```bash
./run-mcp.sh --transport streamable-http --host 127.0.0.1 --port 8096
```

The endpoint is `http://127.0.0.1:8096/mcp`. From another terminal, `curl -fsS http://127.0.0.1:8096/health` checks the adapter; an MCP `carla_status` request checks the upstream simulator. The native service templates below assume the full `/mnt/simulations/control-center` layout; do not copy them unchanged for a home-directory MCP-only checkout.

## Full WebUI + MCP installation

First complete the companion [CARLA stack setup](https://github.com/Croquembouche/CARLA_CARLab/blob/main/carlab/SETUP.md), including the **CarlaUnrealEditor application module** and custom Python API. The WebUI's native process management currently expects:

| Component | Required location |
|---|---|
| CARLA source/project | `/mnt/simulations/carla` |
| Matched engine | `/mnt/simulations/UnrealEngine5_carla` |
| Custom CARLA Python API | `/mnt/simulations/venvs/carla` (Python 3.10) |
| Host launchers | `/mnt/simulations/bin` |
| WebUI/MCP checkout | `/mnt/simulations/control-center` |

### ROS and Node prerequisites

Install ROS 2 Humble for Ubuntu 22.04 using [the official Debian-package instructions](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html), including their locale/repository setup and base installation. After configuring that apt repository:

```bash
sudo apt-get update
sudo apt-get install ros-humble-ros-base ros-humble-rosbag2-py \
  ros-humble-rosbag2-storage-default-plugins ros-humble-sensor-msgs \
  ros-humble-nav-msgs ros-humble-geometry-msgs ros-humble-tf2-msgs \
  ros-humble-rosgraph-msgs ros-humble-std-msgs ros-humble-builtin-interfaces \
  python3.10-venv
```

Install **Node.js 22 with npm** using [Node's official downloads](https://nodejs.org/en/download). The published lockfile's Playwright packages require Node >=20; Ubuntu 22.04's default Node package is too old. The audit used Node 22.22.3. Confirm `node --version` and `npm --version` work in your terminal. Browser clients do not need Node; it installs the server's local Three.js files and developer tools.

### Restore assets and install application dependencies

Run these commands in the checkout created by the stack guide:

```bash
cd /mnt/simulations/control-center
git lfs install --local
git lfs pull
bash scripts/setup-python.sh all
```

The helper checks Python, Node, ROS and the native CARLA binding, creates `.mcp-venv` and `.venv`, installs their selected requirements, runs `npm ci`, checks pip dependencies and imports the WebUI. It does not start CARLA. The complete `*-lock.txt`/`*.lock.txt` files are historical environment inventories that include ROS/system packages; use the helper's `requirements-webui.txt` and `mcp_bridge/requirements-install.txt`, not those full inventories as pip requirements.

### Start and verify

```bash
./run.sh
```

Keep this terminal running. In a second terminal:

```bash
curl -fsS http://127.0.0.1:8095/api/status
```

Open `http://SERVER_IP:8095/` using this machine's address. The initial simulator phase is offline; use the WebUI's Start action and wait for ready status. The browsable guide is `http://SERVER_IP:8095/mcp.html`. The WebUI binds to `0.0.0.0:8095` and expects a trusted network. Its `X-Control-Client` header is a cross-origin control check, not login authentication. The MCP HTTP transport defaults to loopback; see [mcp.md](mcp.md) before exposing it remotely.

Run only one WebUI owner per CARLA instance. Stop the foreground `run.sh` with Ctrl+C before enabling the same application as a service. `run.sh` sources ROS itself; it uses ROS domain 42 and allows network ROS traffic. No shell startup-file modification is required.

### Optional user services

For the exact full-stack paths above, install the supplied templates:

```bash
mkdir -p "$HOME/.config/systemd/user"
cp systemd/carla-control-center.service systemd/carla-mcp.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now carla-control-center.service carla-mcp.service
systemctl --user --no-pager status carla-control-center.service carla-mcp.service
curl -fsS http://127.0.0.1:8096/health
```

These templates work with a normal `/mnt/simulations` directory; it does not have to be a mountpoint. If your deployment uses a separate filesystem, configure its mount dependency before enabling services. They start at user login. To run user services before login, an administrator can explicitly enable lingering with `sudo loginctl enable-linger "$USER"`.

The MCP service uses loopback URLs by default. If a remote MCP client needs downloadable links, set `CARLA_WEBUI_PUBLIC_URL` to a WebUI address reachable from that client with `systemctl --user edit carla-mcp.service`:

```ini
[Service]
Environment=CARLA_WEBUI_PUBLIC_URL=http://SERVER_IP:8095
```

Replace `SERVER_IP`, save, then run `systemctl --user daemon-reload` and `systemctl --user restart carla-mcp.service`. For other checkout paths, change both `WorkingDirectory` and `ExecStart`; the full WebUI's native paths still require the layout above.

### Tests and data

After installation, these regression tests do not launch a simulator:

```bash
cd /mnt/simulations/control-center
source /opt/ros/humble/setup.bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/test_parking.py tests/test_parking_rules.py tests/test_parking_driving.py tests/test_scene_vehicles.py -q
.mcp-venv/bin/python -m unittest discover -s mcp_bridge/tests -v
node tests/test_parking.mjs
```

The real-server acceptance scripts create/remove actors and recordings; run them only in a dedicated scenario. Playwright browser tests additionally need a browser installed with `npx playwright install chromium`; browser installation is not required merely to serve the UI.

Git LFS stores the large map/mesh/texture/recording files. `git lfs fsck` checks the local LFS objects. A full WebUI checkout needs its `static/` assets and map/configuration data; leaving pointer text in place will break file loading. New recordings and configuration updates stay local. Preserve existing data before updating an installation; do not restore the publication snapshot over an active session.

The setup audit uses fresh application venvs and Node dependencies, the installed native CARLA/ROS libraries, and read-only checks against the running server. It does not replace the separate full native rebuild and target-machine runtime validation.
