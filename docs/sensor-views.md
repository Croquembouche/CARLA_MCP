# Live sensor views

The **Sensor views** workspace is separate from the **Sensors** loadout editor.
Choose an ego vehicle, then use All sensors, the per-sensor checkboxes, or Focus /
Single sensor. The grid fits a normal five-sensor loadout to the viewport; larger
loadouts scroll. Scrolled-out tiles do not request data. Freeze previews pauses
only browser observation. Step/Run and Record remain the simulator controls.

Preview rates are 2, 5 (default), or 10 fps, bounded by simulation delivery and
HTTP latency. Each tile shows its actual CARLA frame and simulation timestamp;
multiple live HTTP requests may observe adjacent frames. Exact synchronized
capture continues through the recorder and ROS, independently of the preview.

## Transfer and compute bounds

- The controller retains only each sensor's most recent completed sample. There
  is no eager JPEG encoding in the simulation tick and no preview-history queue.
- The browser sends requests only for active, visible tiles while the document
  is visible. It cancels in-flight requests when a tile becomes hidden, the user
  changes workspace, or previews are frozen. A request already executing on the
  server may finish encoding; there is no continuing stream or subscription.
- Status polling also stops while the browser tab is hidden and slows to 1 Hz
  in Sensor views; sensor preview cadence is independent of status polling.
- Up to three requests run concurrently. Dropped/intermediate simulation frames
  are skipped. A paused tile is fetched once and refreshed after Step.
- Camera previews are JPEG quality 72, sized to the grid (up to 640 pixels), or
  up to 960 pixels in focus view. Requests cannot exceed 960 pixels.
- LiDAR is an interactive 3D point cloud: drag to rotate, wheel/pinch or + / −
  to zoom, and Reset to restore the view. Panning is disabled and the sensor
  origin stays fixed. Rotation and zoom use the already received scan locally.
  The grid receives at most 4,000 points (36 KB); focus receives at most 12,000
  (108 KB). Each point is 6 bytes of quantized coordinates plus 3 colour bytes.
  The coordinate step is at least 1 cm and increases for scans beyond 327 m.
  Only one scan and its GPU buffers are retained per initialized tile. Rendering
  occurs on a new scan, interaction, or resize, without an idle animation loop.
- Radar remains a bounded raster top view over an 80 m radius. The footer reports
  sampled and source counts. Preview sampling never changes full recorded scans.
- IMU and GNSS send small JSON measurements with units. Depth uses a logarithmic
  0–1,000 m scale; semantic/instance images and optical flow get display colours.
- An unchanged frame produces HTTP 204; matching ETags produce HTTP 304 before
  encoding. The response cache holds at most 32 images / 8 MiB.

`GET /api/preview/{sensor_id}?width=640&after=FRAME` returns JPEG or measurement
JSON, with `X-CARLA-Frame` and `X-CARLA-Timestamp` headers. `after` is equality-based
so a new episode can have lower frame numbers. Browser state resets when the
world frame decreases or sensor configuration changes.

Configured sensors still capture in CARLA and feed ROS/recording while previews
are hidden. Visibility controls web transfer and preview encoding; it does not
change capture frequency, native image resolution, sensor ray counts or the
original recorded bytes.

## Lincoln interior cameras

New ego vehicles spawned from **Scenario → Spawn an actor** automatically include
six sensors: **front_rgb**, **roof_lidar**, **imu**, **gnss**, **front_radar**, and
**cabin_overview**. The cabin camera uses the wide cabin preset below. The server
also applies this loadout to ego spawn API requests that omit `sensors`.
Background vehicles and pedestrians receive no default sensors. Explicit custom
loadouts (including an empty list) are respected, so saved scenarios retain their
exact configured sensors on restoration.

New camera loadouts warm for 30 synchronized capture frames before preview
delivery is enabled. This allows Unreal to load view-dependent geometry and
textures and settle temporal rendering; a valid first sensor packet alone is
not sufficient. The interface shows camera warmup progress. Warmup advances
simulation time by 1.5 seconds and does not publish those frames to ROS. Sensor
editing is already restricted to paused, non-recording operation.

In **Sensor views**, uncheck **cabin_overview** to hide it and stop preview
downloads. Native capture and recording continue; remove it in **Sensors** to
stop capture. Choose **Lincoln / MKZ Interior** for the finished cabin.

For additional views, select the ego in **Sensors**, choose a cabin placement,
click **Add to loadout**, then **Apply loadout** while paused and not recording. Mount coordinates remain editable. The same three
cameras are available in `examples/lincoln-cabin-sensors.json` for Import JSON.

- Wide cabin overview: centered above the center console, facing rearward with a slight downward tilt, 120-degree field of view. The Lincoln mount is x 0.55, y 0, z 1.20 m; yaw 180, pitch -8 degrees. Driver and front passenger seating are in frame with the back row between them; front seats naturally occlude parts of the rear bench.
- Dashboard and front controls: centre cabin facing forward.
- Rear seats: rearward view from between the seating rows.
- Cabin coverage: adds all three complementary views.

