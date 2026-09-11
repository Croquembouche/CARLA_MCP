# Traffic authoring in CARLA

Open **Plans** in the workspace navigation. Its four sections author behavior on the loaded map. Lane and road geometry remain read-only.

## Signals

Choose an intersection and select a phase in the sequence. Set its name and duration, then select each approach's **Left**, **Through**, and **Right** indication:

- **Protected** gives that movement priority.
- **Unprotected · yield** uses a flashing yellow turn arrow and yields to conflicting traffic and pedestrians.
- **Stop** closes the movement with red.
- **Off · closed** turns off the indication and keeps that movement closed to Traffic Manager.

Unsupported movements are unavailable. Yellow and all-red clearance have separate duration controls. Conflicting protected movements are highlighted before Apply and rejected by the server. Add, duplicate, reorder, or delete phases; preview the chosen phase's paths on either map. Preview changes no live signals.

**Apply to simulator** queues the complete plan. The current clearance finishes before the replacement becomes active. While paused, use Run or Step to advance clearance. Hold/current-phase controls are under Live cycle controls. Drafts survive browser refresh and group switching. Saved named signal plans stay in the current browser; export/import JSON to share them. OpenDRIVE signal identities allow import when actor IDs change.

## Vehicle flows

Specify a model, spawn and destination points, start time, departure interval, and count. Map Spawn/Destination picking can fill these point choices. Every departure uses CARLA Traffic Manager. An occupied spawn retries once per simulation second for up to 10 seconds; failed or skipped departures appear in the execution log. A flow can remove its own vehicles after arrival. The existing 100-managed-actor limit bounds concurrent load.

## Timeline

Add named events with times relative to arming the schedule:

- Spawn a background vehicle with a destination.
- Spawn a pedestrian between navigation points.
- Change a vehicle's destination, referring either to an existing actor or a named vehicle-spawn event.
- Apply clear, overcast, rain, sunset, or night weather.
- Select and hold a signal phase, hold the current phase, or resume its cycle.

Named destination events must follow their spawn. Events with the same time execute in their saved order. Event times use the fixed 0.05-second simulation clock; actions become visible on the first due frame. Pedestrian controllers begin after their actor has replicated to the next frame.

Save the schedule to the server, then **Arm schedule** while paused. Press **Run** or **Step** to execute it. You may start recording after arming; scheduled actor/state changes are captured alongside the original ego sensor data. Pausing freezes schedule time. Stopping the schedule cancels future actions and departures; actors already spawned remain in the scene.

The server saves the current schedule in `data/authoring-plan.json` and exposes it to other connected computers. It starts disarmed after reconnect. Existing-actor references must still be valid when armed. Browser drafts and JSON import/export support preparing and sharing schedules. Pedestrian point catalogs must match when importing a schedule that uses them.

## Network

Enable a movement plan at every intersection before selecting a network strategy.

- **Independent fixed cycles:** each intersection follows its own phase durations.
- **Coordinated fixed cycles:** choose a common cycle long enough for every plan and its clearances, then set a first-phase offset per group. The controller establishes a common simulation-time epoch. Spare cycle time stays all red. An occupied junction can delay release; following cycle starts align to the common schedule again.
- **Adaptive vehicle demand:** approaching vehicles are detected on the stop waypoint's road and lane, within a configurable distance. Detectors update every 0.5 simulation seconds. A green ends after the minimum and a sufficient vehicle gap, or at the maximum. This strategy has variable cycle lengths and does not use fixed offsets.

Switch to Independent before applying individual plan edits. Manually holding or selecting a signal phase also returns the network to independent operation. Import/export timing JSON to reuse network settings. Scenario configuration export includes the current network and schedule settings.

## API and recording

Existing same-origin and `X-Control-Client: carla-control-center` requirements apply. Commands use `POST /api/command/{action}`:

| Action | Payload |
| --- | --- |
| `movement-program` | `group_id`, `operation`, `phases`, `yellow_time`, `all_red_time` |
| `authoring-configure` | `config: {flows: [...], events: [...]}` |
| `authoring-start` / `authoring-stop` | `{}` |
| `network-timing` | `mode` plus coordinated `cycle_time`/`offsets`, or adaptive `min_green`/`max_green`/`gap`/`distance` |

`/api/status` includes `authoring` execution state and `network_timing` detector/coordination state. These are included in recorded JSON frames. The existing ROS bag records ego sensors, odometry, clock, transforms, and traffic-signal indications. External ego planners retain control of their vehicles and must consume signal indications themselves.

These are CARLA-native authoring and traffic-control workflows. They do not import RoadRunner projects, edit lanes, or launch SUMO co-simulation. The interface follows the phase-authoring concepts described in [RoadRunner's signal tools](https://www.mathworks.com/help/roadrunner/ug/create-traffic-signals-at-junctions.html) and the fixed/actuated distinction in [SUMO's traffic-light documentation](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html).
