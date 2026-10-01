# Data generation performance

Capture remains synchronized at a 50 ms simulation step. Reported wall-clock throughput depends on camera count, rendering settings, scene content, ROS publication and disk recording. A 20 Hz simulated sensor cadence does not imply 20 recorded frames per real second.

The September 15 optimization preserves sensor settings and data formats:

- Signal auditing rejects frames with no entry-boundary crossing before doing route matching; all turn connectors still participate when resolving a crossing.
- Parking occupancy rejects separated bounding boxes before the exact polygon and height tests.
- Recovery checkpoints copy completed state on the capture thread and serialize/write using one bounded background worker. Only atomically published checkpoints are advertised. Write errors are reported on the owner thread, and shutdown waits for the writer.
- The frame timer includes the synchronous checkpoint work under `checkpoint_ms` and in `total_ms`.

A moving-scene test with six 640 x 360 RGB cameras, one legacy 32-channel LiDAR (80 m, 200,000 points/s), one GPU worker, raw capture and ROS bag recording measured 1.59 sustained frames/s before the changes and approximately 1.73–1.86 afterwards. Scene content varied as the vehicle moved, so this is an observed workflow result, not a fixed-scene rendering benchmark. The original run included a 5.26-second checkpoint stall; retained optimized runs had no comparable stall.

GPU sensor completion was the main remaining cost with one worker. After additional GPU use was authorized, a separate rainy-scene comparison recorded at least 60 frames per worker count with raw files and ROS bags enabled:

| GPU workers | Complete recorded frames/s |
|---|---:|
| 1 | 3.54 |
| 2 | 4.57 |
| 3 | 4.67 |
| 4 | 4.15 |

The existing automatic-allocation policy selects two workers: the fewest within 10% of the lowest mean frame time. Its measured choice is stored in `data/gpu-benchmarks.json`, keyed by renderer version, sensor loadout, map, weather and actor models. The two-worker result is about 29% faster than the one-worker rainy-scene sample; three workers improved throughput by only about 2% over two. These are evolving-scene measurements, not deterministic replays. The earlier clear-weather numbers should not be combined with this table to calculate a speedup.

Two longer 121-frame recordings after a fresh automatic startup measured 2.61 and 3.66 complete frames/s. The first included an 11.12-second world-tick delay and a 3.96-second ROS-stage delay. The repeat had normal world-tick timing but another roughly four-second ROS-stage delay. Thus 4.57 frames/s describes the short comparison window, not guaranteed sustained throughput. The remaining intermittent world and ROS delays are not eliminated by adding GPU workers. Both longer recordings passed complete raw-data/ROS comparisons for all 847 sensor samples each.

The six 640 x 360 cameras and the 32-channel / 80 m / 200,000 points/s LiDAR retain their attributes, mounts and simulation cadence.

Multi-worker testing also exposed intermittent first-frame subscription timeouts. Startup now observes actual deliveries instead of assuming a fixed 200 ms sleep is sufficient. It lets workers catch up to each startup frame before advancing again, discarding initialization samples while keeping the existing queues bounded. This prevents fast cameras from filling their queues while another worker initializes. A 90-second deadline and shutdown cancellation remain enforced. The subsequent 30-frame camera warmup still requires matching frames and timestamps, and normal recording still fails on missing frames or queue overflow.

A native ray-before-camera scheduling experiment reduced throughput in paired off/on/on/off tests and was reverted. The dispatcher deliberately excludes scene-capture views; changing sensor order alone does not let rays consume their render passes.
