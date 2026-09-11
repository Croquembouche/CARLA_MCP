# CARLA Control Center — MCP server and WebUI capability guide

This server lets an MCP client inspect and control **the same live simulator as the WebUI**. It connects to the existing HTTP API; it never imports CARLA, owns another world, or advances a separate clock. The WebUI remains usable while MCP is connected. This guide covers the current interface, including the standalone parking survey, and distinguishes simulator operations from browser presentation controls.

Implementation: `mcp_bridge/server.py`; tool schemas: `mcp_bridge/catalog.py`; launcher: `run-mcp.sh`. The machine-readable schemas and examples are available through `carla_capabilities` and `carla://capabilities`. The complete generated tool reference is [mcp-tools.md](mcp-tools.md). Examples use placeholder actor/group/sensor IDs and coordinates: discover current values before submitting a mutation.

## Connect

### Local stdio (recommended for a client on the simulator host)

Install the adapter using [the setup guide](https://github.com/Croquembouche/CARLA_MCP/blob/main/docs/SETUP.md) first. Replace the absolute launcher path if you used an MCP-only checkout outside `/mnt/simulations/control-center`. Configure an MCP client with:

```json
{
  "mcpServers": {
    "carla": {
      "command": "/mnt/simulations/control-center/run-mcp.sh",
      "args": [],
      "env": {
        "CARLA_WEBUI_URL": "http://127.0.0.1:8095",
        "CARLA_WEBUI_PUBLIC_URL": "http://127.0.0.1:8095"
      }
    }
  }
}
```

`mcpServers` is a common client configuration shape; clients with a different settings format need the same command, arguments and environment. The process writes only MCP protocol messages to stdout; diagnostics go to stderr. No ROS environment or GPU access is needed by the adapter.

### Streamable HTTP

The supplied full-stack user-service template is `carla-mcp.service`, bound to **127.0.0.1:8096**. Its MCP endpoint is **http://127.0.0.1:8096/mcp**, using stateless Streamable HTTP with JSON responses. `/health` describes the adapter itself; use `carla_status` to check CARLA. An HTTP GET in a normal browser is not an MCP initialization request.

```bash
systemctl --user status carla-mcp.service
systemctl --user restart carla-mcp.service
journalctl --user -u carla-mcp.service -n 50
```

Replace `USER` and `SERVER_IP` in the SSH examples with the server login and address. For another computer, forward this port over SSH and configure that computer's MCP client with `http://127.0.0.1:8096/mcp`:

```bash
ssh -N -L 8096:127.0.0.1:8096 USER@SERVER_IP
```

Alternatively, a remote-capable stdio client can launch:

```json
{
  "mcpServers": {
    "carla": {
      "command": "ssh",
      "args": ["-T", "USER@SERVER_IP", "env", "CARLA_WEBUI_PUBLIC_URL=http://SERVER_IP:8095", "/mnt/simulations/control-center/run-mcp.sh"]
    }
  }
}
```

SSH authentication is configured by the user. The installed service does not open a new unauthenticated LAN control port. Direct LAN hosting is supported by `run-mcp.sh --transport streamable-http --host SERVER_IP --port 8096`, but requires `CARLA_MCP_TOKEN` and clients supplying `Authorization: Bearer <token>`. Use HTTPS at a trusted reverse proxy or an SSH tunnel when credentials cross a network. Static bearer tokens are preconfigured credentials, not OAuth discovery; clients that require OAuth should use the SSH/local transport instead. Non-loopback startup without a token fails. For a proxy or wildcard bind, set `CARLA_MCP_ALLOWED_HOSTS` to comma-separated exact external `host:port` values. Browser Origin requests are rejected. The existing WebUI's access model is unchanged.

Environment:

| Variable | Default | Purpose |
|---|---|---|
| `CARLA_WEBUI_URL` | `http://127.0.0.1:8095` | Fixed upstream API; callers cannot supply arbitrary URLs. |
| `CARLA_WEBUI_PUBLIC_URL` | Same as upstream | Reachable links for downloads/mesh manifests. Set this to a WebUI address reachable from the MCP client when using remote downloads. |
| `CARLA_MCP_TIMEOUT` | `1800` seconds | Long operation read timeout; connect timeout is 5 seconds. Configure a corresponding timeout in the MCP client. |
| `CARLA_MCP_TOKEN` | Unset | Optional loopback / required non-loopback static bearer credential. |
| `CARLA_MCP_ALLOWED_HOSTS` | Empty | Extra exact HTTP Host values for proxies; no permissive wildcard default. |

Install from the pinned, separate environment without changing CARLA's dependencies:

```bash
cd /mnt/simulations/control-center
bash scripts/setup-python.sh mcp
./run-mcp.sh --transport streamable-http
```

The adapter uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0); protocol implementation and transport validation come from that SDK. The bridge has no automatic command retries and no background preview subscriptions.

