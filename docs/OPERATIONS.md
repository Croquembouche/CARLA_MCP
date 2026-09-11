# CARLA Control Center

A separate LAN web application for the locally compiled CARLA UE5 simulator.
Designed first in `design/DESIGN.md` and `design/preview.html`, then implemented
as a FastAPI service with a browser canvas map and optional Three.js view.

Open **http://128.175.213.232:8095** or **http://10.100.100.7:8095** from a computer
that can route to that host interface. The service listens on `0.0.0.0:8095`.
Both addresses are checked locally; reachability from a particular remote network
also depends on that network's routing. No other web service was replaced.

## MCP integration

The separate MCP service exposes 49 tools and 9 resources over the current WebUI API.
Read the [complete WebUI capability guide](docs/mcp.md) and [generated tool schemas](docs/mcp-tools.md),
or open [the browsable MCP guide](http://128.175.213.232:8095/mcp.html).
Local stdio: `./run-mcp.sh`. Installed HTTP: `http://127.0.0.1:8096/mcp`
(`carla-mcp.service`); remote access uses the documented SSH tunnel. MCP never owns a second simulation clock.

## Using the interface

1. **Start simulation** launches the existing GPU-optimized CARLA primary plus
   four workers. Connect → GPU workers can select one worker for a lighter run.
   Initialization takes a few minutes. The interface shows the current status;
   Connect → Refresh startup log shows launcher progress. To use an independently
   launched server on port 2000, use Connect to existing CARLA. Do this only when
   another client is not already advancing its clock.
2. In **Scenario**, choose Ego, Background vehicle, or Pedestrian and a model
   from the connected server's blueprint dropdown. Select a spawn point and a
   destination using map clicks or the indexed spawn selectors. Vehicle points
   snap to drivable lanes; pedestrians require walkable navigation space.
3. Ego vehicles can use **Traffic Manager** or **External planning algorithm**.
   Background vehicles always use TM; pedestrians use CARLA's walker navigation.
   Vehicle destinations are expanded into road-graph paths before `set_path`.
   TM vehicles brake when they reach the destination. Select an existing actor
   to change its destination or remove it. Pause before scenario edits.
4. **Sensors** edits each ego's named loadout, mount pose, and blueprint attributes.
   Import/export JSON is available. Supported types: RGB, depth, semantic/instance
   segmentation, normals, optical flow, LiDAR, semantic LiDAR, radar, IMU and GNSS.
   The default has RGB 640×360, 32-channel 200k points/s LiDAR, radar, IMU and GNSS.
   The world step is fixed to 0.05 s; sensor_tick=0 requests every simulation
   frame without interval rounding. The controller verifies every frame.
   New blueprints are validated and their first complete sample frame is checked
   before old sensors are replaced. Applying a loadout advances setup frames
   while recording is disabled.
5. **Weather** reads the current scene and applies presets or individual values.
   Apply advances one synchronized frame, including while paused, so all GPU
   workers receive the weather before sensor capture. The local UE5 bridge drives
   the loaded sky light components using CARLA daylight curves normalized to the
   map's original light intensity, maps fog distance
   from metres to Unreal centimetres, and adjusts the cloud material extinction.
   Existing weather material/rain effects remain in the CARLA blueprint. These
   controls are visual simulation settings, not a calibrated atmospheric model.
   The header shows applied
   cloud/rain/sun values; the optional browser 3D view approximates lighting/fog.
6. **Run**, **Pause**, and **Step** control one server-owned synchronous clock.
   All browser clients share the same scenario. API requests are serialized.
7. **Record** captures actor states, traffic lights, weather and original ego
   sensor samples. Check **ROS 2 bag** to also write a standard rosbag2 directory.
   While paused, recording is armed but no frames advance; press Run or Step.
   Stop recording before editing the scenario or loadout.
8. In **Sessions**, open a recording, scrub the timeline, or play recorded data.
   This view shows original states on the map and its top-down overview. Original
   camera samples remain available in the session files and preview API.
   Download complete session streams an uncompressed `.tar` without building a
   second archive on disk. Individual manifest, recorder, map and bag files are
   also linked. **Replay actors in CARLA** is a separate native replay action, available for simulator groups started by
   this interface. Stopping native replay restarts a clean live scene because
   CARLA replica sensor routing must be reset before new capture.

## Map and optional 3D

The 2D map is derived from the loaded scene's OpenDRIVE lane network, with actor
positions, traffic light colors, routes, destinations and optional spawn points.
White arrows show actual lane travel direction. Gold junction approach arrows
show connected left, straight and right turns, derived from CARLA waypoint
connectivity. Hover over a lane in either view to read its lane ID and connected
turns. These describe the lane network, not a separate inventory of painted signs.
The footer is a top-down overview of the loaded roads, buildings, actors and
routes, drawn in the browser without another Unreal camera.

Select an actor and click **Destination** on the map toolbar to choose and
immediately apply a new goal while running or paused. Alternatively choose a
destination from the dropdown and press **Apply destination to selected actor**.
Traffic Manager receives non-junction exit-road targets, with its previous
waypoint buffer replaced; the displayed road route ends at the snapped goal.
Vehicles slow on their destination lane and stop within 3 metres of the goal.
Arrival brakes use explicit batch commands to bypass CARLA's per-object sticky
control cache, including when the same actor is assigned another trip.
Changes are blocked during recording and native replay.

The `.xodr` download contains the original map. No Lanelet2 conversion is required.

The 3D view runs on the viewing computer and automatically loads an offline
export of the current map when available. Town10HD_Opt includes actual mesh
geometry for buildings, roads/sidewalks, vegetation, signs, lamps, fences,
street furniture, and water. The package preserves repeated component placement,
bakes spline deformation, reduces dense source meshes, and shares repeated
geometry with GPU instancing and spatial culling. Surface textures are compressed
and downsampled for browser use. Lane direction/turn overlays, destinations,
routes and live traffic-light state markers remain available.

Choose **Scene detail → Lightweight map** to cancel downloads and unload the
detailed scene, returning to road strips and building bounds. Layer checkboxes
hide buildings, vegetation, street objects, other props or water independently.
Geometry is downloaded only after opening 3D. A paused, unchanged scene is not
redrawn by each status poll. The top-down footer remains a separate 2D overview.

This is a planning view of the real static map geometry, not Unreal's complete
renderer. Complex shader graphs, projected decals, animated skeletal meshes,
particles and Unreal lighting are not reproduced; live actors retain clear map
symbols. Maps without an exported package show an explicit lightweight fallback.
There is no additional live camera stream or continuous server-side rendering job.

Under **Custom scene mesh**, a local `.glb` loader also accepts embedded assets,
up to 64 MiB, one million triangles and 64 million texture pixels. GLB coordinates
are Three/glTF X = CARLA X, Y = CARLA Z, Z = CARLA Y, in metres.

To rebuild the detailed map package without changing or saving Unreal assets:

```bash
source /media/william/mist1/Simulations/env.sh
cd /mnt/simulations/control-center
# Optional: export CARLA_SCENE_MAP=/Game/Carla/Maps/AnotherMap
for script in export_scene export_scene_splines export_scene_textures; do
  "$UE5_ROOT/Engine/Binaries/Linux/UnrealEditor" \
    "$CARLA_ROOT/Unreal/CarlaUnreal/CarlaUnreal.uproject" \
    -nullrhi -nosound -unattended -run=pythonscript \
    -script="/mnt/simulations/control-center/diagnostics/$script.py" \
    -abslog="/mnt/simulations/control-center/data/$script.log"
done
.venv/bin/python scripts/build_scene_textures.py
node scripts/build_scene.mjs
node tests/test_scene_geometry.mjs
node tests/browser-scene-detail.cjs
```

The exporter uses Unreal's original source geometry and textures. Scene files in
`static/scenes/<map>/` have content hashes; the small manifest is replaced
atomically. Export diagnostics and build/texture/browser reports are in `data/`.

## Recording contents and fidelity

Sessions live in `data/recordings/SESSION_ID/` on the Simulations drive:

- `carla.log`: CARLA native recorder with additional data enabled.
- `states.jsonl` and `frames.idx`: indexed simulation-frame snapshots with actor
  identity/blueprint attributes, pose, velocity, acceleration, angular velocity,
  vehicle/walker controls, light state/timers/frozen status and scene weather.
- `sensors/ego_ID/NAME/FRAME.bin`: unmodified CARLA raw sensor bytes.
  IMU and GNSS values use JSON because their measurements have no raw byte buffer.
- Per-frame sensor records preserve frame, timestamp, capture pose, dimensions,
  attributes, LiDAR horizontal angle/channel counts, and IMU compass where present.
- `map.json`, `map.xodr`, `manifest.json`: map and scenario/loadout metadata.
- `rosbag2/metadata.yaml` and `rosbag2_0.db3`: optional ROS 2 bag.

The controller waits for every configured sensor's matching frame and timestamp.
It writes captured samples before advancing again. Disk backpressure slows the
simulation; missing sensor frames, queue overflow or write failures pause it and
mark an active recording failed. Incomplete/interrupted sessions are labeled.
The UI camera preview is a small JPEG; the recording retains original full-size
sensor bytes. There is no claim that replaying physics or regenerating GPU sensor
images gives bit-identical original sensor measurements. Use the archived samples
for exact data replay. The GPU render-versus-collision geometry limits documented
in `/media/william/mist1/Simulations/GPU-SENSORS.md` still apply.

This is a shared trusted-network workspace, with no per-user accounts or access
roles. Cross-origin browser controls are rejected; API controls require the
`X-Control-Client` header. It does not run uploaded planner code or shell commands.

## ROS 2 and external planning

ROS **Humble**, domain **42**, is isolated to this service. Sensor messages are
published while frames advance, even when bag recording is off. The bag writer
uses the exact captured samples directly, avoiding DDS recorder discovery loss.
Topics include:

- `/clock`, `/tf`
- `/carla/ego_ID/odometry`
- `/carla/ego_ID/SENSOR/image` and `/camera_info` for cameras
- `/carla/ego_ID/SENSOR/points` for LiDAR/semantic LiDAR/radar
- `/carla/ego_ID/SENSOR/data` for IMU/GNSS
- `/carla/ego_ID/SENSOR/metadata` for original frame/capture metadata, LiDAR
  channel counts, compass, and blueprint attributes (`std_msgs/msg/String` JSON)

ROS uses right-handed x forward/y left/z up; camera optical frames use x right,
y down/z forward. Raw archives retain CARLA coordinates. Radar PointCloud2 has
x/y/z, radial velocity, azimuth, altitude and depth fields; semantic LiDAR retains
uint32 object IDs and labels. Raw CARLA camera buffers use `bgra8`, including
packed depth and label encodings; optical flow uses `32FC2`. Decode CARLA packed
depth/labels as appropriate for the consuming stack. CameraInfo is an ideal
pinhole calibration; non-default lens distortion needs a matching calibration.
IMU orientation is marked unavailable; its original compass is in metadata.

On another ROS 2 computer on the same DDS-capable network:

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=42
export ROS_LOCALHOST_ONLY=0
ros2 topic list
# After downloading/extracting a complete session:
ros2 bag info /path/to/SESSION/rosbag2
ros2 bag play /path/to/SESSION/rosbag2
```

The web recording bag already contains `/clock`; use either the bag's clock topic
or the player's generated clock according to your consumer configuration, not
both clock sources at once. DDS multicast/firewall routing is separate from web
port reachability. HTTP planners can use `/api/status` to receive ego state,
destination and planned route, then send:

```python
import requests
requests.post('http://128.175.213.232:8095/api/command/control',
    headers={'X-Control-Client': 'carla-control-center'},
    json={'id': 25, 'throttle': 0.25, 'steer': 0.0, 'brake': 0.0}).raise_for_status()
```

Use the actual ego ID shown by the interface. Steering is -1..1; throttle/brake
are 0..1. The vehicle must use the External policy. A control older than one wall
second applies the brake. Run only one external controller per ego. See
`examples/external_planner.py` for a small pure-pursuit integration example;
replace its `plan()` function with your own stack. It is not a validated AV planner.
The API reference is served at `/docs`.

## Service and development

```bash
systemctl --user status carla-control-center
journalctl --user -u carla-control-center -f
systemctl --user restart carla-control-center
```

The service is enabled at user startup, with lingering already enabled on this
host. A Linux mount condition prevents launch on the wrong backing filesystem.
The web process starts independently; expensive CARLA workers start only when
requested. It owns and stops only the simulator group it creates. It restores
prior world settings when disconnecting from an existing server.

Source: `/mnt/simulations/control-center` (the same files are accessible under
`/media/william/mist1/Simulations/linux/control-center`). Backend dependencies are
in `.venv`; browser dependencies are local, so clients do not need a CDN.

```bash
cd /mnt/simulations/control-center
source /opt/ros/humble/setup.bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 .venv/bin/pytest -q tests/test_capture.py
node tests/browser.cjs
```

The real-server acceptance scripts in `tests/` create/remove test actors and
recordings; run them only in a dedicated paused scenario. Reports are in `data/`.

References: CARLA's [Traffic Manager](https://carla.readthedocs.io/en/latest/adv_traffic_manager/),
[Python API / recorder](https://carla.readthedocs.io/en/latest/python_api/),
[ROS bag writer](https://docs.ros.org/en/humble/p/rosbag2_cpp/generated/classrosbag2__cpp_1_1Writer.html),
and [Three.js GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).

The instance-segmentation camera also received the subscriber check used by the
other camera types, so headless primaries and unassigned replicas do not enqueue
image readbacks. A missing render resource is now checked before dereferencing
it. These changes are included in
`/media/william/mist1/Simulations/scripts/carla-local-changes.patch`.

## Verified deployment

The final acceptance report is `data/acceptance-report.json`. The active scene is
Town10HD_Opt with four GPU workers, paused with one ego, one background vehicle,
one pedestrian, and the five default ego sensors. These are reviewable test
actors; they can be removed from the Scenario panel.

Verified: 168 lane groups and 17 vehicle blueprints; TM route and destination
arrival/braking; external API control and its timeout brake; 50 recorded frames;
700 ROS messages across 14 topics with matching timestamps and exact camera bytes;
all 11 supported sensor formats through loadout replacement and recording;
recorded-state playback; native actor replay followed by a clean simulator restart;
desktop/mobile rendering, browser GLB loading and a complete 267-entry session tar.
The native replay/restart check was retained from the preceding successful run;
the final pass repeated the capture and browser checks after the instance-camera
and subscription-startup fixes. Six unit tests cover sensor validation, ROS
coordinate/ID preservation, indexed raw recording and archive integrity.

The main verification session is `20260907-221557-607589`. Native replay, startup and
sensor-format diagnostic logs remain available under `data/` and the parent
Simulations `logs/` directory. The final run completed without a web-service
restart or an active error. Both host URLs return the interface/status locally;
no separate physical client computer was used for the network test.


## September 8 interface and runtime fixes

The deployed follow-up is verified in `data/user-fixes-acceptance-report.json`.
It covers destination changes while running, replacement TM routes through
junctions, repeated arrival braking, actual day/night/fog camera output on all
four workers, both map views and the top-down footer. Nine focused tests pass.
Background 31 completed the second route (about 505 m) and stayed stopped within
3 m of its goal. A fresh three-frame capture contains all five ego sensors and
42 ROS messages across 14 topics, verified by reading the bag database.

The deployed state is paused Town10HD_Opt with ego 25, background 31, pedestrian
32, five ego sensors, and the user's original rainy weather restored. Refresh
existing browser tabs once to load the updated interface.

## Detailed scene verification — September 8, 2026

Town10HD_Opt now exports 57,542 visible static mesh instances from 575 mesh
assets, including 1,762 spline components with baked deformation. The published
scene contains 23,021,466 instanced triangles (reduced from 409,939,724), 211
compressed surface textures and six geometry layers. Total scene geometry and
texture transfer is 29,196,890 bytes (27.8 MiB); texture images total 29,654,016
pixels. Actual draw counts depend on the camera and enabled layers.

Geometry/coordinate/spline validation and the nine existing Python tests pass.
Desktop/mobile layout and layer switching passed before texture integration; the
final textured scene and layer controls were inspected in the in-app browser with
no warning/error logs. Lightweight mode released all 208 textures used by that
view and reduced loaded GPU geometries from 876 to 26. All 217 published geometry
and texture assets were verified over HTTP. See
`data/scene-detail-acceptance-report.json` for the combined evidence.

The native control-center service retained its existing process, and the simulator
frame, running/paused state, weather and managed actors were identical before and
after this update.

## Display preferences and latency

The header Light/Dark switch changes the interface, OpenDRIVE canvas and top-down
overview palette. The choice is stored in this browser under `carla-theme` and
applied before the stylesheet paints on reload. The default remains dark. Theme
changes do not modify CARLA weather or 3D scene illumination.

The footer displays **Server: N ms**, measuring the browser-to-web-server HTTP
round trip through completion of the existing `/api/status` JSON response. It
updates with the normal 500 ms status polling, with no additional requests. This
is not an ICMP ping or simulation frame time; it includes response transfer and
browser scheduling/decoding. Failed requests show unavailable, and a five-second
timeout releases a stalled status poll so the interface can retry.

## Traffic signal controls

Signals appear as labelled red/yellow/green icons on the OpenDRIVE and 3D maps;
the top-down overview also shows their current colours. Map markers use the
actual light-head locations where available. Click one or open **Signals** and
choose its ID. Live state, elapsed simulation time, hold status, intersection
members and OpenDRIVE ID appear in the panel.

- **Set signal state** selects Red, Yellow, Green or Off. With **Hold
  intersection** checked, the selected intersection is frozen, other signals in
  it are set red, and the chosen signal takes the requested state. Unchecked
  applies the state once without changing the existing hold/cycle mode.
- **Resume intersection cycle** resets the native intersection sequence and
  releases its hold.
- **Apply timings & resume cycle** applies green/yellow/red durations (0.1–600
  simulation seconds) to the selected signal controller or all signals in its
  intersection. It then restarts that intersection. Heads sharing a native
  controller share its timings. Red includes the controller's clearance stage;
  a signal can remain red longer while other approaches run.

Edits work while paused or running and advance one synchronized frame to publish
the change to the GPU workers. The clock advances only with simulation time.
Edits are blocked during recording or native/recorded playback. Recording states
already contain signal state, timing, elapsed time and hold status; exported
scenario configurations now include the current traffic-light snapshots too.

The API is `POST /api/command/traffic-light` with the existing
`X-Control-Client: carla-control-center` header. Payloads use integer `id` and
`operation` (`state`, `timing`, `resume`). State takes `state` and boolean `hold`;
timing takes `green_time`, `yellow_time`, `red_time` and `scope` (`signal` or
`intersection`). The response includes the updated signal and group IDs.

Our CARLA Python client adds `TrafficLight.freeze_group(bool)` using CARLA's
existing targeted server RPC. The upstream `freeze()` method keeps its original
whole-world behavior. No Unreal server rebuild was required. See
`traffic_signals.py`, `tests/test_traffic_signals.py` and
`tests/verify_signal_controls.py`. The latter intentionally changes signal states,
steps the world, records two frames and restores the tested group's timings.

Acceptance on 2026-09-08: 13 unit tests passed. Live CARLA checks exercised all
four selectable states, isolated intersection holds, timing changes, resumed
green/yellow/red cycles, and a two-frame recording with a ROS 2 bag. Browser
checks selected signals directly in both map views and applied a native timing
change through the form; light mode and the mobile controls were also checked.
The original 10/3/2-second timings were restored and every intersection released.
Evidence: `data/traffic-signals-acceptance-report.json` and
`data/signal-controls-live-report.json`.

### Compact workspace redesign (2026-09-08)

All six workspace panels and both map views were captured before revising the
interface. `static/redesign-preview.html` records the prototype; the design
decisions are in `data/ui-redesign-plan.md`.

Signals now use 8 px state dots, a selected-only label and hover details, with
12 px picking tolerance in both map views. The Signals checkbox hides the main
map overlays. The inspector can be hidden with the arrow at the map's top right;
selecting a workspace panel reopens it. Signal timings and help, scene layers,
actor creation, sensor editors and startup logs expand on demand. Sensor drafts
survive panel changes. Weather fields use two columns and identify current/custom
values separately from presets. Startup and disconnect actions are under Connect;
Run, Pause and Step remain in the header. The overview and server latency remain
visible in the footer.

The before/after gallery is `/redesign-review/index.html`. Acceptance evidence is
`data/ui-redesign-acceptance.json`. Browser checks covered marker selection,
visibility, inspector controls, sensor drafts, playback restrictions, both themes,
mobile layout and detailed/lightweight scene switching. The simulator remained
paused at frame 211 throughout this frontend-only update.

### Protected and permissive movement signals

The **Signals** inspector distinguishes junction groups, approaches (CARLA actors),
vehicle heads, pedestrian heads and push buttons. Town10's exported component
inventory identifies 43 vehicle heads, 19 pedestrian heads and 15 push buttons;
the older `get_light_boxes()` semantic grouping also includes non-vehicle hardware.
The vehicle-head inventory is matched against exact scene actor transforms.

Select an approach, open **Turn phases & timings**, and configure left, through and
right indications for every approach in that group. **Apply phase program** enables
native arrow heads. Protected is a green arrow; permissive is a flashing yellow
arrow. Permissive is available for left and right turns. Stop is red; Off is dark
and keeps that movement closed to Traffic Manager. Unsupported map movements stay
Off. Phase durations and flashing use simulation time, so Pause freezes both.

Conflicting protected paths are rejected using OpenDRIVE connector lane geometry.
Programs transition through yellow and all-red before granting another phase, and
extend all-red while a vehicle or pedestrian occupies the junction. Hold freezes
the selected movement phase; **Run & hold** requests a selected phase through the
same clearance sequence. **Use native cycle** clears the junction before restoring
the original shared-colour controller. External planners retain control of their
vehicles and must interpret the published movement indications themselves.

The native Traffic Manager identifies each vehicle's planned left, through or right
route. It stops at closed movements, permits protected entry, and checks predicted
vehicle and pedestrian paths before permissive entry. Normal collision avoidance
continues after a vehicle enters the junction. 

`POST /api/command/movement-program` accepts `group_id`, `operation`
(`enable`, `update`, `hold`, `resume`, `phase`, `disable`), and for program updates:

```json
{"group_id":8,"operation":"enable","yellow_time":3,"all_red_time":2,
 "phases":[{"name":"Permissive left / protected through","duration":15,
 "states":{"8":{"left":"Permissive","straight":"Protected"},
           "16":{"straight":"Protected"}}}]}
```

Omitted supported movements default to Stop. Invalid programs do not mutate the
simulator. `/api/status` exposes `movement_programs`, each signal's `movements`,
`movement_word` and `movement_lanes`. ROS domain 42 publishes the same states with
frame and simulation timestamps on `/carla/traffic_signals` (`std_msgs/msg/String`),
and includes them in the ROS 2 bag when recording is enabled.

The compiled Python API adds `TrafficLight.set_movement_states(uint16)` and
`get_movement_states()`. Bit 15 enables movement control; three 3-bit fields at
0/3/6 encode left/through/right (0 Stop, 1 Caution, 2 Protected, 3 Permissive,
4 Off); bit 14 is the visible half of the permissive flash. Zero restores original
head meshes. Direct native setters bypass phase-program validation; use the web
API for coordinated intersection control. Native packet 25 carries the exact
movement word to GPU replicas and recorded replay. The actor snapshot layout is
121 bytes, so server, all render workers and external Python clients must use this
matching local build. Original captured sensor files remain the source of exact
sensor replay; native rerendering is not promised to be bit-identical.

The movement material is reproducible with `diagnostics/create_signal_material.py`
through UnrealEditor-Cmd. The generator verifies all graph connections before
saving. Its deployed asset is also saved under
`/media/william/mist1/Simulations/scripts/assets/M_MovementSignal.uasset`; copy it
to `CarlaUnreal/Content/Carla/Static/TrafficSignal/` alongside the native source patch.
Returning from native replay restarts the control-center owner process and its
simulator group together, avoiding stale CARLA client threads from the old episode.

The OpenDRIVE and 3D maps use the same signal hierarchy: one **G** badge per
intersection group at overview scale. Selecting a group reveals its **A** approach
badges; the inspector names Left, Through and Right and shows each indication.
Zooming into an intersection reveals turn arrows and physical head positions.
Labels avoid overlap and connect to their actual locations with leader lines.
The **Overview** button clears the approach selection. The approach dropdown is
grouped by intersection, and phase-table columns use full direction names.

## Traffic authoring workspace

The **Plans** tab provides signal phase editing, repeated vehicle flows, scenario timelines, and coordinated/adaptive network timing. See [the traffic authoring guide](docs/traffic-authoring.md) for operation, APIs, recording behavior, and import/export. Screenshots, example files, and live-test evidence are available at `/authoring-review/index.html`.