All presets capture 960 × 600 pixels. No single physical camera sees through seats
or behind itself; the complementary views provide broader cabin coverage. The
finished interior asset is `vehicle.lincoln.mkz_interior`; other models need
individually calibrated interior mounts.

Cabin presets use the installed CabinObservation post-process profile for indoor
automatic exposure. Its portable copy is `examples/CabinObservation.json`; copy it
to `CarlaUnreal/Content/Carla/Config/PostProcess/` when reusing these presets on
another installation. Keep the worker policy Automatic for multi-camera coverage.

GPU workers render replicas of one scene. They do not have independent weather
presets. The sensor page displays shared scene weather, and each tile retains its
own captured frame/time. Cabin histogram auto exposure can make the interior and
sky brighter than the exterior camera; brightness alone is not a weather-state
comparison. Weather controls work while running or paused, with application
feedback identifying the completed frame. They remain disabled during recording
and replay.

Weather.cpp removes its rain and dust post-process materials from existing camera
settings before applying the new active effects. Previously, removing an effect
from the weather controller's registry left its camera copy installed, so a
rain-to-clear transition could retain droplets even after all replicas reported
zero precipitation. Other camera post-process materials are preserved.

Weather updates enable the directional sun's volumetric cloud shadows on scene
surfaces, with a 5 km local shadow extent. This allows the cloud volume to block
sunlight reaching the cabin while retaining the atmospheric sun that lights the
daytime sky. Turning the atmospheric sun intensity to zero incorrectly darkens
the sky as well, so that approach is not used. The cabin exposure profile is
preserved.

Sensor-only render workers do not draw a regular game viewport. Unreal's realtime
skylight capture explicitly skips scene-capture views, so weather updates switch
the loaded sky to an explicit capture and request it after the sky parameters are
updated. Town10's authored sky component used `SLS_SpecifiedCubemap` with no
cubemap assigned; an explicit capture also switches it to `SLS_CapturedScene`.
This refreshes the diffuse environment without adding an idle viewport render
each frame.

At 90% cloud cover and above, the weather controller also suppresses the sun's
direct surface contribution through its lighting-channel mask. This is a dense
overcast approximation; atmospheric scattering and skylight remain active.
Each sun component's original channel mask is saved and restored below that
threshold. This prevents the hard seat-shadow pattern that cloud shadows alone
did not remove in Town10. Lighting channels apply to direct surface lighting;
see the [UE5.5 API reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/Components/ULightComponent/LightingChannels?application_version=5.5).

## Native multi-camera upload memory