## Operating rules and coordinates

1. Read `carla_status` before acting. `phase`, `running`, `mode`, `error`, `recording`, `camera_warmup`, `recovery_operation`, `weather_application`, `stream_health` and GPU progress describe readiness. Starting or restarting is asynchronous; an accepted response is not proof of readiness.
2. Use `carla_catalog` for installed models and blueprint attributes. Use `carla_inspect` for small subsets of status/map data; a full map can be several megabytes. Actor, sensor and signal IDs can change after reload/recovery. Do not reuse old IDs blindly.
3. CARLA coordinates are **metres, left-handed, +X forward, +Y right, +Z up**. Rotations are degrees. World points have `x,y` and preferably `z`; sensor mounts are relative to their ego. Traffic schedule point indices and phase indices are **zero-based**. Displayed numbers in dropdown labels may differ from phase index.
4. Pause before spawning/deleting actors, replacing sensors, restoring configuration, changing GPU policy, benchmarking, or configuring/arming schedules. These require live mode and recording stopped. `carla_pause` does not stop recording. The MCP adapter never silently pauses, stops recording, destroys actors, or retries a write to satisfy a precondition.
5. Destinations can change while running or paused, including during recording. Weather, signals and network timing work running or paused, but not during recording/native replay. They advance a synchronization frame. Camera setup advances warmup frames even when paused.
6. The server's fixed simulation step is 0.05 seconds. Wall-clock speed varies with scene and sensors. Read current performance fields; MCP latency is not the simulation-to-real-time ratio. CPU Chaos physics and GPU rendering/ray queries retain the existing implementation.
7. A timed-out or disconnected write may still execute: the WebUI shields submitted commands. Inspect live state before deciding to repeat it. Multi-step workflows are not atomic transactions. This adapter serializes its own mutations, and the WebUI serializes world commands; another client can still change the scene between calls.

## WebUI feature-to-MCP mapping

