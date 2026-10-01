# Synchronized surround recording at 2 FPS

The October 1, 2026 production run recorded **361 synchronized frames in 125.60057 seconds**, sustaining **2.87419 complete recorded frames/s** after warm-up. Both raw files and ROS bags were enabled. The previous full-rig sample sustained 0.25257 frames/s; the measured improvement is 11.38 times. This is a workstation measurement, not a performance guarantee for other machines or scenes.

The rig used six 1280 × 800 ray-traced cameras, one physical/material LiDAR with 64 channels, 150 m range and 400,000 points/s, 29 vehicles including 28 background vehicles, four RTX 2080 Ti workers, and synchronized 0.1 s simulation steps. One background vehicle moved 44.428 m during the sample. Total frame processing averaged 342.42 ms with a 439.69 ms p95. Cold startup still has allocation and shader stalls.

## Implementation

The matched private [Unreal Engine fork](https://github.com/Croquembouche/UE5_CARLab_Source) adds separate Vulkan compute contexts and safe upload submission, invalidates deleted image layouts in every relevant context, packs ray-tracing shader records, and reuses unchanged spline ray geometry. Opt-in mapped device-local descriptor arrays and uniform uploads retain host-memory fallback. Completed device-local upload blocks are preferred over available host fallback blocks, preventing a transient startup allocation from keeping shader constants in system RAM indefinitely.

The [CARLA fork](https://github.com/Croquembouche/CARLA_CARLab) provides sensor dispatch, physical LiDAR, profiling and worker orchestration. The control center collects sensor arrivals as they finish, preserves complete frame synchronization, and uses a bounded ordered ROS bag writer with a native binding that releases Python's GIL during blocking I/O. Direct Image serialization retains the standard ROS wire format.

Workers run concurrently across four GPUs. Hardware measurements observed overlapping graphics and asynchronous compute on every GPU, without reported trace diagnostics. Paired cameras on one GPU still share an ordered graphics queue; this does not create six independent concurrent graphics queues.

## Enable the validated profile

Update and build the matched engine and CARLA repositories using the stack setup guide. Install the control-center dependencies, including the native binding, with `bash scripts/setup-python.sh all`.

For a service installation at the documented `/mnt/simulations` paths:

```bash
mkdir -p "$HOME/.config/systemd/user/carla-control-center.service.d"
cp systemd/carla-control-center.service.d/surround-2fps.conf \
  "$HOME/.config/systemd/user/carla-control-center.service.d/"
systemctl --user daemon-reload
systemctl --user restart carla-control-center.service
```

Save the current scene before restarting its owner service. For foreground use, export the variables from the supplied profile before starting `run.sh`. The renderer flags must be present before Vulkan device creation; entering equivalent console variables after startup cannot create the separate compute queue.

The profile sets scheduling weights and memory/cache policies. Select four GPU workers in the Runtime controls. Configure sensor resolution, mounts, LiDAR attributes, fixed time step, actor loadout and raw/ROS recording in the control center. A routing scale changes worker assignment weight; it does not reduce the physical LiDAR pulse rate. Startup settings are opt-in, and their defaults preserve the existing engine behavior.

## Validation

All 2,527 camera/LiDAR payloads matched their ROS messages byte for byte. Sequential frame IDs, common timestamps, complete sensor coverage, checksums and bag topic counts passed. The 65,536-ray native GPU test matched its CPU reference with zero maximum distance error, and all 17 physical fixtures passed. Six synchronized camera views were inspected. All 29 saved vehicle poses were restored after testing, and temporary raw benchmarks were removed.

The retained [validation summary](verification/surround-2fps-20261001/validation-summary.json), [recording report](verification/surround-2fps-20261001/final-production-report.json) and [hardware overlap evidence](verification/surround-2fps-20261001/production-hardware-overlap.json) describe the measured scope and limitations. The deleted raw recordings are not included in the repository.
