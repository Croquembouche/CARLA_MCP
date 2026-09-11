# Browser road surfaces and scene materials

The Town10 browser export now uses the source geometry of all four road and all four lane-marking meshes. The older Nanite fallback geometry omitted parts of junction asphalt and paint. The source mesh pipeline welds identical position/UV vertices and simplifies with locked borders and a small error tolerance, retaining the actual road and painted shapes. The road layer contains 323,667 rendered triangles across 400 instances.

Lane paint uses opaque, high-contrast white/yellow materials with a depth bias to prevent flickering against the asphalt. Optional OpenDRIVE lane-direction guides are more subdued and obey scene depth. Toggle them under **3D scene → Scene layers & detail → Layers → Lane direction guides**; this does not hide actual lane paint.

The material patch also repairs 16 opaque material mappings (14 source textures) that previously turned black when an unused alpha channel was premultiplied during resizing. Opaque colour is now separated from alpha before downsampling. It resolves additional native colour inputs, parked-vehicle paint with stickers, and interior textures. Interior cubemaps use a static wall-face projection in the browser, not Unreal's parallax shader. Masked textures retain cutouts across scenery categories. The browser is a lightweight preview; native lighting, shader effects and projected decals are not reproduced in full.

Source exports run in isolated Unreal commandlets and do not save native assets. Road 1 needs its unused second material slot temporarily removed in memory for GLTF export; the exporter restores that slot in a finally block. No running simulation restart is required.

Relevant tools:

- `diagnostics/export_road_source.py` and `diagnostics/export_road_one.py`: source road exports.
- `scripts/rebuild_road_layer.mjs`: weld, simplify and publish the road layer.
- `diagnostics/export_scene_material_patch.py` and `diagnostics/export_scene_cubemaps.py`: source material inputs and CPU DDS cube exports.
- `scripts/patch_scene_materials.py`: convert browser textures and publish hashed scene layers.
- `node diagnostics/check_road_coverage.mjs --junction-test`: 483 downward samples over the central hatched intersection; zero uncovered samples after the replacement.
- `node --experimental-default-type=module tests/test_scene_materials.mjs`: paint visibility, depth and alpha behavior.

The read-only `/road-review.html` page provides close views of the central, eastern and western intersections without changing the simulator.

Opaque texture repair: `diagnostics/export_dark_textures.py` exports CPU source DDS images; `python tests/test_scene_texture_assets.py` validates every published texture and verifies that repaired colours are retained.
