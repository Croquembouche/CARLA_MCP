# Vehicles supplied by the map

On connection to a new live scene, Control Center discovers scenery tagged as
cars, trucks, buses, motorcycles or bicycles. Existing native vehicle actors
are adopted into the background-vehicle list. Static scenery vehicles are
replaced with physical CARLA vehicle actors and the original scenery is hidden.
The authored Unreal map and its original vehicle assets are not edited.

Body and glass components are grouped into one vehicle. Separate vehicles packed
into a single scenery actor are converted as one transaction: every replacement
must spawn successfully, or all replacements in that group are removed and the
original actor is restored. Instanced scenery objects retain separate identities.

Matching drivable models are preferred. Some legacy parked meshes have no UE5
vehicle blueprint; these use an available model of the same vehicle class.
The selected-actor description and the map-vehicle status report substitutions.
Missing compatible models and obstructed replacement positions remain visible
as conversion failures rather than silently removing the scenery. The retry
button processes remaining scenery vehicles without duplicating successful ones.

## Additional motorcycle presets

Four separate vehicle blueprints under `SceneControllable` reuse the original
Harley, Vespa, Yamaha and Kawasaki meshes. Their original blueprints lacked Chaos
wheel and engine configuration. The copies use four invisible wheel supports
on the existing skeleton, with reduced engine torque and motorcycle mass. These
are approximate background-traffic physics, not calibrated two-wheel dynamics.
The selected-actor inspector identifies this approximation. Their legacy animation
RPM default is set to the configured engine RPM. Native verification still observes
a divide-by-zero warning from the inherited motorcycle animation graph during
active driving. Parked actors and physics-free render replicas skip that unnecessary
Blueprint tick while retaining skeletal pose snapshots, eliminating parked log spam.
The four motorcycle presets pass driving and removal acceptance.

`diagnostics/configure_background_motorcycles.py` creates these copies and
`scripts/register_scene_vehicle_models.py` registers them only after a saved-asset
reload audit confirms their wheel and engine setup. Existing catalogue entries
are preserved. Browser meshes and textures are exported incrementally.

CARLA's `SetSimulatePhysics` and the UE5 no-op `SetWheelSteerDirection` no longer
assert that every vehicle uses `UVehicleAnimationInstance`: that unused cast
crashed legacy motorcycle animation classes. Physical state handling is retained. Before sleeping, the vehicle caches its full
physics control. Recorder/RPC reads use that retained control when live wheel
objects have been destroyed, avoiding the recorder's out-of-bounds wheel access.

Two Town10 display vehicles overlap coarse building collision. Their replacements
are constructed on a free road, frozen, and positioned at the source geometry.
They can only be activated by relocating to a checked road position. Manual
parking-bay placement continues to reject obstructions.

## Controls

- Select any background vehicle, pedestrian or ego vehicle in the actor list,
  OpenDRIVE map or 3D view. The Remove button below the actor list names that actor.
- Pause and stop recording before removal. Ego removal also destroys attached
  sensors and cleans up ROS publishers. Pedestrian removal destroys its walking
  controller. Renderer resources are reconciled after removal.
- Converted scene vehicles start parked, with handbrake applied, autopilot off
  and physics disabled. They retain their collision geometry. This avoids adding
  Traffic Manager and physics work for vehicles which have not been released.
- To drive a parked vehicle, select a Road start point and use Move to road &
  enable Traffic Manager while paused. Occupied road positions are rejected.
  Then assign a destination and Run. This explicitly relocates the vehicle; it
  does not implement an animated parking exit or an off-road parking planner.

## Rendering, persistence and replay

Scenery visibility changes are applied to the primary and GPU workers, including
workers added later. Secondary clients run in a short-lived helper process and receive primary
startup ticks while waiting for their first snapshot. Python's client holds the
GIL during `get_world`, so a thread cannot safely provide those ticks. Applied
visibility is cached per worker PID and hidden-source set. The web 3D model hides matching original vehicle mesh
instances so replacements are not displayed over duplicate body/glass geometry.
Only known vehicle mesh paths are eligible for that web-display suppression.

Configuration version 4 stores hidden source identities independently of live
actors. Removing a converted vehicle leaves its original scenery hidden, including
after configuration recovery. Source identity and substitution flags are retained
when a vehicle moves to the road. Recordings include the configuration, map and
actor state. Native replay applies the recording's scenery visibility settings.
Disconnect restores original scenery when the connected simulator remains alive.

## Verification status

Tests exercise grouping, composite rollback, model substitution, repeated
conversion, parked physics/control state, occupied road rejection, hidden-source
recovery and removal cleanup for all three actor roles. Browser inspection checks
the visible selected-actor removal control. An isolated Town10 native test converted
48 scenery vehicles with zero failures and zero parked drift across 60 ticks.
All 48 retained complete wheel configurations while asleep, and a three-frame
native recording completed successfully.
Traffic Manager drove the released car and all four motorcycle presets. Live
snapshot checks confirmed background deletion, ego plus IMU deletion and pedestrian
plus walking-controller deletion. Hidden scenery stayed hidden after removal and
retry. CARLA caches `get_actor(id)` descriptions after destruction, so the test uses
the current world snapshot and actor list as the removal authority.

See `data/scene-vehicles/native-verification.json` for native results and
`data/scene-vehicles/validation.json` for deployment evidence.

## Local runtime compatibility

The simulator launcher includes the same local EOS, Boost and Oodle library paths
as the repaired editor launcher. On this RTX 2080 Ti installation it uses Unreal's
`-SkipVulkanProfileCheck` compatibility switch: the rebuilt aggregate SM6 profile
requires features beyond these cards, while the actual Vulkan device extension
checks still run. SM6 and ray-tracing shaders remain enabled. This is a local
hardware compatibility setting, not a general recommendation to bypass device
checks on other machines. Live camera, LiDAR and radar acceptance is recorded in
the deployment report.

## Live acceptance

The saved three actors, their destinations (within 1 mm reprojection tolerance),
weather and five ego sensor configurations were restored. Town10 now has 51 managed
actors, including 48 converted map vehicles and 18 explicit model substitutions.
A temporary vehicle (82) was removed through the browser; it is not retained.
The test also verified late addition of a second GPU worker with synchronized
sensor frames. The final restored saved loadout uses automatic resource selection.

A five-frame capture with 51 managed actors, 15 traffic lights, all five ego sensors
and ROS 2 bag passed hashes, frame/timestamp coverage and bag-topic count checks.
The final RGB image was 640x360 with nontrivial image content; LiDAR had 40,587 finite
returns and radar had 2,833 finite detections in the checked frame. These are
specific acceptance measurements, not guaranteed detection rates. Test captures
are retained under `data/scene-vehicles/`, outside the user's Sessions list.

## Sidewalk scenery conversion

Scenery motorcycles and bicycles are only converted where their original position
is on a driving, bicycle, or parking lane, or inside a mapped parking bay.
Sidewalk waypoints are rejected explicitly. Decorative two-wheelers outside these
surfaces stay hidden rather than becoming collidable background vehicles. The
same exclusions are applied during configuration restoration. Town10's seven
misplaced actors were removed; the Harley inside bay P037 was retained.
The audit and cleaned configuration are in `data/sidewalk-vehicles/`.
