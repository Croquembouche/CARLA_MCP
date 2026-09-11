# Town10HD_Opt — cleared vehicle placements

This revision removes ten authored scenery vehicles that failed the local parking-exit planner: seven overlapped collision/clearance obstacles at their starting position and three lacked an accepted non-junction exit. Thirty-eight original vehicle placements remain. Lane geometry, traffic signals, parking bay annotations and buildings are unchanged by the cleanup script.

## Use in another CARLA UE5 installation

This is a map update for an existing compatible CARLA project, not a standalone simulator or cooked distribution. It was saved by the locally modified CARLA UE5 project using Unreal Engine 5.5.4. See `compatibility.json` for the source revision. Asset dependencies must already be installed at their original `/Game/Carla/...` paths.

1. Stop the destination simulator/editor and back up its `Content/Carla/Maps/Town10HD_Opt.umap`.
2. Copy the supplied `Content` directory into the destination `CarlaUnreal/Content`, preserving the `Carla/Maps` hierarchy.
3. Load `/Game/Carla/Maps/Town10HD_Opt`. For packaged simulators, recook/repackage the map using that project's normal build workflow; replacing an editor `.umap` does not alter an existing `.pak`.

Alternatively, keep `apply_cleanup.py` and `cleanup-manifest.json` together and run Unreal's PythonScript commandlet against the original compatible CARLA project:

```bash
/path/to/UnrealEditor /path/to/CarlaUnreal.uproject -nullrhi -nosound -unattended -run=pythonscript -script=/absolute/path/to/apply_cleanup.py
```

The script validates all ten object names, their positions, mesh asset identities and owning level before deletion. It backs up the original map beside the script, saves only the persistent Town10 level, reloads it, and verifies the resulting actor set. Reapplying to an already cleaned map is a no-op. A partial or mismatched map fails validation without saving.

## Control Center scenario

`scenario.json` preserves the active user's 41 managed actors (38 retained scenery replacements, the existing background ambulance, ego ambulance and pedestrian), five ego sensors, weather and configured destinations. Restore this with the matching Control Center version; the actor IDs may change. Actor conversion and sensor configurations are Control Center functionality and are not baked into the native map.

`control-center/map-revisions/Town10HD_Opt.json` records the approved deletions for compatible Control Center installations. The updated restore logic ignores only those deleted source identities when loading older configurations. The 3D viewer also uses those identities/poses to suppress obsolete scenery from older web geometry exports.

`apply-report.json` records the saved-map SHA-256 and before/after actor counts. `SHA256SUMS.json` covers the reusable files. The original native map backup stays locally under `backup/` and is excluded from the portable archive.
