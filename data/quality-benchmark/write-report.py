import json
from pathlib import Path
p=Path(__file__).resolve().parent;rows=json.loads((p/'summary.json').read_text());by={r['case']:r for r in rows}
text=['# CARLA graphics and HD camera resource test','',
'Test date: 2026-09-10. Hardware: four RTX 2080 Ti GPUs with 11 GiB VRAM each; Xeon E5-2690 v4, 28 logical CPUs; approximately 125 GiB system RAM.','',
'## Result','',
'Unrestricted Cinematic graphics with all camera ray-traced lighting effects enabled did not fit GPU memory. After disabling the incompatible external-query bounds optimization, Unreal reported Vulkan out-of-memory errors while allocating another 512 MiB. This failed before a valid high-resolution steady-state measurement, so no 720p or 1080p frame rate is claimed for the unrestricted configuration.','',
'Both 720p and 1080p completed with Epic graphics and the optimized GPU sensor path. Forced camera ray-traced lighting was disabled in these successful runs. They must not be described as unrestricted maximum-quality results.','',
'## Measured results','',
'RAM is CARLA systemd cgroup memory, including charged cache. VRAM is the highest observed nvidia-smi memory usage on a single GPU during the measurement window. Power is the total across all four GPUs, not whole-machine wall power. CPU equivalents are service CPU seconds divided by elapsed wall time; one equivalent is one fully occupied logical CPU.','',
'| Configuration | Frames | Frames/s | Frame time median / p95 | RAM mean / peak GiB | Peak single-GPU VRAM GiB | GPU power mean / peak W | CPU equivalents |',
'|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:
 text.append(f"| {r['case']} | {r['frames']} | {r['simulation_fps']:.2f} | {r['frame_ms_median']:.1f} / {r['frame_ms_p95']:.1f} ms | {r['service_ram_gib_mean']:.2f} / {r['service_ram_gib_peak']:.2f} | {max(g['vram_gib_peak'] for g in r['gpus']):.2f} | {r['gpu_power_watts_mean']:.1f} / {r['gpu_power_watts_peak']:.1f} | {r['cpu_core_equivalents']:.2f} |")
text+=['','## Protocol and limits','',
'- Same saved Town10 scene, night weather, 31 managed actors, six ego sensors, and four GPU workers. Ego position stayed effectively unchanged. Existing LiDAR/radar settings remained unchanged.',
'- Both RGB cameras used 1280 x 720 together, then 1920 x 1080 together. Each successful HD measurement ran for 90 seconds after at least 30 warm-up frames.',
'- Epic settings were applied as live CVar overrides: quality groups at level 3, view distance 1, skeletal LOD bias 0, 8x filtering, reflection downsampling 1, two reflection bounces, 100% screen percentage, 4000 MB texture pool, 8192 virtual-shadow pages. The source launcher remains High; effective test values are recorded separately.',
'- GPU ray sensors remained active. External query bounds stayed enabled and forced camera ray-traced lighting stayed off in the successful Epic runs.',
'- Browser previews were requested for both cameras at width 960 and remained compressed. This measures full-resolution sensor generation with bounded web previews, not streaming two uncompressed HD videos to the browser.',
'- Baseline-high is the initial long-running server. Baseline-fresh, when present, is the original configuration after restart. Renderer assignment and warm-cache state can affect throughput, so these are short live-scene measurements rather than identical deterministic replay trials.',
'- The unrestricted test first hit a deliberate external-query-bounds compatibility check. Disabling that optimization then exposed the GPU memory limit. Test-helper RPC failures are excluded.',
'- The original quality settings, camera loadouts, actors and weather were restored after testing. See final-restored-status.json for the verified final runtime state.','',
'Raw samples: summary.json, baseline-high.json, baseline-fresh.json, epic-720p.json, epic-1080p.json. Native OOM evidence: unrestricted-maximum-failure.json. Preview JPEGs are downscaled browser previews, not native-resolution exports.']
(p/'report.md').write_text('\n'.join(text)+'\n')