| WebUI area | Available functions | MCP equivalent |
|---|---|---|
| Top bar / Runtime | Start CARLA, connect existing, stop CARLA, Run, Pause, Step, startup/error progress, logs | `carla_start`, `carla_connect`, `carla_shutdown`, `carla_run`, `carla_pause`, `carla_step`, `carla_status`, `carla_log` |
| Runtime resources | Worker policy Auto/1/2/3/4, next-start Auto/single/four, benchmark, native sensor/frame timings, stream health, traffic-rule observations | `carla_gpu_profile`, `carla_start`, `carla_gpu_benchmark`, `carla_status` / `carla_inspect` |
| Runtime recovery | Recover saved configuration after failure | `carla_recover`; poll status through owner restart |
| Scenario | Search/list/select actors, inspect model/pose/velocity/control/light state, role and route | Read `actors` and `managed` via `carla_inspect`; selection/search are client-side |
| Scenario | Spawn ego/background/pedestrian; TM or external ego; remove actor and attached sensors | `carla_spawn`, `carla_delete_actor` |
| Scenario routes | Road/walking/parking destination, immediate replan, walking reachability and arrival radius | `carla_destination`, `carla_pedestrian_path` |
| Scenery vehicles | Convert remaining map vehicles, inspect source/substitution/failure records | `carla_convert_scene_vehicles`, status `scene_vehicles` |
| Parking | Inspect bays/exclusions/reservations/occupancy, place background car, drive ego/background into/out of a bay | `carla_map`, status `parking`, `carla_spawn` with `parking_space`, `carla_destination` |
| Parking placement utility | Move parked vehicle to road and enable TM | `carla_move_parked_to_road` (explicit repositioning) |
| Parking survey | Unobstructed pavement/curb/paint/meter review, region selection, colored individual bays | `carla_download_links` kind `parking_review`; annotations in `carla_map`; survey controls are local to that page |
| Scenario persistence | Export scenario; restore exported scenario into an empty scene | `carla_configuration`, `carla_restore_configuration`; restore also supports automation beyond the visible export button |
| Sensors | Add/remove/edit named sensors, mount/attributes, import/export loadout JSON, cabin presets, Apply | Read current sensors, edit JSON locally, submit complete list with `carla_configure_sensors` |
| Sensor views | Select ego, all/single sensor, checkboxes, Freeze, 2/5/10 fps, frame/time labels | Read sensor IDs; explicitly call `carla_sensor_preview` for requested sensors; client controls visibility and cadence |
| Sensor views | Cabin/RGB/depth/segmentation/normals/flow, lidar, radar, IMU, GNSS | `carla_sensor_preview`; lidar binary point format or raster; original bytes are in recordings |
| Weather | Clear/overcast/rain/sunset/night presets, custom fields, Reset to scene, Apply and progress | `carla_weather`; presets below; read weather to reset a local draft |
| Signals | Group/approach/head inventory, native Red/Yellow/Green/Off, Hold, Resume, individual/group timing | `carla_status` signal metadata plus `carla_traffic_light` |
| Plans → Signals | Protected/permissive turns, phase durations/clearances, add/duplicate/reorder/delete, apply, hold/select/resume/disable | Edit full phase array locally then `carla_movement_program`; read live programs in status |
| Plans → Signals | Draft phase preview, saved named plans, JSON import/export and OpenDRIVE identity mapping | Client-side draft/file workflow; submit resolved live IDs with `carla_movement_program` |
| Plans → Flows | Model, spawn/goal, start, interval, count, cleanup; save/arm/stop and log | `carla_configure_schedule`, `carla_start_schedule`, `carla_stop_schedule`; status `authoring` |
| Plans → Timeline | Spawn vehicle/pedestrian, destination, weather, signal phase/hold/resume at time | Same schedule tools and `config.events` |
| Plans → Network | Independent fixed, coordinated cycle/offsets, adaptive demand and detectors | `carla_network_timing`; status `network_timing` |
| Record controls | Record exact actor/pedestrian/light/weather states and ego sensors; optional ROS 2 bag; stop | `carla_record_start`, `carla_record_stop` |
| Sessions | Refresh/list, original recorded frame playback/scrub, original RGB preview | `carla_sessions`, `carla_session_frame`, `carla_recorded_preview`; client implements playback timer |
| Sessions | Native actor replay, autoplay/start offset, stop replay/restart clean scene | `carla_replay_native`, `carla_replay_stop`, Run/Pause/Step |
| Sessions | File list, raw sensor/bag downloads, full tar archive, verify, compare runs | `carla_session_files`, `carla_session_file`, `carla_download_links`, `carla_verify_session`, `carla_compare_sessions` |
| OpenDRIVE / 3D maps | Lane direction/turn connectivity, sidewalks/crossings, spawn points, actor heading/route, signals and parking | `carla_map`, `carla_status`, `carla_opendrive`, `carla_scene_manifest`; rendering/selection belongs to the client |
| Interface presentation | Light/dark, hide inspector, dismiss notices, map zoom/pan/fit/top-down, actor focus, layers, extent/detail, custom GLB, legends | Browser-only; no simulator mutation or remote browser-control tool. See display section. |
| Latency display | Browser-to-WebUI round trip | `carla_latency` measures bridge-to-WebUI instead; status contains simulation performance separately |

## Actors, routing and parking

Discover models and indexed points first:

```json
{"source":"map","fields":["spawn_points"],"offset":0,"limit":10}
```

Submit a point selected from that result to `carla_spawn`:

