"""Repeat fresh-process, seeded scenario benchmarks; leave the last trial paused.
Run from a terminal outside the web service. Each trial restarts the owned simulator.
"""
import argparse,json,time,subprocess,statistics,httpx,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recording import dump
from gpu_resources import summary
root=Path(__file__).resolve().parents[1];data=root/'data'
p=argparse.ArgumentParser();p.add_argument('--configuration',type=Path,required=True);p.add_argument('--workers',default='1,2');p.add_argument('--repeats',type=int,default=2);p.add_argument('--frames',type=int,default=50);args=p.parse_args()
counts=[int(x) for x in args.workers.split(',')];assert all(1<=n<=4 for n in counts) and 2<=args.repeats<=10 and 10<=args.frames<=1000
config=json.loads(args.configuration.read_text());c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=2000,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def restart(count):
 dump(data/'restart-live-request.json',{'gpus':'auto','created':time.time()})
 subprocess.run(['systemctl','--user','restart','carla-control-center.service'],check=True)
 for _ in range(600):
  try:
   state=c.get('/api/status').json()
   if state['phase']=='connected':break
   if state['phase']=='error':raise RuntimeError(state.get('error'))
  except (httpx.TransportError,json.JSONDecodeError):pass
  time.sleep(1)
 else:raise RuntimeError('Startup timeout')
 cmd('gpu-profile',{'profile':str(count)})
 cmd('restore-configuration',{'configuration':config})
 # Fixed warmup from a fresh process and the same restored configuration.
 for _ in range(20):cmd('step')
 return c.get('/api/status').json()
s=c.get('/api/status').json();assert not s['running'] and not s.get('recording') and s.get('mode','live')=='live'
report={'configuration':str(args.configuration),'protocol':'Fresh CARLA and controller processes, fixed step, TM and walker seed 42, identical saved poses/configuration, 20 warmup frames; sensor fidelity unchanged','trials':[]}
try:
 for repeat in range(args.repeats):
  for count in (counts if repeat%2==0 else list(reversed(counts))):
   print('TRIAL_START',repeat+1,count,flush=True);start=restart(count);rows=[];began=time.monotonic()
   for _ in range(args.frames):cmd('step');rows.append(c.get('/api/status').json())
   duration=time.monotonic()-began
   profiles=rows[-1].get('native_profiles',[])
   trial={'repeat':repeat+1,'workers':count,'frames':args.frames,'wall_seconds':duration,'real_time_factor':args.frames*.05/duration,'start_sim_time':start['time'],'end_sim_time':rows[-1]['time'],'frame_time_ms':duration*1000/args.frames,'pipeline_timings_ms':summary([s['performance']['last_frame_ms'] for s in rows]),'native_profiles':profiles}
   report['trials'].append(trial);dump(data/'repeated-benchmark.json',report);print('TRIAL_COMPLETE',json.dumps(trial),flush=True)
 report['groups']=[{'workers':n,'mean_frame_ms':statistics.mean(t['frame_time_ms'] for t in report['trials'] if t['workers']==n),'min_frame_ms':min(t['frame_time_ms'] for t in report['trials'] if t['workers']==n),'max_frame_ms':max(t['frame_time_ms'] for t in report['trials'] if t['workers']==n)} for n in counts]
 report['status']='complete'
finally:
 dump(data/'repeated-benchmark.json',report)
print('REPEATED_BENCHMARK_COMPLETE',flush=True)
