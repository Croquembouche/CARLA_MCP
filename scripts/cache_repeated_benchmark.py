"""Register a completed fresh-process benchmark for this exact saved workload."""
import json,time,statistics,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gpu_resources import GpuResources
from recording import dump
root=Path(__file__).resolve().parents[1];data=root/'data'
report=json.loads((data/'repeated-benchmark.json').read_text());assert report['status']=='complete'
config=json.loads(Path(report['configuration']).read_text());results=[]
for workers in sorted({t['workers'] for t in report['trials']}):
 trials=[t for t in report['trials'] if t['workers']==workers]
 assert len(trials)>=2
 mean=statistics.mean(t['pipeline_timings_ms']['total_ms']['mean'] for t in trials)
 results.append({'workers':workers,'frames':sum(t['frames'] for t in trials),'timings_ms':{'total_ms':{'mean':mean,'p95':max(t['pipeline_timings_ms']['total_ms']['p95'] for t in trials)}},'trials':trials})
fastest=min(r['timings_ms']['total_ms']['mean'] for r in results)
selected=min(r['workers'] for r in results if r['timings_ms']['total_ms']['mean']<=fastest*1.10)
owner=SimpleNamespace(state={'map':config['map'],'weather':config['weather']},managed={str(a['id']):{'actor':SimpleNamespace(type_id=a['model'])} for a in config['actors']})
key=GpuResources.profile_key(owner,[s for a in config['actors'] for s in a.get('sensors',[])])
path=data/'gpu-benchmarks.json';cached=json.loads(path.read_text()) if path.exists() else {}
entry={'selected_workers':selected,'results':results,'measured_at':time.time(),'selection':'Fresh-process repeated benchmark; fewest workers within 10% of fastest mean pipeline time; reported p95 is the worst trial p95'}
cached[key]=entry;dump(path,cached);dump(data/'reliability-selected-profile.json',{'key':key,**entry});print('PROFILE_CACHED',selected,key)