```json
{"role":"ego","model":"vehicle.lincoln.mkz_interior","planner":"tm","spawn":{"x":0,"y":0,"z":0}}
```

The coordinates above are placeholders, not a known free spawn. An omitted ego `sensors` list adds front RGB, roof LiDAR, IMU, GNSS, front radar and cabin overview. An explicit empty list intentionally adds none. Background vehicles always use Traffic Manager; pedestrians use the native walker controller. There is a 100-managed-actor limit. Spawn collisions, unsuitable pedestrian points and missing models return errors.

For a parking destination, obtain a mapped entry from map `parking_spaces`, then pass its `x,y,z` and `id` as `point.parking_space`:

```json
{"id":52,"point":{"x":8,"y":63,"z":0,"parking_space":"P024"}}
```

The backend checks vehicle fit, occupancy, obstruction and reservations. All 180 mapped Town10 bays are offered; the historical restriction filter is disabled. With TM, the vehicle drives along roads, positions itself, stops before gear changes and reverses using throttle/brake/steering. A new road or parking destination replaces its current trip immediately. An external ego receives the validated exact bay pose, heading and ID and retains responsibility for driving. `carla_control` accepts throttle [0,1], steer [-1,1], brake [0,1] and reverse; it is not a high-rate planning transport. The existing direct HTTP endpoint and ROS integration remain appropriate for control loops.

Place a stationary background vehicle directly using `carla_spawn` with `role:"background"`, `model` and `parking_space`; omit `spawn`. This placement does not perform a maneuver. `carla_move_parked_to_road` also explicitly relocates the vehicle. Use `carla_destination` for a physical departure instead.

Parking colors: **purple = open**, **grey = occupied**. There is no restricted category. Bays claimed by approaching vehicles are also displayed as occupied to prevent double assignment; inspect status `parking.reserved` for that actor. Historical rule audits remain on disk but do not withhold any mapped bay. Individual divisions on continuous curb strips are planning estimates. The parking review is static and does not show live grey occupancy; cyan markers identify meters. The overlays are separate from original OpenDRIVE. `carla_reload_parking` loads validated disk annotations; MCP does not edit lanes or survey geometry.

## Sensors and observation

`carla_configure_sensors` replaces the **whole** ego list. Preserve entries you want to keep. Names are unique lowercase identifiers matching `[a-z][a-z0-9_]{0,39}`. At most 16 sensors per ego. A sensor has `name`, `type`, `mount` and string-valued `attributes`:

```json
{"name":"front_rgb","type":"sensor.camera.rgb","mount":{"x":1.5,"z":2.2},"attributes":{"image_size_x":"1920","image_size_y":"1080","fov":"90"}}
```

Supported types: RGB, depth, semantic segmentation, instance segmentation, normals, optical flow, ray-cast LiDAR, semantic LiDAR, radar, IMU and GNSS. Read catalog `sensors` for actual blueprint attributes. Resource bounds: image width 16–1920, height 16–1080, ray points/s 1–2,000,000, channels 1–128, range 1–150 m, FOV 1–179°. Mount components must be finite with absolute value ≤360. `sensor_tick` accepts 0 or 0.05 and is normalized to 0 for every 0.05-second synchronous frame.

Default Lincoln cabin overview: mount `{x:0.55,y:0,z:1.2,yaw:180,pitch:-8,roll:0}`, 960×600, 120° FOV, `post_process_profile:"CabinObservation"`, `lens_k:"0"`, `use_ray_tracing:"false"`. It faces rearward from the center-console area. The WebUI also offers dashboard, rear-seat and three-camera coverage presets in its loadout draft. Exact current preset objects are included in the generated tool reference. Applying a list warms new cameras for 30 synchronized frames and may resize GPU workers; watch `camera_warmup` rather than repeating Apply.

For a single requested camera:

```json
{"sensor_id":53,"width":640,"after":-1}
```

For a LiDAR cloud:

```json
{"sensor_id":54,"format":"points","point_limit":4000,"after":-1}
```

