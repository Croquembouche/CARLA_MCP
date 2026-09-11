# Reliability, navigation, validation and profiling

This deployment keeps CARLA's Traffic Manager and single-user operation. It adds no SUMO service.

## GPU traversal

The hardware ray shader filters candidate intersections in one traversal using FORCE_NON_OPAQUE and the existing collision-component/ignored-actor table. The old restart-at-next-float loop could exhaust 256 iterations. The new implementation has no retry cap and does not discard valid returns or switch to CPU tracing. A 300-excluded-box test compares 65,536 rays with Chaos for hit/miss, distance, normal and actor identity. Its current result is in data/reliability-gpu-selftest.log.

Native profiling records GPU timestamp durations for ray dispatch and camera buffer copies, plus host-side queue/readback/conversion measurements. These metrics are different: ray GPU duration is actual timestamp-query time; readback readiness includes scheduling and synchronization. Camera render-pass costs can be inspected with Unreal's existing GPU trace events; the new camera copy metric is not camera rendering time. No synchronous timing query waits were introduced.

## Pedestrians

The native client exposes WalkerAIController.get_navigation_path(destination). It uses the agent's navigation filter, projects both endpoints onto the navigation mesh, and rejects disconnected, partial, truncated, or out-of-node paths. The web map shows its returned path. Pedestrian goals default to a 0.75 m arrival radius, configurable from 0.25–3 m. Explicit native walker destinations no longer switch to random goals on arrival or unblock timeout. Pedestrian crossing checks recognize custom movement words instead of treating the native red fallback as permission to cross.

## Traffic behavior

A native permissive-left check gives opposing protected through traffic in the same junction priority even while stopped at its newly green approach. The motion predictor allows for acceleration of protected traffic. The live regression script tests red stop, protected entry, permissive yielding, collision events and pedestrian crossing release. Movement-program tests cover conflicting protection, yellow/all-red intervals and occupied-junction clearance.

The runtime observer detects movement-entry crossings and conflicting protected programs. It selects the planned movement before testing its boundary, suppressing duplicate entries caused by slightly offset connectors. This is an observation tool, not a formal certificate of all traffic behavior. It does not establish yielding correctness without interaction tests.

## Capture and comparison

Each new session stores immutable configuration, map, native-client/source fingerprints, seeds, mounts and intrinsics, successful control-command events, per-sample SHA256 values and an end-of-recording integrity seal. The frame index commits after the state row is written. Closing reports verification results; Sessions > Verify recorded data recomputes hashes and checks frame coverage, sensor coverage, timestamps, SQLite consistency and ROS topic counts. Legacy/interrupted sessions without a complete seal are labeled partial.

Sessions > Compare recorded runs reports position maximum/RMS error, yaw error, velocity error, time alignment, signal-state differences and sensor-payload differences. It streams the input frames and aligns recording-relative frames and configured actor order across different actor IDs. Comparison rejects a passing trajectory result when either recording fails integrity checks. Stored-data integrity and agreement between two simulation runs are separate results. Native replay includes the final sample interval and holds the recorded endpoint instead of automatically re-enabling vehicle physics. Stop replay and restart the scene before returning to live driving. It still does not promise identical regenerated camera pixels. The live replay regression compares every recorded actor pose and traffic-light state against native replay at matching relative frames.

## Worker recovery

A separate watchdog detects an owned worker's exit while the controller is waiting for a frame. It pauses the displayed run, identifies the failed worker and last delivered frame, and exposes Recover saved scene. Recovery restarts the owned simulator and restores a periodically saved configuration. It is not an exact physics checkpoint: actor IDs, random-generator progression, signal-clock phase and simulation time may differ. Incomplete recordings keep their completed rows and failed status.

## Benchmark protocol

