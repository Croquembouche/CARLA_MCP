# LiDAR material optics and camera reflections

Ordinary `sensor.lidar.ray_cast` now defaults to `material_model=true`. The output remains one strongest return per emitted ray in the existing XYZI format. `material_model=false` retains distance-only intensity and a geometric first hit. Semantic LiDAR, HSS LiDAR and radar keep their existing geometric models.

## Material response

The model separates diffuse reflection, retroreflection, specular reflection, and transmission. Surface intensity depends on incidence angle as well as atmospheric attenuation. Marks and sign faces have stronger effective near-infrared returns than concrete/asphalt. These are configurable simulation presets, not measured sensor/material calibration.

| Preset | Diffuse | Retro | Specular | Transmission | IOR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Generic/concrete | 0.30 | 0 | 0 | 0 | — |
| Asphalt | 0.10 | 0 | 0 | 0 | — |
| Road marking | 0.45 | 0.45 | 0 | 0 | — |
| Sign face | 0.25 | 0.70 | 0 | 0 | — |
| Mirror | 0 | 0 | 0.95 | 0 | — |
| Glass | 0.002 | 0 | Fresnel | 0.96 | 1.5 |
| Rubber/tire | 0.08 | 0 | 0 | 0 | — |

Material names select initial presets; the `RoadLine`/`RoadLines` component tag identifies dedicated marking meshes. Classification uses the hit mesh material section, including visible vehicle meshes associated with hidden sensor-collision proxies. A `LidarMaterial=glass` (or `mirror`, `marking`, `sign`, `asphalt`, `concrete`, `rubber`) component tag overrides the preset choice. Material scalar parameters `LidarDiffuse`, `LidarRetro`, `LidarSpecular`, `LidarTransmission`, `LidarIOR`, `LidarRoughness`, and `LidarThinSheet` override individual coefficients when authored in a material. Finite values are clamped to 0–1, except IOR (1–3).

Glass defaults to a zero-thickness sheet: it applies both interface losses and returns the transmitted beam to the surrounding medium. This prevents a single-surface window from treating the air behind it as glass. For closed glass geometry with modeled thickness, add the `LidarSolid` component tag or set the material scalar `LidarThinSheet=0`; that mode traces entry, internal refraction, and exit. The sheet approximation neglects the small lateral displacement and optical delay within a real thin pane.

The optical model traces reflected and refracted branches for up to three additional surface interactions. It uses dielectric Fresnel reflectance, total internal reflection, and Snell's law. The forward and reciprocal return paths attenuate the signal. A smooth mirror gives a strong direct return close to normal incidence; an angled mirror can create a return from a reflected target, or no return if no target sends energy back.

Measured range uses accumulated optical path length. The reported point lies along the original beam direction, so a mirror can produce an apparent point behind its surface. This matches the meaning of a range measurement; the packet does not disclose the true target position as though the ray had travelled straight. Weather noise is applied afterward to the selected return.

GPU scene construction now includes translucent geometry for external sensor queries. Visible glass, mirrors and marking/sign surfaces without sensor collision are added only to material-aware LiDAR; radar and semantic/legacy LiDAR retain their collision predicate. This does not make those meshes solid for physical simulation. Actor collision disablement remains authoritative, and a `LidarIgnore` component tag opts non-solid decorations out of this additional optical visibility. CPU tracing adds exact static-mesh queries for these non-solid optical surfaces and a two-sided glass exit query, since ordinary collision queries can discard backfaces when a ray starts inside glass.

## Camera reflections

The project enables Lumen hardware ray tracing, and the renderer launcher allows individual ray-traced effects instead of forcing all effects off. Saved postprocess profiles use hit lighting for reflections, front-layer translucency reflections, and three reflection bounces. Camera and LiDAR tracing volumes are retained together, so LiDAR bounds do not remove objects needed by camera mirrors. In external-query workers, the unused offscreen spectator view keeps only the sensor trace region; each actual camera retains its configured Lumen maximum trace distance. Hardware Lumen lighting is limited to actual captures in these workers; the unused main view disables lighting, shadows and postprocessing while retaining the external geometry query pass. This avoids allocating an additional lighting scene around the spectator, including on LiDAR-only workers.

RGB loadouts default to `use_ray_tracing=true`, including the cabin camera. An explicit `false` remains an opt-out. The 11 GiB worker launcher bounds the virtual-shadow cache to 2,048 pages; shadow resolution settings remain unchanged. Check for virtual-shadow page-pool overflow when increasing scene or camera complexity. Vulkan dedicated buffers now honor the existing host-memory fallback policy under VRAM pressure instead of aborting inside the device heap. Fallback preserves output but can reduce performance. The launcher uses Unreal's local filesystem DDC mode on the NVMe drive (`~/.cache/carla-ddc`, overridable with `CARLA_DDC_PATH`) to avoid shared Zen startup and slow loop-volume cache reads. Camera exposure and color grading remain profile-controlled. `OpticsTest.json` supplies a fixed exposure for the unlit regression fixture; it is not the normal driving profile.

## Verification and limits

`carla.Sensors.OpticsSelfTest` creates isolated concrete, marking, sign, mirror, and glass fixtures and compares CPU/GPU returns. Generate its materials using `scripts/assets/create-lidar-optics-fixtures.py` in the installed Unreal editor. The test includes normal and oblique solid glass, single-surface windows, non-solid glass, mirror multipath, a mirror miss, legacy first-hit behavior, and hidden/disabled actor exclusion. RGB captures additionally verify an object behind the camera appearing in a mirror, plus glass transmission and front-surface reflection.

This is a bounded geometric-optics model, not a full waveform or wavelength-calibrated LiDAR simulator. It does not evaluate arbitrary material graphs, texture masks, decal-only lane markings, microscopic roughness geometry, polarization, or nested dielectric stacks. Mixed paint/glass/mirror regions stored inside a single material section need separate geometry/material sections or a future texture-aware optical mask. GPU section mapping uses the mesh's LOD0 section material layout; assets with different layouts in other ray-tracing LODs require matching layouts. CPU results depend on collision geometry and available static-mesh CPU buffers; skeletal glass exits and coarse vehicle collision proxies can differ from GPU render geometry. The fifteen-fixture agreement does not establish equivalence across all stock assets.

Unreal camera translucency still has the renderer's front-layer and refraction limitations. See [Epic's Lumen documentation](https://dev.epicgames.com/documentation/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine).
