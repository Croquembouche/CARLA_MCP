# Simulator resource profiles

Superseded startup policy: the current default is demand-based automatic scaling, including zero render workers without GPU sensors. See [parallel-gpu-processing.md](parallel-gpu-processing.md) for the deployed policy and benchmark behavior. The measurements below document the earlier fixed one-worker optimization.

The default launcher and Control Center startup profile now use one GPU worker. The primary world uses no graphics device; the worker runs GPU camera rendering and GPU LiDAR/radar queries. Camera resolution, sensor fidelity and ray-tracing settings are unchanged. Four workers remain an explicit option for larger sensor workloads.

Each GPU worker loads another Unreal world into host RAM as well as GPU memory. On the measured Town10 setup, four workers each occupied approximately 11 GiB of proportional host memory, in addition to approximately 9.3 GiB for the primary. Reducing the worker count removes this duplication. A single worker still has a loaded scene even if there are no sensors; runtime worker creation/removal based on sensor demand is not implemented.

New ego vehicles now start with an empty sensor loadout unless their spawn configuration explicitly supplies sensors. The Sensors tab supports adding or importing a loadout. Existing saved sensor configurations remain valid and are preserved during the optimization deployment.

The Connect tab distinguishes the active worker/sensor count from the GPU profile selected for the next startup. Changing the worker count requires a scene restart.

The controller now removes stale managed references when Traffic Manager or another simulator operation destroys an actor. It also exports actor poses from the last published state snapshot, so a removed native handle cannot prevent configuration export. Light and sign ignore percentages are explicitly set to zero for managed vehicles when they are spawned.

Validation includes single-worker sensor capture, empty default ego loadouts, removed-actor cleanup, a full mapped-movement stop audit, and protected/permissive driving checks. Live measurements and reports are stored under `data/`.

The stop audit covers all 34 mapped movements across 15 signal approaches. Entry is checked against the target junction ID: five test starts are inside a different upstream junction, which vehicles must be allowed to clear. Separate driving tests cover protected left/right entry and permissive left/right yielding and release. These are controlled checks, not a claim that every possible traffic interaction has been validated.

Measured after deployment and restoring all five ego sensors: host used memory 27.2 GiB (previously approximately 60 GiB); Unreal proportional memory 21.39 GiB (previously 54.36 GiB), saving 32.98 GiB. Twenty synchronized frames completed without sensor frame/timestamp errors. Results: `data/resource-optimization-acceptance.json`. One worker offers less parallel sensor capacity than four; the high-demand profile remains available without changing sensor quality settings.