`carla_sensor_preview` returns an MCP image for raster previews, JSON values/units for IMU/GNSS, or an embedded binary resource for point clouds. Metadata retains CARLA frame/timestamp, source dimensions, source/sample point counts, stride and scale. Packed LiDAR is **9 bytes per point**: three little-endian signed int16 coordinates followed by three uint8 RGB values; multiply coordinates by `x-point-scale` to get metres. It is a decimated visualization, not the original raw scan. Raster LiDAR/radar uses a sensor-relative top-down image.

`width` is bounded to 160–960 and point count to 512–12,000. `after` suppresses an identical frame (equality, not ordering). Reset it on a new scene/sensor ID. Warmup or unchanged samples return `available:false`, not a broken image. Missing/not-yet-completed samples return a tool error with the upstream explanation. A paused simulator can supply its last completed frame. Two independent preview requests may observe adjacent frames; use recordings for exact synchronized multisensor capture.

Nothing is streamed unless requested. An MCP client should only poll sensors it is actively showing, stop on hidden views and keep a bounded concurrency/cadence. The WebUI uses at most three concurrent previews and 2/5/10 fps. Lidar rotation/zoom, no-pan behavior and reset-to-vehicle-forward operate on the already-downloaded cloud locally. Hiding or freezing previews stops transfer and encoding, **not native capture**; remove a sensor from its loadout to stop capture.

## Weather presets

The WebUI presets start with this base and apply the overrides below. Submit the merged object to `carla_weather`; a partial object changes only those fields.

```json
{"cloudiness":0,"precipitation":0,"precipitation_deposits":0,"wetness":0,"wind_intensity":10,"sun_azimuth_angle":0,"sun_altitude_angle":45,"fog_density":0,"fog_distance":100}
```

| Preset | Overrides |
|---|---|
| Clear midday | cloudiness 5, sun altitude 65 |
| Overcast | cloudiness 95, sun altitude 45 |
| Wet weather | cloudiness 95, precipitation 70, deposits 60, wetness 80, sun altitude 35 |
| Golden hour | cloudiness 20, sun altitude 8, sun azimuth 270 |
| Night | cloudiness 10, sun altitude -35 |

Nine fields are visible in the form. The API additionally supports dust storm, fog falloff and scattering controls; every accepted field/range is in the tool schema. Reset to scene reloads current weather into the local draft. Apply synchronizes workers and can need subsequent frames for exposure settling. Automatic vehicle lights follow the existing simulator policy; no separate manual-light button/API is invented by this adapter.

## Signals and traffic authoring

Read `movement_programs` and traffic-light actor metadata in status to obtain groups, approach actor IDs, mapped turns, defaults, conflict data and physical heads. Multiple physical heads can belong to the same approach actor; a head does not imply an independently controlled phase.

`carla_traffic_light` supports native `state`, `timing` and `resume`. State is Red/Yellow/Green/Off. With `hold:true` (default), it freezes the intersection and sets other approaches red. With false it sets the selected state without changing the existing hold. Timing requires green/yellow/red durations 0.1–600 seconds and `scope:"signal"` or `"intersection"`. Resume resets and releases the intersection cycle.

`carla_movement_program` supports enable/update/disable/hold/resume/phase. Full phase arrays contain 1–16 entries, each with a name, duration 0.5–600 seconds and states keyed by **string approach actor ID**:

```json
{"group_id":10,"operation":"update","yellow_time":3,"all_red_time":2,"phases":[{"name":"Approach with yielding left","duration":20,"states":{"10":{"left":"Permissive","straight":"Protected","right":"Protected"}}}]}
```

Replace these IDs and movements with the loaded group's actual metadata. Unsupported movements, permissive straight and conflicting protected paths are rejected. Unspecified mapped movements stop; unsupported ones are Off. Permissive turns yield; Off is closed to TM. Clearances must be 0.5–30 seconds. Plans apply after yellow/all-red; use Run/Step to finish a pending transition while paused. Native colour controls cannot take over until movement disable clearance finishes. Selecting a phase uses zero-based `index`, usually `hold:true`. Manual hold/phase/disable switches a coordinated/adaptive network to independent operation. External planners must consume signal indications themselves.

