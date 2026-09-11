# Actors in the 3D map

The web map loads the installed CARLA vehicle and pedestrian meshes on demand. All 55 types in the current vehicle/walker catalog are covered. Ego and background vehicles use the same model library, selected by their CARLA blueprint ID.

- Click an actor to select it in the inspector.
- Double-click its 3D model to select it and focus the orbit camera on it. Small actors also have a 12-pixel picking tolerance in the overview.
- Double-click its inspector entry for the same camera focus.
- Only the selected actor receives the downward cone, positioned above its model. Its screen size stays small as the camera zooms. Routes remain visible, without cones at every destination.
- **Fit map** returns to the complete road-area view.

Model and texture resources are shared between actor instances. State updates reuse the loaded models and update their transforms. A removed actor cannot be resurrected by an outstanding model download. Model picking intersects oriented model bounds rather than scanning skin triangles on each pointer event.

The previews use reduced geometry and source colour textures. Unreal's complex materials and skeletal animation graph are not reproduced; the web preview follows each actor's live position and orientation. Native simulation rendering, sensors, actor controls and recordings are unchanged.

Asset preparation uses an isolated Unreal Python commandlet without saving native assets. `diagnostics/export_actor_models.py` exports each visible component's static/skeletal mesh and its blueprint transform; the stock glTF scene exporter skips Pawn meshes. `scripts/prepare_actor_models.mjs` reduces and repacks geometry. `diagnostics/export_actor_textures.py` exports source material textures, and `scripts/prepare_actor_textures.py` downsamples them and attaches browser material approximations.

Validation:

```sh
node --experimental-default-type=module tests/test_actor_models.mjs
python tests/test_actor_assets.py
```

The first check covers transforms, selection, focus, picking and asynchronous lifecycle behavior. The second verifies complete catalog coverage, nonempty exports, valid buffers and indices, finite bounds and texture references.
