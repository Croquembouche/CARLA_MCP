# Physical LiDAR model

This document describes the physical model implementation. Deployment and native acceptance results are tracked separately in the verification report. The supplied `generic` profile is an **uncalibrated pulsed time-of-flight model**; it does not claim to reproduce a named commercial sensor.

Enable the model on `sensor.lidar.ray_cast` using these blueprint attributes:

```json
{
  "material_model": "true",
  "physical_model": "true",
  "physical_profile": "generic",
  "output_format": "extended"
}
```

`physical_profile` is a basename under the Unreal project's `Content/Carla/Config/Lidar/` directory. Profiles must be present on every sensor worker. Invalid profiles are rejected at sensor creation. `output_format=xyzi` keeps the established CARLA XYZI point layout; it discards the additional per-return metadata. The native blueprint default remains the established sensor model unless physical mode is explicitly enabled. The control center defaults new ordinary LiDAR sensors to the generic physical profile and extended output, and exposes installed profiles in the sensor editor. Explicit legacy opt-outs remain supported.

## Scan and receiver

Each channel has its own firing schedule. Profiles can specify `elevation_deg`, `azimuth_offset_deg`, `firing_offset_us`, `beam_origins_m`, `channel_range_bias_m`, and `channel_gain`, each with one entry per channel. Firing offsets must fit inside a column (`channels / points_per_second`). Random draws are keyed by pulse ID to avoid dependence on task scheduling.

The sensor pose and available moving render geometry are interpolated between observations. This is an approximation between discrete physics states, including interpolated skinned vertex positions; it does not integrate physics at every firing. A newly observed sensor has no earlier pose history and reports a warm-start flag. Each moving mesh retains its own observation times; firing times are evaluated against those times. Changes in mesh topology, unavailable geometry, or firings older than the retained observation interval are reported as incomplete motion geometry. A low-rate sensor sharing a world with a faster observer can exceed that interval; this is not a substitute for a complete physics history.

Finite beams use weighted Gaussian samples of aperture position and direction. Beam weights sum to one, including samples that miss a surface. The receiver combines sub-beam echoes, merges unresolved echoes, applies photon signal and noise, thresholds, range bias, quantization, saturation, and selection of up to four returns. It is a reduced pulse/echo model, not a full electromagnetic waveform solver. Optical traversal retains up to eight candidates per sub-beam; candidate clipping is marked on returns.

`signal` is detected photon signal in the model. `intensity` is a normalized return fraction compensated for geometric spreading. These are different quantities. Optical losses, cover transmission, and atmospheric effects can affect the reported fraction. None of these values should be assumed equivalent to a vendor's integer intensity scale without calibration.

The legacy arbitrary point dropoff controls are superseded by the physical receiver when physical mode is enabled. Receiver thresholds, noise, saturation and emitted-beam propagation determine physical returns.

## Infrared material authoring

`Content/Carla/Config/Lidar/materials.json` is read once when each native worker starts. Its version-1 `materials` array maps an exact Unreal material path/name, or a component tag `LidarIR=<name>`, to explicit near-infrared properties. Restart workers after changing this registry. The registry is independent of visible base color; stock RGB textures are never treated as measured near-infrared data.

Each entry supplies `wavelengths_nm: [low, high]`, `dry_low` and `dry_high` arrays in the order **diffuse, retro, specular, transmission**, and optional `wet_multipliers` in the same order. Coefficients interpolate linearly between the two wavelengths and clamp to the endpoint outside that interval. Wetness interpolates each multiplier between 1 and the specified wet value using scene wetness 0–100. All supplied values require appropriate measurement/provenance for predictive use.

An optional `mask` contains integer `width` and `height` (1–256), plus flattened row-major `rgba` floats in [0, 1]. The four linear channels multiply diffuse, retro, specular and transmission respectively. These are numerical coefficient channels, not sRGB colors. Mask values use UV channel 0, nearest sampling, and repeat addressing after optional `uv_scale: [u,v]` and `uv_offset: [u,v]`. GPU UVs come from render triangles; moving mesh UVs interpolate with the hit barycentrics. The CPU path supports static render-face UVs and the moving-mesh UVs supplied by its intersection routine. Geometry without accessible UVs uses the entry's spatially uniform coefficients; it cannot reproduce a textured material mask.

The shipped checker entry is used only by the native acceptance fixture and is explicitly synthetic. Other assets continue using the existing effective material presets until explicit profiles are authored. No measured road, paint, clothing or glass-coating database was supplied with this implementation.

## Extended point data

`carla.PhysicalLidarMeasurement.raw_data` contains tightly packed 64-byte points in little-endian order. Measurement properties provide `scan_start`, `scan_end`, `channels`, `pulse_count`, `flags`, `profile_crc`, `sequence`, `horizontal_angle`, and `wavelength_nm`. CARLA's enclosing `frame`, `timestamp`, and `transform` retain the capture's simulation identity even when delivery is delayed.