Phase creation, duplication, reordering, deletion, draft preview and named-plan import/export happen before Apply. MCP clients implement those as JSON edits and submit the complete phase array. Browser localStorage names/drafts are not server state. Resolve saved OpenDRIVE signal identities to current actor IDs after restart.

Network timing modes:

- `independent`: each movement program follows its own durations.
- `coordinated`: `cycle_time` 1–3600 seconds; string-keyed group `offsets` between 0 and cycle−0.05. All applied plans including clearances must fit. Spare cycle stays all red; occupied junctions may delay release.
- `adaptive`: `min_green` 0.5–120, `max_green` min_green–600, `gap` 0.5–15 seconds, `distance` 5–100 m. Uses approaching vehicles on stop-waypoint lanes. Read detector counts from status.

Enable and finish applying a movement plan at every intersection before coordinated/adaptive mode. Return to independent before editing complete intersection plans.

`carla_configure_schedule` takes `{config:{flows:[],events:[]}}`. Stop schedule, pause, save the full plan, then arm and Run. Limits: 32 flows, 256 events. Every ID must be unique across both lists and match `[A-Za-z][A-Za-z0-9_-]{0,39}`. Time is relative to arming, bounded to 0–86400 seconds.

A flow specifies model, indexed spawn/destination, start, interval (1–3600 s), count (1–1000) and remove_arrived. Occupied departures retry each simulation second for up to 10 seconds; failures/skips appear in `authoring.log`. Actor cap remains 100. Events support:

| Action | Fields beyond id/time/action |
|---|---|
| `spawn_vehicle` | model, spawn, destination (road point indices) |
| `spawn_pedestrian` | model, spawn, destination (pedestrian point indices) |
| `destination` | actor (existing ID or named spawn event), destination road index |
| `weather` | preset: clear/cloudy/rain/sunset/night |
| `signal_phase` | group_id, index |
| `signal_hold`, `signal_resume` | group_id |

Named destination events must follow their spawn; ties use saved order. Save replaces the full plan. Arming establishes a new epoch. Pause freezes schedule time; Stop cancels future execution and cleanup, leaving existing actors. Scheduled events can execute during recording after being armed beforehand. These are native CARLA traffic workflows; no SUMO process, lane editing, RoadRunner project importer or general map editor is exposed.

## Recording, replay, files and restoration

`carla_record_start` defaults to `rosbag:true`. Recording arms while paused; Run/Step produces frames. It captures managed/background/pedestrian states, lights, weather, original ego samples and control events, plus native `carla.log` and optional standard rosbag2. ROS domain is 42 with `/carla/ego_ID/...`, `/clock` and `/tf`. Raw CARLA files retain left-handed coordinates; ROS messages use right-handed axes and camera optical conventions. Recording needs ROS and at least 5 GiB free. Stop finalizes the session before verification/archive download.

`carla_session_frame` uses a recording-relative **index**, not the world's frame ID. It returns original states and `sensor_files` references (type, dimensions, timestamp, pose, hash, path). `carla_recorded_preview` visualizes the first saved RGB; all camera/raw samples are reachable via files. Recorded-state playback is a client timer reading these frames; it does not require mutating CARLA. The WebUI pauses live simulation when opening that playback, but MCP frame reads do not implicitly pause.

`carla_replay_native` replaces current actors in an owned group and starts at an optional simulation-second offset. It does not reproduce bit-identical rendered sensors. `carla_replay_stop` restarts both owner and CARLA into a clean live scene; poll status while the API is temporarily unavailable. Export configuration first when it must be restored later. A regular live restart can be composed explicitly as export → stop recording if needed → shutdown → start → wait connected → empty managed scene if necessary → restore configuration. These steps intentionally are not hidden inside an ambiguous restart tool.

`carla_verify_session` checks original-data integrity and frame/timestamp consistency and saves `verification.json` in the session. `carla_compare_sessions` compares recording-relative runs, matching configured actor order. Byte fidelity and rerun agreement are distinct. `carla_session_files` lists data including `manifest.json`, `configuration.json`, `map.json`, `map.xodr`, `states.jsonl`, frame index, events, provenance, native recorder, sensor directories and ROS bag files as present.

