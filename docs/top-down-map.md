# Top-down 3D map

Click the **TOP-DOWN MAP** preview in the footer to open the loaded scene from directly overhead. The control is disabled until a map is loaded. In the 3D toolbar, **Top down** opens the overhead view and **Angled view** restores the previous orbit camera position.

In overhead mode, drag to pan and scroll to zoom. Double-clicking an actor focuses it while keeping the overhead orientation. **Fit map** fits the complete road bounds while retaining the current camera mode. OpenDRIVE and 3D views remain separate; the footer preview continues to show live or replay actor and route state.

The overhead view reuses the current Three.js renderer and loaded scene assets. It does not allocate a native CARLA camera or change the simulation. The 2D fit also skips hidden canvases, preventing invalid scaling when Fit map is used in 3D mode.

Validation: `node --experimental-default-type=module tests/test_top_down.mjs` covers overhead orientation, wide/narrow viewport fit, panning controls, mode-preserving fit and orbit pose restoration. Actor focus behavior is covered by `tests/test_actor_models.mjs` and live browser verification.
