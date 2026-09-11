import json,statistics,os
from pathlib import Path
p=Path(__file__).resolve().parent;result=[]
def percentile(xs,p=.95):return sorted(xs)[min(len(xs)-1,int(p*(len(xs)-1)))]
for name in ['high-720p','epic-720p','high-1080p','epic-1080p']:
 f=p/(name+'.json')
 if not f.exists():continue
 d=json.loads(f.read_text());r=d['samples'];elapsed=r[-1]['wall']-r[0]['wall'];cpu=(r[-1]['cpu_usage_usec']-r[0]['cpu_usage_usec'])/1e6/elapsed
 row={'case':name,'frames':d['last_frame']-d['start_frame'],'measured_seconds':r[-1]['seconds'],'simulation_fps':(r[-1]['frame']-r[0]['frame'])/elapsed,'frame_ms_median':statistics.median(x['timings']['total_ms'] for x in r),'frame_ms_p95':percentile([x['timings']['total_ms'] for x in r]),'service_ram_gib_mean':statistics.mean(x['service_memory_gib'] for x in r),'service_ram_gib_peak':max(x['service_memory_gib'] for x in r),'host_available_gib_min':min(x['host_available_gib'] for x in r),'cpu_core_equivalents':cpu,'cpu_percent_of_28_threads':cpu/28*100,'gpu_power_watts_mean':statistics.mean(sum(g['power_watts'] for g in x['gpus']) for x in r),'gpu_power_watts_peak':max(sum(g['power_watts'] for g in x['gpus']) for x in r),'maximum_observed_frame_gap_s':d['max_observed_frame_gap_s'],'vram_gib_peak_after_30s':max(g['vram_mib'] for x in r if x['seconds']>=30 for g in x['gpus'])/1024,'gpus':[]}
 for i in range(4):
  g=[x['gpus'][i] for x in r];row['gpus'].append({'nvidia_index':i,'utilization_percent_mean':statistics.mean(x['gpu_percent'] for x in g),'utilization_percent_p95':percentile([x['gpu_percent'] for x in g]),'vram_gib_peak':max(x['vram_mib'] for x in g)/1024,'power_watts_mean':statistics.mean(x['power_watts'] for x in g)})
 result.append(row)
(p/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
