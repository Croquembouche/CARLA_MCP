import time,json,httpx
from pathlib import Path
p=Path('data/lag-light-fix');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=30)
for _ in range(600):
 try:
  s=c.get('/api/status').json()
  if s.get('phase')=='error':raise RuntimeError(s.get('error'))
  if s.get('recovery_operation',{}).get('stage')=='ready':break
 except httpx.TransportError:pass
 time.sleep(1)
else:raise RuntimeError('restore timeout')
def cmd(n,payload={}):
 r=c.post('/api/command/'+n,json=payload,headers={'X-Control-Client':'carla-control-center'},timeout=120);r.raise_for_status();return r.json()
original=s['weather'];ego=next(int(k) for k,v in s['managed'].items() if v['role']=='ego');report=[]
try:
 for label,w in [('night',dict(original,sun_altitude_angle=-35,cloudiness=10,precipitation=0,wetness=0)),('day',dict(original,sun_altitude_angle=65,cloudiness=5,precipitation=0,wetness=0)),('rain',dict(original,sun_altitude_angle=35,cloudiness=95,precipitation=70,wetness=80))]:
  cmd('weather',w);cmd('run');s=c.get('/api/status').json();start=s['frame']
  for _ in range(200):
   s=c.get('/api/status').json()
   if s['frame']>=start+30:break
   time.sleep(.2)
  else:raise RuntimeError('frame wait')
  cmd('pause');s=c.get('/api/status').json();a=next(a for a in s['actors'] if a['id']==ego);bits=a['light_state'];assert bool(bits&2)==(label=='night'),(label,bits)
  for cam in s['sensors']:
   if cam['type']=='sensor.camera.rgb':
    r=c.get(f"/api/preview/{cam['id']}?width=960");r.raise_for_status();(p/f"{cam['name']}-{label}.jpg").write_bytes(r.content)
  report.append({'condition':label,'frame':s['frame'],'ego':ego,'lights':bits,'weather':s['weather']});print(label,s['frame'],bits,flush=True)
finally:
 cmd('weather',original);cmd('run');start=c.get('/api/status').json()['frame']
 for _ in range(200):
  s=c.get('/api/status').json()
  if s['frame']>=start+30:break
  time.sleep(.2)
 cmd('pause');(p/'lights.json').write_text(json.dumps(report,indent=2))
