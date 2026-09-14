# Live scene weather and LiDAR

Scene weather is the weather input for both camera appearance and ordinary LiDAR. The separate LiDAR noise panel, densities and loadout-rebuild command have been removed. Imported older loadouts automatically discard `weather_rain_density`, `weather_fog_density` and `weather_smoke_density`. New scenario exports use `lidar_weather_model: scene-weather-v1`.

Use **Weather → Apply weather** while running, paused, or recording. The controller applies changes between synchronized frames, and the native LiDAR snapshots the current world weather for every scan. Sensor IDs, subscriptions, point schemas, firing schedules and recording sessions remain in place. Native replay remains protected from edits. Recordings store scene weather for each captured frame and log weather commands.

**Fog starts at (m)** is the clear distance before the fog begins, not a visibility range. For fog surrounding the vehicle use 0 m. If fog starts at 100 m and LiDAR range is 80 m, that fog lies beyond the sensor's range. New weather presets start fog at 0 m; an existing scene's distance is preserved.

The physical receiver attenuates surface echoes with two-way transmission `exp(-2 * optical_depth)` and separately models atmospheric backscatter on emitted rays. Very dense fog can remove distant surfaces while nearby objects or droplet returns remain. The model never simply erases the entire cloud at a chosen percentage.

CARLA's percentage settings are artistic parameters, not physical concentrations. The current generic mapping is:

- Rain: `rainfall_mm_h = 0.5 * precipitation`; extinction `0.01 * rainfall_mm_h^0.6` per metre.
- Fog: extinction `0.002 * (1001^(fog_density / 100) - 1)` per metre, beginning at `fog_distance`. This gives 0 at 0%, approximately 0.0613/m at 50%, and 2/m at 100%.
- Dust: extinction `0.0003 * dust_storm` per metre.

Camera height fog uses the same base fog extinction, converted to Unreal centimetres and its base-2 transmission calculation. Its atmospheric light follows sun altitude; the map's black fog color no longer suppresses visible in-scattering. Camera height falloff, lighting, materials and the LiDAR receiver still affect the two outputs differently. These mappings are uncalibrated and do not establish an exact equivalence between camera visibility and a particular LiDAR wavelength. Per-profile physical medium parameters and spatial volumes can represent authored environments; their calibration remains independent of scene percentages. The legacy XYZI receiver shares scene weather and fog onset using its simpler return model. Semantic LiDAR remains geometric.

Example API update, valid during live recording:

```http
POST /api/command/weather
X-Control-Client: carla-control-center
Content-Type: application/json

{"fog_density":100,"fog_distance":0}
```

The response is returned after a synchronized frame has applied the weather. Clearing fog uses `{"fog_density":0}` and takes effect on the same sensor.
