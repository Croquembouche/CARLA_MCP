import json,time,urllib.request
from pathlib import Path
root=Path(__file__).parent;base='http://127.0.0.1:8095'
def status():return json.load(urllib.request.urlopen(base+'/api/status',timeout=10))
def command(name,payload):
 request=urllib.request.Request(base+'/api/command/'+name,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 return json.load(urllib.request.urlopen(request,timeout=120))
for _ in range(600):
 try:s=status()
 except OSError:time.sleep(1);continue
 if s['phase']=='error':raise RuntimeError(s['error'])
 if s.get('recovery_operation',{}).get('stage')=='ready':break
 time.sleep(1)
else:raise RuntimeError('Restore did not finish')
assert not s['running'] and len(s['sensors'])==6
start=s['frame'];print('RESTORED',start,flush=True)
for i in range(800):
 command('step',{})
 s=status();assert s['phase']=='connected' and s['error'] is None
 if i%50==49:
  mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
  print('STEPS',i+1,'ENTRIES',s['signal_audit']['entries_observed'],'AVAILABLE_GIB',round(mem['MemAvailable']/1024**2,1),flush=True)
  if mem['MemAvailable']<16*1024**2:raise RuntimeError('Stopped bounded verification before memory pressure')
 if i>=99 and s['signal_audit']['entries_observed']>=1:break
assert s['signal_audit']['entries_observed']>0,'No real intersection crossing observed within the bounded test'
frames=[]
for sensor in s['sensors']:
 fmt='points' if sensor['type'].startswith('sensor.lidar.') else 'image'
 with urllib.request.urlopen(base+f"/api/preview/{sensor['id']}?format={fmt}&width=480") as response:
  assert response.status==200 and response.read()
  frames.append(int(response.headers['X-CARLA-Frame']))
assert set(frames)=={s['frame']}
assert not s['running'] and s['worker_count']==4
(root/'final-status.json').write_text(json.dumps(s,indent=2))
report={'verified':True,'start_frame':start,'final_frame':s['frame'],'steps':i+1,'actor_count':len(s['managed']),'sensors':len(s['sensors']),'worker_count':s['worker_count'],'signal_audit':s['signal_audit'],'error':s['error'],'running':s['running']}
(root/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
