# 3D scene extent

In **3D scene → Scene layers & detail → Scene extent**, choose:

- **Road network area** (default): shows the rectangle surrounding the loaded OpenDRIVE lanes, including lane widths and 25 metres of surrounding scenery. Central blocks remain visible. Geometry crossing the boundary is shown as a cutaway; distant components are omitted before GPU instancing.
- **Full environment**: restores the complete exported scenery, including background buildings outside the road network.

The setting applies to detailed geometry and lightweight building boxes. It does not modify the Unreal world, native sensor output, traffic routes, or imported custom GLB files. If no valid lane geometry is available, it retains the full scene. Changing extent rebuilds the browser scene from the existing exports; compressed layer downloads are not spatially partitioned.

The detail status counts rendered mesh instances (spline sections may be merged), rather than original Unreal components. Town10's road-area scene has 7,755 mesh instances and 6,383,581 triangles, compared with 55,791 instances and 23,263,889 triangles in the full export. Every original road mesh remains loaded; the display boundary clips peripheral scenery consistently.

Verification: `node --experimental-default-type=module tests/test_scene_area.mjs` and `node tests/test_scene_geometry.mjs`. Spatial results are saved in `data/scene-area-verification.json`.
