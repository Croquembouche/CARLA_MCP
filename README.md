# CARLA_MCP

CARLab's network WebUI and Model Context Protocol server for the customized CARLA UE5 simulator. The MCP bridge exposes **49 tools and 9 resources** through the same API used by the interface; it does not start a second simulation clock.

Companion repositories: [CARLA_CARLab](https://github.com/Croquembouche/CARLA_CARLab) and [UE5_CARLab](https://github.com/Croquembouche/UE5_CARLab).

## What is included

- LAN scenario control: start/stop CARLA, run/pause/step, scene recovery and visible operation status.
- OpenDRIVE and browser 3D maps, lane directions and turn markings, pedestrians, actor models and parking overlays.
- Ego/background/pedestrian spawning, immediate destination changes, actor removal, physical reverse parking and Traffic Manager road driving.
- 180 Town10 parking positions, with Open and Occupied display states; physical fit, reservation and collision checks remain active.
- Traffic-light state/cycle controls and protected/permissive movement plans, network timing and scenario authoring.
- Configurable ego sensors, front/cabin cameras, on-demand sensor previews and rotatable/zoomable LiDAR visualization.
- Weather, automatic vehicle lights, latency/resource displays, and light/dark appearance.
- State/sensor recording, ROS 2 bags, recorded-session playback and native CARLA replay.
- A complete MCP capability guide, tool schemas, examples, tests, source map/texture data and captured development/test recordings.

Read the [complete WebUI/MCP guide](docs/mcp.md), [tool schemas](docs/mcp-tools.md), [operations reference](docs/OPERATIONS.md), [parking controller notes](docs/parking-driving.md), and [setup instructions](docs/SETUP.md).

## Install and run

The full WebUI expects the matched native CARLA build, Python 3.10 and ROS 2 Humble on Ubuntu 22.04. The standalone MCP bridge can connect to an already running WebUI without importing CARLA or ROS.

Start with [docs/SETUP.md](docs/SETUP.md), which separates the two installation paths:

- **MCP-only:** clone to any writable directory (LFS downloads can be skipped), run `bash scripts/setup-python.sh mcp`, set `CARLA_WEBUI_URL`, and configure the client to launch the absolute `run-mcp.sh` path. ROS, Node and a local simulator are unnecessary.
- **Full WebUI + MCP:** finish the companion native build, install ROS 2 Humble and Node.js 22/npm, restore LFS assets, then run `bash scripts/setup-python.sh all` in `/mnt/simulations/control-center`. Start the UI with `./run.sh` and use its Start action for CARLA.

WebUI: `http://SERVER_IP:8095/`. Readiness/status: `/api/status`. Browsable MCP guide: `/mcp.html`.
For local HTTP MCP, run `./run-mcp.sh --transport streamable-http --host 127.0.0.1 --port 8096`; the protocol endpoint is `/mcp` and adapter health is `/health`.

The stdio launcher waits for MCP protocol input and does not start a WebUI by itself. Remote access, SSH forwarding, optional bearer authentication and service installation are covered by the [setup guide](docs/SETUP.md) and [MCP connection guide](docs/mcp.md). The WebUI's client header is not login authentication; deploy it on the intended trusted network.

## Data and reproducibility

`static/` includes the browser-ready meshes, textures, parking survey and actor assets. `data/` includes source geometry/textures, map annotations, saved configurations, recordings and test evidence captured for this publication. Large files are in Git LFS. The application writes new runtime data locally after cloning. Virtual environments, node_modules, caches, credentials and transient process IDs are excluded.

The pinned dependency files ending in `lock.txt` preserve the installed environment inventory, including system ROS packages; use the smaller install requirements selected by `setup-python.sh` instead of feeding those whole inventories to pip. `package-lock.json` pins browser/build dependencies.

September 11 acceptance: 76 parking/scene regression tests, two successful live Lincoln parking maneuvers (R135/R136), and 180/180 empty-road geometric paths. See [acceptance.json](data/parking-open-fix/acceptance.json). Historical evidence is not a guarantee of every scenario or every hardware configuration.

## Tests

```bash
source /opt/ros/humble/setup.bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/test_parking.py tests/test_parking_rules.py tests/test_parking_driving.py tests/test_scene_vehicles.py -q
.mcp-venv/bin/python -m unittest discover -s mcp_bridge/tests -v
node tests/test_parking.mjs
```

## License and access

This repository is public. See docs/ASSET-NOTICES.md for asset attribution. CARLA/Unreal-derived scene and vehicle assets retain their upstream licenses and notices; keep those restrictions when sharing the data. Repository ownership does not replace third-party asset licenses.

## Physical LiDAR and live weather

New ordinary LiDAR loadouts default to the generic physical profile and extended return data. The sensor editor exposes installed profiles; Sensor views supports height or intensity coloring. Scene weather can be applied while running or recording, preserving the sensor actors and recording session. Separate LiDAR noise controls have been removed. Set **Fog starts at (m)** to zero for fog surrounding the vehicle.

See [physical model and schema](docs/lidar-physical.md), [optics](docs/lidar-optics.md), and [live weather](docs/lidar-weather.md). This requires the matching rebuilt CARLA native plugin and Python wheel plus the `Content/Carla/Config/Lidar` profiles installed by the CARLA content setup. `CARLA_LIDAR_PROFILE_DIR` overrides the control center profile directory for custom installations. The generic profile is uncalibrated.
