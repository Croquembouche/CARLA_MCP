"""Temporary Lincoln cabin and multi-camera acceptance scene; preserve existing actors."""
import json,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1];out=root/'data/sensor-view'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=600,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
for _ in range(600):
 try:s=c.get('/api/status').json()
 except httpx.TransportError:time.sleep(1);continue
 if s.get('recovery_operation',{}).get('stage')=='ready':break
 if s.get('phase')=='error':raise RuntimeError(s.get('error'))
 time.sleep(1)
else:raise RuntimeError('Scene did not restore')
assert not s['running'] and not s.get('recording') and len(s['managed']) in (41,42)
if len(s['managed'])==42:
 aid=next(a['id'] for a in s['actors'] if a['type']=='vehicle.lincoln.mkz_interior');result={'id':aid}
else:
 # Let the allocator spread the temporary camera coverage across available GPUs.
 print('AUTOMATIC_WORKERS',cmd('gpu-profile',{'profile':'auto'}),flush=True)
 configs=json.loads((out/'cabin-presets.json').read_text())
 configs.append({'name':'test_roof_lidar','type':'sensor.lidar.ray_cast','mount':{'z':2.5},'attributes':{'channels':'16','range':'80','points_per_second':'40000','rotation_frequency':'20'}})
 for point in c.get('/api/map').json()['spawn_points'][:20]:
  try:
   result=cmd('spawn',{'role':'ego','planner':'external','model':'vehicle.lincoln.mkz_interior','spawn':point,'sensors':configs});break
  except httpx.HTTPStatusError as e:
   if 'occupied' not in e.response.text:raise
 else:raise RuntimeError('No free position for temporary Lincoln')
aid=result['id'];(out/'temporary-actor.json').write_text(json.dumps({'id':aid}));print('TEMPORARY_LINCOLN',aid,flush=True)
for frame_index in range(60):
 result=cmd('step')
 if frame_index%10==9:print('VERIFIED_STEPS',frame_index+1,result,flush=True)
s=c.get('/api/status').json();assert len(s['sensors'])==9
report={'id':aid,'sensors':[]}
for sensor in s['sensors']:
 if sensor['parent']!=aid:continue
 r=c.get('/api/preview/'+str(sensor['id'])+'?width=960');r.raise_for_status();(out/(sensor['name']+'.jpg')).write_bytes(r.content);report['sensors'].append({'id':sensor['id'],'name':sensor['name'],'frame':r.headers['X-CARLA-Frame'],'bytes':len(r.content)})
(out/'cabin-live-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