The interactive GPU benchmark averages three 50-frame windows per candidate, with warmup. It is explicitly an evolving-scene throughput sample. scripts/benchmark_repeated.py performs stronger comparisons using fresh CARLA/controller processes and the same saved configuration, actor order, sensor fidelity, random seeds and warmup before each trial. Each trial starts a fresh owned process and applies synchronous fixed-step settings before creating the managed actors. Initial episode time can vary with connection timing; the report includes it, and this protocol does not claim bitwise determinism. Candidate order reverses on alternate repeats. The script runs outside the web service, intentionally restarts the simulator, and leaves the supplied configuration paused after the last trial. Results are written to data/repeated-benchmark.json.

Runtime separates world update, additional sensor wait, ROS publishing, recording writes and preview encoding. It displays last-frame real-time factor, last complete sensor delivery age, and native worker timings. Paused sensor age is labeled as expected. World time includes physics and other server work; it is not a pure physics measurement.

## Live acceptance evidence (September 8, 2026)

- Native ray fixture: 65,536 rays, 32,768 hits, zero maximum distance error in the fixture, including 300 ignored box layers. `data/reliability-gpu-selftest.log`.
- Pedestrian navigation: complete navmesh route, outbound and return arrivals within the 0.75 m radius, invalid destination rejected. `data/reliability-walking-test.json`.
- Traffic: red stop, protected entry, permissive left yielding to opposing protected traffic without collision, and pedestrian crossing wait/release passed. `data/reliability-signals-live.json`.
- Four fresh-process sensor trials: one worker averaged 106.81 ms per frame; two workers averaged 137.19 ms. Each candidate ran two 60-frame trials after 20 warmup frames. These are controller pipeline times, excluding HTTP/status polling. The first two trials included signal-audit time in the old recording-write timing field; the complete-frame values remain comparable. `data/repeated-benchmark.json`.
- GPU stress: 320 additional frames with camera, LiDAR, radar, IMU and GNSS. Decoded samples contained a nonconstant 640 by 360 camera image, 8,988 finite LiDAR returns and 476 finite radar returns. `data/reliability-capture-live.json`, `data/reliability-sensor-payloads.json`.
- Complete recording: 30 frames, 150 sensor samples, 160 sealed files, and 15 ROS topics with 30 messages each passed verification. Session `20260908-231850-c8fa1b`.
- Worker exit: the failed recording preserved five complete frames. A separate abrupt-exit check detected failure in 0.292 seconds. Recovery through the web button restored three actors and five sensors, paused. `data/reliability-abrupt-fault.json`, `data/reliability-recovery-status.json`.
- Native replay initially missed the final samples (0.818 m maximum position error). After repairing the unfinished final-duration marker and endpoint handling, all 30 frames matched all three actor positions and yaw exactly, with zero light-state mismatches. This test compares poses and signals, not newly rendered pixels. `data/reliability-native-replay-before.json`, `data/reliability-native-replay.json`.
- 39 targeted Python tests pass. JavaScript restart/recovery state-machine checks and module syntax checks pass. The native Python client, CARLA server and Unreal plugin were rebuilt; the final replay repair is in the Unreal plugin.

The measured profile uses one worker for this exact loadout. Other configurations can use multiple workers, and the interactive benchmark can select a different count. No sensor resolution or ray rate was reduced. Physics remains Chaos on the CPU. The measured roughly 107 ms pipeline time for a 50 ms simulation step is below real time; the new metrics expose the remaining sensor-delivery bottleneck.

Final handoff: the original saved configuration was restored and verified in live mode, paused, with pedestrian 25, background vehicle 27 and ego vehicle 28. All five ego sensors, weather values and active signal plans match the saved configuration; projected destinations remain within 0.1 m. Automatic selection uses one renderer. The final host snapshot reported 27 GiB used and 96 GiB available RAM; the CARLA GPU was idle while paused. `data/reliability-acceptance.json` records the handoff checks. Browser checks covered native timing display, failure/recovery status, recording verification/comparison, and the restored pedestrian route (reachable with two navigation waypoints).
