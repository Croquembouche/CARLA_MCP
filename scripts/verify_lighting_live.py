import json,time
from pathlib import Path
import httpx
out=Path('data/lighting-lidar');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def status():return c.get('/api/status').json()
for _ in range(600):
 s=status()
 if s['phase']=='error':raise RuntimeError(s['error'])
 if s.get('recovery_operation',{}).get('stage')=='ready':break
 time.sleep(1)
else:raise RuntimeError('Restore timed out')
assert len(s['managed'])==41 and not s['running'] and not s.get('recording')
original=s['weather'];created=[];report={}
def spawn(role,planner):
 for p in c.get('/api/map').json()['spawn_points'][:20]:
  try:
   aid=cmd('spawn',{'role':role,'planner':planner,'model':'vehicle.ambulance.ford','spawn':p,'sensors':[]})['id'];created.append(aid);return aid
  except httpx.HTTPStatusError as e:
   if 'occupied' not in e.response.text:raise
 raise RuntimeError('No free test position')
try:
 tm=spawn('background','tm');external=spawn('ego','external')
 for name,w,mask,on in [('night',{'sun_altitude_angle':-10,'precipitation':0,'fog_density':0},3,True),('day',{'sun_altitude_angle':50,'precipitation':0,'fog_density':0},3,False),('rain',{'sun_altitude_angle':50,'precipitation':90,'fog_density':0},3,True),('fog',{'sun_altitude_angle':50,'precipitation':0,'fog_density':40},131,True)]:
  cmd('weather',w);cmd('step');s=status();vehicles=[a for a in s['actors'] if a['type'].startswith('vehicle.') and str(a['id']) in s['managed']]
  assert vehicles and all((a['light_state']&mask)==(mask if on else 0) for a in vehicles),(name,[(a['id'],a['light_state']) for a in vehicles])
  report[name]={'vehicles_checked':len(vehicles),'tm_state':next(a['light_state'] for a in vehicles if a['id']==tm)}
 # Let the actual automatic transmission select reverse before checking lamps.
 for _ in range(5):cmd('control',{'id':external,'throttle':.1,'reverse':True,'steer':-.5});cmd('step')
 for _ in range(2):cmd('control',{'id':external,'brake':.8,'reverse':True,'steer':-.5});cmd('step')
 s=status();value=next(a['light_state'] for a in s['actors'] if a['id']==external)
 assert value&8 and value&64 and value&32,value
 report['external_brake_reverse_left']=value
finally:
 for aid in reversed(created):cmd('delete',{'id':aid})
 cmd('weather',original);cmd('gpu-profile',{'profile':'auto'})
report['verified']=True;(out/'lighting-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
