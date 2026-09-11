# Parallel GPU acceptance

Native CARLA, UE5 Renderer and Python client changes were built and installed. The live tests completed without sensor frame/timestamp errors or service restarts on the successful run.

## Current loadout calibration

One 640×360 RGB camera, 32-channel LiDAR at 200,000 points/s, radar at 10,000 points/s, plus IMU and GNSS. Town10HD_Opt, saved rainy weather, saved vehicle models. Ten warmup and 50 measured frames per candidate; 0.05 s simulation step. Timings below measure uncapped capture including world updates, sensor waiting, ROS publishing and preview encoding.

| GPU workers | Mean frame ms | p95 frame ms | Unreal PSS GiB |
|---|---:|---:|---:|
| 1 | 84.13 | 106.53 | 21.12 |
| 2 | 81.12 | 103.55 | 32.70 |
| 3 | 85.73 | 115.94 | 43.44 |

Automatic mode chooses one worker: within 10% of the fastest measured mean, with lower memory. Two workers were about 3.6% faster than one; three did not improve throughput in this sample. This is a small workload sample, not a claim about all scenes or sensor configurations. Sensor resolution, point rates, quality and physics settings were preserved.

## Lifecycle and recording

Four simultaneous GPU streams used ports 2011/2021/2031/2041. Native logs verified distinct assigned workers and correct actor-to-local-stream mappings, including different local IDs on late joiners. IMU/GNSS stayed on the primary. A temporary second RGB camera was used to exercise the fourth GPU stream and then removed.

Ten complete recorded frames and all six sensor topics were verified in ROS bag `20260908-213728-d69810`. All 15 traffic-light actors and sensor files were present; LiDAR payloads were finite, nonempty and in range, and RGB images had valid dimensions and image content.

Removing all GPU sensors left two working CPU sensor streams and zero render workers. Unreal PSS was 9.83 GiB, versus 55.86 GiB for the four-worker test. The original five-sensor loadout and all three managed actors were restored.

Twenty Python tests pass. The native endpoint regression test accepts equal local stream IDs at different worker endpoints and unsubscribes the intended stream. The socket shutdown stress test passed 2,000 connect/stop cycles with four I/O threads. Logs and source backups are retained under data/.

Physics remains CPU Chaos with existing multithreading and fixed-step/substep behavior. Measured world update time was around 7 ms, including physics and other world/server work. No GPU physics performance claim is made.

Direct native Python clients need the rebuilt client wheel to handle worker-local stream IDs and correct unsubscribe routing. Browser and ROS consumers use the updated Control Center and do not need this client wheel.
