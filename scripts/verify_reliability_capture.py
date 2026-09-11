"""Exercise live GPU capture, sealed recording, bag readback, and worker-fault detection.
Uses the currently restored paused scene. Recovery is triggered separately after UI inspection.
"""
import json,os,signal,sqlite3,time,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'data'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=300,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def state():return c.get('/api/status').json()
s=state();assert s['phase']=='connected' and not s['running'] and not s.get('recording') and len(s['sensors'])==5
report={}
def save(): (data/'reliability-capture-live.json').write_text(json.dumps(report,indent=2))
# Traverse the scene beyond the previous GPU failure, delivering every required sensor.
for n in range(320):
 cmd('step')
 if n%80==79:print('GPU_STRESS_FRAMES',n+1,flush=True)
s=state();report['stress']={'frames':320,'last_frame':s['frame'],'phase':s['phase'],'native_profiles':s.get('native_profiles')};save()
rec=cmd('record-start',{'rosbag':True});sid=rec['id']
for _ in range(30):cmd('step')
closed=cmd('record-stop');assert closed['status']=='complete',closed
r=c.post('/api/sessions/'+sid+'/verify',json={});r.raise_for_status();verified=r.json();assert verified['status']=='verified' and verified['sensor_samples']==150,verified
bag=next((data/'recordings'/sid/'rosbag2').glob('*.db3'))
with sqlite3.connect(f'file:{bag}?mode=ro',uri=True) as db:
 counts=dict(db.execute('select topics.name,count(messages.id) from topics left join messages on topics.id=messages.topic_id group by topics.id'))
 assert counts and all(v==30 for v in counts.values()),counts
r=c.post('/api/compare',json={'reference':sid,'candidate':sid});r.raise_for_status();comparison=r.json();assert comparison['trajectory_pass'] and comparison['sensor_payload_differences']==0,comparison
report['recording']={'id':sid,'verification':verified,'rosbag_counts':counts,'self_comparison':comparison};save();print('RECORDING_AND_BAG_PASSED',sid,flush=True)
# Capture an interrupted session and check the watchdog while the simulator is paused.
failed=cmd('record-start',{'rosbag':True})
for _ in range(5):cmd('step')
s=state();worker=s['gpu_workers'][0];pid=worker['pid'];command=Path(f'/proc/{pid}/cmdline').read_bytes()
assert b'UnrealEditor' in command and b'CarlaUnreal' in command
started=time.monotonic();os.kill(pid,signal.SIGKILL)
for _ in range(100):
 s=state()
 if s.get('worker_health',{}).get('status')=='failed':break
 time.sleep(.1)
assert s.get('worker_health',{}).get('status')=='failed' and not s['running'],s.get('error')
report['fault']={'pid':pid,'detection_seconds':time.monotonic()-started,'health':s['worker_health'],'recording':failed['id']};save();print('WORKER_FAULT_DETECTED',json.dumps(report['fault']),flush=True)
for _ in range(100):
 manifest=json.loads((data/'recordings'/failed['id']/'manifest.json').read_text())
 if manifest['status']=='failed':break
 time.sleep(.2)
assert manifest['status']=='failed' and manifest['frames']==5,manifest
report['fault']['recording_status']=manifest['status'];report['passed']=True;save();print('CAPTURE_FAULT_TEST_PASSED',flush=True)