The Vulkan temporary upload allocator has a local UE5 source fix in
`Engine/Source/Runtime/VulkanRHI/Private/VulkanMemory.cpp`.
On the RTX 2080 Ti, CPU-mapped device memory occupies a separate 246 MiB BAR heap.
Multiple camera captures exhausted that heap, despite available ordinary VRAM.
Temporary uniform uploads now use coherent host memory when the compatible BAR
heap is smaller than 1 GiB. Larger BAR heaps keep Unreal's preferred BAR path.
This changes upload-buffer placement, not where cameras render or LiDAR/radar
ray queries execute. Cabin cameras use GPU raster rendering (`use_ray_tracing=false`) to avoid the
additional ray-traced capture memory that exceeded an 11 GiB card in testing.
Existing ego camera settings and LiDAR/radar GPU ray queries are unchanged. The native module
must be rebuilt when carrying this fix to another UE installation. A portable
patch is preserved in the private [UE5_CARLab_Source archive](https://github.com/Croquembouche/UE5_CARLab_Source/blob/main/carlab/restricted-archives/CARLA_MCP/examples/ue5-small-bar-camera-uploads.patch); Unreal source access is required.


The CARLA worker router includes a fixed per-sensor overhead in addition to pixel
or ray rate. This spreads mixed camera and ray-sensor loadouts more evenly:
low-rate LiDAR still needs acceleration structures and scene residency. The
source delta is `examples/carla-sensor-worker-overhead.patch`. This changes
assignment among existing workers; it does not force idle workers to remain on.

The native systemd service sets `LimitNOFILE=65536`. The former soft limit was
1,024; the higher limit provides headroom for the expanded Vulkan/cache workload,
which also produced a curl polling failure during stress testing.


## Acceptance evidence

- `data/sensor-view/browser-verification.json`: real five-sensor UI, focus,
  paused-frame suppression, Freeze, hidden workspace and off-screen tile checks.
- `data/sensor-view/cabin-browser-verification.json`: three simultaneous cabin
  views plus LiDAR, single view, loadout navigation, preset addition and light mode.
- `data/sensor-view/cabin-balanced-setup.log`: 60 synchronized steps with nine
  sensors, followed by previews from the same completed frame.
- `data/sensor-view/recording-verification.json`: three recorded frames,
  27 complete sensor samples, ROS topic counts and timestamps, no errors/warnings.
- Native builds: `data/sensor-view/vulkan-build.log` and
  `data/sensor-view/carla-balance-build.log`.

The temporary test Lincoln is removed after acceptance; the original 41-actor,
five-sensor scene remains paused with Automatic workers. Native actor IDs can
change after a saved-configuration restore.


## Point preview protocol and vehicle lighting

`GET /api/preview/{id}?format=points&point_limit=4000&after=FRAME` returns
`application/vnd.carla.pointcloud` for LiDAR. Each 9-byte point is little-endian
int16 X/Y/Z followed by uint8 RGB; multiply coordinates by `X-Point-Scale`.
`point_limit` is bounded to 512–12,000. Existing JPEG preview clients still work.
Frame suppression, ETags, visibility cancellation and the cache bound also apply.

Vehicle lights update automatically during live simulation. Traffic Manager
controls its active vehicles' route indicators, brakes and weather lighting.
Parked, arrived, parking-manoeuvre and external-planner vehicles use the same
dusk/heavy-rain/fog thresholds; brake, reverse and steering indicators follow
vehicle controls outside TM. Parked vehicles do not display stale brake, reverse
or turn lights. Explicit high-beam, interior and special/emergency flags are
preserved by the fallback policy. Updates are batched and sent only on changes.
The automatic policy is disabled during native replay. Integer `light_state` is
included in actor snapshots and the recorded scene states.

Saved driven vehicles restore at their saved X/Y and orientation with 20 cm
spawn clearance for road contact; they are not projected onto another lane.

During restore, vehicles remain braked and autopilot is held until all actors and
sensors are initialized. Destinations and drivers are enabled only after placement,
so a restored vehicle cannot occupy a later vehicle's saved position during warmup.

Lighting/LiDAR acceptance: `data/lighting-lidar/lighting-verification.json` checks
42 vehicles under night, day, rain and fog, plus external brake/reverse/turn lamps.
`lidar-ui-verification.json` in the same directory checks rotation, wheel/buttons,
reset, fixed origin, and zero additional preview requests during interactions.
The saved Mustang restored within 3 mm in X/Y (`restore-position-verification.json`).

## Existing ambulance ego cabin

The Ford ambulance uses a separate cabin mount (x 1.6, y -0.55, z 1.65 m,
yaw 140, pitch -20 degrees) and `AmbulanceCabinObservation` exposure profile.
This views both front seats from the front passenger side. The profile is
installed alongside `CabinObservation`; its portable copy is
`examples/AmbulanceCabinObservation.json`. Scenario spawning selects this
mount automatically for `vehicle.ambulance.ford`. Other camera presets remain
unchanged. The existing ego 28 was given this camera while keeping its five
previous sensor configurations.

## Frame delivery and sensor-only workers

A camera-only GPU worker keeps a 160 × 90 unlit maintenance viewport while a
camera has a subscriber. Its main view has lighting, shadows, post-processing,
GI and reflections disabled. This advances Unreal's scene frame and permits
renderer caches to retire; disabling the entire viewport while scene captures
continued caused camera-worker resident memory to grow during sustained runs.
External GPU ray queries remain separately enabled only for subscribed LiDAR or
radar. Camera sensor resolution and rendering quality are unchanged.

The status API reports `stream_health` with the current world/sensor/publish
stage and elapsed time. The interface displays a wait longer than two seconds
separately from HTTP server latency, retains the last complete images and clears
the wait indication as delivery resumes. A paused simulator is not labelled as
a stalled data stream. Capture still requires complete, matched samples for
recording; this change does not skip missing frames.


The native vehicle light setter repairs low/high-beam spot components when a
Blueprint requests a beam but leaves its intensity at zero. Working authored
lights are preserved. Repaired low beams use 1,200 lumens per lamp and a 60 m
attenuation radius; high beams use 1,800 lumens and 100 m. They use inverse-square
falloff and remain attached to their authored vehicle mounts. A component tag
tracks repaired lights so switching the corresponding state off also sets their
intensity to zero. The Traffic Manager and external-planner lighting policies
continue to select the actual state.

Native sensor timing samples are aggregated in memory and written by one
bounded background task. A pending write coalesces new samples rather than
queuing more disk work. On Linux with `XDG_RUNTIME_DIR`, profiles are stored in
`$XDG_RUNTIME_DIR/carla-sensor-profiles/<pid>.json`; the monitor reads this
runtime location first and supports the legacy Saved/SensorProfiles fallback.
Shutdown joins the outstanding writer. Filesystem writes no longer hold the
profiling mutex on the render or sensor-delivery threads.