| Offset | Field | Type | Meaning |
|---|---|---|---|
| 0, 4, 8 | x, y, z | float32 | Metres, CARLA axes, sensor frame at each firing |
| 12 | intensity | float32 | Normalized return fraction |
| 16 | range | float32 | Measured optical range in metres |
| 20 | signal | float32 | Model photon signal |
| 24 | ambient | float32 | Model background photon signal |
| 28 | pulse_width | float32 | Effective pulse width in nanoseconds |
| 32, 36 | azimuth, elevation | float32 | Reported angles in radians |
| 40 | time_offset | float32 | Seconds after the reported scan start |
| 44 | confidence | float32 | Model detection confidence |
| 48 | pulse_id | uint64 | Stable emitted-pulse identifier |
| 56 | channel | uint16 | Zero-based channel |
| 58, 59 | return_id, return_count | uint8 | Return index and number of detected returns |
| 60 | flags | uint32 | Return classification and approximation flags |

Return flags: surface `1`, atmosphere `2`, cover `4`, multipath `8`, saturation `16`, mixed echo `32`, false alarm `64`, clipped optical candidates `128`.

Scan flags: calibration status declared validated `1`, warm start `2`, simulated packet loss `4`, incomplete motion geometry `8`, frame dispatch budget exceeded `16`. Calibration flags reflect profile metadata; a SHA256 links supporting evidence but is not independent certification of that evidence.

Clock offset, drift and jitter affect the reported scan clock. The enclosing CARLA timestamp remains simulation time. Deskewing must use a consistent clock and the sensor poses at firing time. Raw motion-distorted points should not be treated as if they all occupy the sensor frame at the end of the scan.

Both native ROS and the control-center ROS bridge preserve the 64-byte layout. This installed CARLA build enables native ROS with `--ros2` (two dashes), and its native DDS publisher uses domain 0; the control-center bridge has its own domain configuration (42 in this workspace). ROS `PointField` has no uint64 integer type, so pulse IDs use `pulse_id_low` and `pulse_id_high` uint32 fields at offsets 48 and 52. Reconstruct with `(high << 32) | low`. Y and azimuth change sign for ROS coordinates. Recordings retain raw bytes plus a per-frame schema and scan metadata in the index.

The preview offers Height and Intensity coloring. Intensity uses a fixed 0–1 scale (weak dark blue to strong yellow); there is no per-frame normalization. Preview selection does not change recordings.

## Weather, cover and delivery

The native sensor reads current scene weather on every scan. Rain and fog changes take effect on existing sensors while running or recording, with no loadout rebuild. Scene fog starts at `fog_distance` metres; use zero for fog surrounding the vehicle. The separate LiDAR noise controls have been removed. See [live weather behavior](lidar-weather.md) for the percentage mapping and fog-distance semantics.

The profile also accepts authored visibility in metres, rainfall in mm/h, and smoke/dust/snow extinction in inverse metres. Scattering runs along emitted sub-beams including rays with no surface hit. Spatial `volumes` add oriented boxes of extinction and backscatter. Road spray creates approximate plumes behind moving vehicles in wet weather. These are bounded empirical approximations, not resolved particle-fluid simulations.

`cover` contains angular sectors with transmission and near-cover scatter. Receiver ambient background can be fixed or driven by scene illumination, with a configurable direct-sun term. The scalar scene controls remain approximate mappings; their units should not be confused with measured visibility or particle distributions.

Receiver `latency_ms`, `latency_jitter_ms`, and `packet_loss_probability` model delivery effects. To preserve CARLA's synchronous frame contract, packet loss produces an empty flagged measurement instead of silently withholding a frame. Delivery delay uses wall time and remains active while the synchronous server waits. This is a generic CARLA transport contract, not a vendor UDP protocol.

## Calibration workflow

`tools/lidar_calibrate.py` consumes paired reference-target measurements. Its docstring describes the required CSV columns and units. Include every emitted shot, with missing detections marked explicitly, and separate entire captures into training and validation. It fits per-channel range offsets and photon gains and reports held-out detection probabilities and residual range errors by range bin.

```bash
.venv/bin/python tools/lidar_calibrate.py reference-targets.csv \
  --base-profile /path/to/generic.json \
  --output-profile /path/to/candidate.json \
  --report /path/to/calibration-report.json
```

The utility always labels the candidate `fitted`. Hardware validation also needs checks of firing pattern, motion, edge mixing, detection thresholds, false alarms, saturation, materials, weather and timing. A synthetic fixture can test the fitter; it cannot supply this evidence. Vendor signal counts require an independently justified conversion before they can be used as photon measurements.
