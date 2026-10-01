# Per-town browser scenery and parking

The browser package is generated from the selected town's own Unreal level. The
export includes static meshes, instances, road markings, spline deformation,
source textures, and landscape height geometry with authored holes. Large maps
load every `Town*_Tile_*` level using `LargeMapManager.get_tile_location`, which
includes the map's tile-zero offset and reversed tile Y index. Opening only the
large map's root level exports its sky, not its scenery.

Source buffers and diagnostics live in `data/scene-sources/<town>/`. Browser
packages live in `static/scenes/<town>/`; the manifest is published atomically.
Large categories are divided into bounded chunks and the browser combines all
chunks under their category toggle. Pavement and road-marking buffers retain their exported geometry. Repeated
curb/gutter splines use a conservative browser-only simplification tolerance,
and dense vegetation receives an instance-weighted preview budget. Native CARLA
sensor rendering and the source pavement used for parking validation are unchanged. Landscapes use a simple ground material; this browser preview does not
reproduce Unreal's lighting, projected decals, or layered landscape shaders.

CPU DDS texture exports preserve opaque RGB even when unused source alpha is
zero. Unmodified textures are reused between towns through atomic cache links. CPU
texture encoding uses four worker processes, preserves the preview resolution
and quality setting, and reuses completed image files. Browser texture names include
image content, so repaired pixels cannot reuse an old texture cache entry. Triangle
winding is matched to vertex normals in both the builder and browser loader,
including previously generated packages. Non-finite UVs from native world-aligned
materials receive a finite planar fallback in the builder and loader.

Parking inventories live in `data/parking/<town>.json`. They are independently
revision-checked against the town's OpenDRIVE, scene metadata, and geometry.
Town10 retains its existing 180-position hand survey and legacy source directory.
Other towns use authored parking lanes, sufficiently wide shoulders adjoining a
sidewalk, and verified existing parked-vehicle poses. Candidate rectangles must
fit completely on native pavement and marking geometry, with at least 80 percent
base pavement. Separate painted strips can fill authored surface seams; paint
alone cannot create a parking footprint. Lane positions also fit a sampled OpenDRIVE
lane ribbon; nearest-lane point lookup alone is insufficient beside narrow
shoulders. Unpainted divisions and footprints around parked vehicles are labeled
as planning estimates, not surveyed painted stalls. Actual painted markings
remain visible in the detailed road geometry.

Overlapping candidates, pavement gaps and excessive height changes are rejected.
Corner elevations place new overlays on slopes. Native parked poses are not
extrapolated into invented rows. Towns without a verified footprint explicitly
report that limitation. Occupancy uses a spatial grid for nearby vehicle boxes and retains the same
height, polygon-overlap, and priority rules. Unchanged dropdown labels are not
rewritten every refresh. Vehicle-fit checks still apply; historical
traffic-rule restrictions do not withhold geometrically valid positions.

Rebuild with the control-center Python environment (ROS environment sourced):

```bash
source /opt/ros/humble/setup.bash
.venv/bin/python tools/build_town_scenes.py Town03_Opt
# Reuse complete native exports when only browser packing/parking changes:
.venv/bin/python tools/build_town_scenes.py --resume Town03_Opt
.venv/bin/python tools/build_town_review.py
```

Omitting town names rebuilds the other installed towns and preserves Town10.
Exports run in disposable editor commandlets and never save native assets.
Distance-field generation is disabled only for these CPU export commandlets;
runtime CARLA rendering settings are unchanged. Spline matching uses an index
instead of repeatedly scanning all scene instances. Repeated slices reuse the
same deformation frame; baked chunks use deformed positions and a vertex cap,
so components with zero transform origins cannot collapse into one huge chunk. The
landscape OBJ exporter runs last and clears static component references only in
that disposable world to avoid material baking; it does not edit saved levels.

Validation tools:

- `tools/validate_town_scenes.py`: map identity, buffer references, finite vertices,
  triangle accounting, textures and browser memory limits.
- `tools/validate_town_alignment.py <towns...>`: independent OpenDRIVE driving
  samples against native pavement/marking triangles, including elevation.
- `/town-review/`: read-only visual review of the same scene renderer and parking
  overlays without replacing the running simulator's world.
- `tests/test_town_parking.py` and `tests/test_scene_pack.mjs`: revision isolation,
  full-footprint/slope/gap checks and lossless category chunking.

A material classification or export gap can appear as an alignment miss; inspect
its saved coordinates before attributing it to the native map. Pipeline logs and
per-town reports are retained under the source directory.
