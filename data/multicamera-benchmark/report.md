# Seven-camera CARLA resource benchmark

Date: 2026-09-10. Hardware: four RTX 2080 Ti cards, each with 11 GiB VRAM; Xeon E5-2690 v4 with 28 logical CPUs; approximately 125 GiB RAM.

## Loadout and method

- Seven RGB cameras: six exterior views at yaw 0, 60, 120, 180, -120 and -60 degrees, plus the existing center-console cabin camera. All seven use the selected resolution together.
- Four other sensors remain active: roof LiDAR (32 channels, 80 m, 200,000 points/s), front radar, IMU and GNSS.
- Same Town10 nighttime scene, 31 managed actors, original weather and destinations. Four GPU workers remain active.
- Each case ran for 90 seconds after a 30-frame warm-up, following the existing controller camera warm-up. Completed frames require all eleven sensor samples to match.
- High and Epic use effective runtime quality overrides recorded in high-settings.json and epic-settings.json. High retains the current 2000 MB texture pool; Epic uses 4000 MB. Forced camera ray-traced lighting remains disabled; GPU LiDAR/radar remain enabled with external-query bounds.
- All seven camera previews are requested throughout the run, compressed and capped at 960 pixels wide. Actual camera generation is full 1280 x 720 or 1920 x 1080.
- Two temporary 16 x 16 camera streams retain the worker pool between tests while old HD streams are released. Temporary streams are absent during measurements. This avoids loading two full multicamera configurations simultaneously.
- GPU resource measurements include the entire GPU, while CPU and RAM refer to the CARLA service cgroup. GPU power is not whole-machine wall power. One CPU equivalent means one continuously occupied logical CPU.

## Results

| Case | Completed frames | Frames/s | Median / p95 frame ms | Mean / peak service RAM GiB | Peak / settled peak VRAM GiB | Mean / peak total GPU W | CPU equivalents |
|---|---:|---:|---:|---:|---:|---:|---:|
| high-720p | 344 | 3.85 | 247.9 / 261.0 | 54.75 / 54.87 | 10.14 / 9.26 | 547.5 / 703.2 | 9.29 |
| epic-720p | 340 | 3.78 | 252.3 / 266.0 | 54.76 / 54.78 | 9.52 / 9.21 | 575.2 / 681.5 | 9.23 |
| high-1080p | 227 | 2.58 | 357.4 / 388.4 | 55.01 / 55.09 | 10.16 / 9.94 | 532.3 / 696.0 | 8.89 |
| epic-1080p | 238 | 2.69 | 342.5 / 386.3 | 54.99 / 55.02 | 10.20 / 9.90 | 565.9 / 697.9 | 8.86 |

Peak VRAM is the maximum on any single GPU within the measured window; settled peak uses samples after its first 30 seconds. Allocation/cache history and sensor routing vary, so differences such as High having a higher initial peak than Epic are not evidence that High inherently requires more VRAM.

## Interpretation and limits

All four cases completed with eleven synchronized sensor streams and without an out-of-memory failure or sensor timeout. Seven-camera 720p delivered about 3.8 simulation frames/s; 1080p delivered about 2.6-2.7. System RAM was approximately 55 GiB in all cases. The bottleneck is not represented by RAM capacity alone: render/readback time increases and the busiest GPU approaches its 11 GiB VRAM capacity.

These are short live-scene tests rather than repeated deterministic trials. The small High/Epic FPS difference at a given resolution is insufficient to rank them reliably; worker assignment and cached resources varied. The initial VRAM peaks also include resources still retiring after configuration warm-up.

The maximum observed frame-gap field in raw JSON is the interval between polling observations, including seven sequential preview downloads. It is not a direct measure of a simulator freeze.

This test retains the optimized GPU sensor rendering path. It does not enable the unrestricted Cinematic/full-camera-ray-tracing configuration that failed the earlier GPU-memory test.

The original scene, two-camera loadout, quality settings and running state are restored after the experiment. final-restored-status.json contains the final verification.

Raw evidence: summary.json, per-case JSON samples and configuration files, continuous-resources.jsonl, per-case preview JPEGs, and run.log.
