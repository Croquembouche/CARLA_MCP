# CARLA Control Center — interface design

Design prepared before application implementation, 2026-09-07.

## Workspace

A dark slate, restrained engineering workspace with mint accents. The central
map is the primary control surface. A narrow navigation rail switches Scenario,
Sensors, Weather, and Recordings. A right inspector changes with that selection.
A persistent header shows the loaded town, connection state, frame and simulation
time. Run/pause/step and Record controls remain visible. A bottom strip shows
the ego camera and session capture status without streaming full-resolution video.

```
┌ CARLA / CONTROL CENTER ── Town10HD ── Connected ── Start · Pause · Step ┐
│ Scenario │ OpenDRIVE / 3D   Fit · Spawn · Destination │ Vehicle        │
│ Sensors  │                                           │ Ego / Traffic  │
│ Weather  │        Road lanes, actor arrows,           │ Model dropdown │
│ Sessions │        spawn pins, route, goal             │ Planner        │
│          │                                           │ Spawn / Goal   │
│          │                                           │ Add / Update   │
├──────────┴───────────────────────────────────────────┴────────────────┤
│ Ego camera preview     Frame / sim time     ● Record   ROS 2 bag □    │
└──────────────────────────────────────────────────────────────────────┘
```

## Interaction contract

- A disconnected service is useful: Start simulation launches the configured
  four-GPU CARLA group; initialization progress and errors are explicit.
- Map defaults to local OpenDRIVE-derived lane geometry. Wheel zoom, drag pan,
  fit, labeled spawn points, actor selection and route overlays are available.
- Pick spawn or destination then click the map. Vehicle dropdown comes from the
  connected server. Background vehicles use Traffic Manager. Ego supports TM
  or an external planner via a documented control API; a stale external command
  brakes the vehicle. Route planning follows the road graph before TM set_path.
- Pedestrians have a separate spawn/destination workflow using navigation points.
- Sensor cards configure type, mount pose and blueprint attributes. Changes are
  applied while paused, with validation before replacement. Configuration can be
  exported/imported as JSON. Every attached sensor has an explicit name.
- Weather presets and numeric controls are read from/apply to the live world.
- 3D is optional and lazily loaded: road surfaces and static scene bounds plus a
  local GLB loader. No server-side live 3D video, extra UE viewport or full-map
  asset conversion. GLB has file-size and geometry limits and is rendered only
  while the 3D view is visible. Label proxy geometry honestly.
- Record starts a native CARLA recorder plus frame-aligned state and raw ego
  sensor capture. Optional ROS 2 bag writes the same captured samples as standard
  ROS messages. No silent dropping: missing samples or write failures pause the
  simulation and mark the session incomplete. ROS publishers are available to
  external planners. Topic timestamps use simulation time.
- Sessions expose exact recorded-state playback in the web map with original
  camera samples, downloadable artifacts, and native CARLA replay separately.
  Replay does not claim regenerated sensor data matches original measurements.
- Shared LAN workspace: one server owns ticking and serializes all browser
  commands. Controls show errors inline. No arbitrary shell commands or planner
  code uploads through the interface. Service remains separate from other apps.

## Acceptance

Real CARLA map and blueprint inventory; map pick and TM route; ego/background
spawn and delete; sensor configuration, camera preview, weather update; custom
planner command; synchronized recording and ROS bag readback; recorded-state
playback and native replay; browser desktop/mobile checks; LAN listener and
service restart. Archive test evidence and document any unverified constraints.