`carla_session_file` transfers at most 2 MiB and rejects traversal paths. JSON is decoded, images are image content and other bytes are embedded resources. For large files use `carla_download_links` with `kind:"session"`, `session_id`, and optional `filename`. Without filename the URL is the streaming complete `.tar` archive. No archive bytes are downloaded into the MCP process just to return a link. Direct links use the configured public WebUI URL; this does not authenticate or change the existing WebUI.

Configuration export/restore and crash recovery restore scenario setup, not an exact mid-frame physics checkpoint. Restore requires no existing managed actors, remains paused, and may remap IDs. Native map cleanup remains in the installed cleaned Town10 package; the MCP adapter does not rewrite Unreal assets.

## Map and display features

The 2D OpenDRIVE map and optional 3D mesh show lane travel directions and connected left/straight/right turns, pedestrian navigation paths, actor routes/goals, live signal states and parking. Native OpenDRIVE is available as XML; pedestrian/parking annotations live in the JSON map. `carla_scene_manifest` returns exported scene layers and a base URL, avoiding expensive geometry downloads merely to inspect availability.

The following are **browser-local presentation**, documented here but not advertised as remote CARLA commands:

- Switch OpenDRIVE/3D; pan, cursor-centered zoom, Fit, orbit/top-down; double-click actor focus; selected-actor cone; bottom overview; lane hover information.
- Toggle signals, parking, sidewalks/crossings, spawn markers; collapse group/approach signals; show phase-path draft preview.
- Detailed versus lightweight geometry; road-network extent versus full environment; building, vegetation, street, props, water and lane-guide layers. Load/clear a local embedded `.glb` with the UI's 64 MiB / 1 million triangle limit. This does not import a new map into Unreal.
- Light/dark theme, inspector visibility, searchable actor list and selected actor; notification expansion/dismissal; saved local drafts and JSON file dialogs.
- Sensor tile selection, grid/focus, preview rate/freeze, local LiDAR rotate/zoom/reset; hiding previews is distinct from removing sensors.
- Parking survey region selection, Fit/pan/zoom, annotation toggles, meter/bay inspection and its color legend. It hides obstructing buildings/vegetation/scenery vehicles for review, without deleting them from the running world.

Vehicle symbols are rectangles with heading arrows; pedestrian symbols are smaller circles with arrows. Colors: background blue, ego green (role takes precedence), pedestrians purple, cyclists yellow, emergency red, motorcycles orange. Map footprints use actual actor extents when available. A 3D UI screenshot or changing another browser's selected tab requires separate browser automation; this MCP service returns scene data and simulator controls, not an unsolicited browser remote-control channel.

## Resources and verification

Read-only resources: `carla://status`, `carla://catalog`, `carla://map`, `carla://configuration`, `carla://sessions`, `carla://log`, `carla://opendrive`, `carla://capabilities`, `carla://documentation`. The equivalent tools work in clients that do not expose resource browsing. Use `carla_inspect` with selected fields/pagination instead of a complete map when you only need a few spawn points, bays or actors.

Tools return `structuredContent` plus compatible text; list responses are wrapped as `{items:[...]}`. Expected backend/validation failures become MCP `isError:true`, retaining HTTP status and the WebUI explanation. Resource failures use protocol resource errors. Requests are limited to 1 MiB; ordinary API responses to 16 MiB; explicit files/previews to 2 MiB. Downloads exceeding that bound belong on the direct WebUI file/archive route.

Run adapter regression tests and non-mutating live protocol acceptance:

```bash
cd /mnt/simulations/control-center
.mcp-venv/bin/python -m unittest discover -s mcp_bridge/tests -v
.mcp-venv/bin/python -m mcp_bridge.smoke
```

The test suite checks command coverage, schema validation, write forwarding, backend errors, timeout semantics, binary metadata, bounded transfer, path validation, transport access checks, resources and actual MCP initialization/discovery. Live acceptance reads the running scene and requested previews without spawning, pausing, weather changes, recording or simulator restart. It is not a claim that every destructive tool was exercised on the current scenario.
