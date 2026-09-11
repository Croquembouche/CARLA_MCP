"""Live regression for a destination change inside overlapping Town10 connectors.
Requires the saved user scene restored and paused; restores its goal afterward.
"""
import json,time,math,httpx
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=120,headers={'X-Control-Client':'carla-control-center'})
def get():r=c.get('/api/status');r.raise_for_status();return r.json()
def cmd(action,payload={}):r=c.post('/api/command/'+action,json=payload);r.raise_for_status();return r.json()
report={'samples':[]};sid=None;original=None;ego=None
try:
 s=get();assert not s['running'] and s['mode']=='live' and not s['recording']
 ego=int(next(k for k,m in s['managed'].items() if m['role']=='ego'));original=s['managed'][str(ego)]['destination']
 points=c.get('/api/map').json()['spawn_points'];point=lambda i:next(p for p in points if p['index']==i)
 report['initial_route']=cmd('destination',{'id':ego,'point':point(96)})
 cmd('run');start=time.monotonic()
 while time.monotonic()-start<90:
  s=get();a=next(a for a in s['actors'] if a['id']==ego)
  if a['pose']['x']>-59.5 and a['pose']['y']<-56 and math.hypot(a['velocity']['x'],a['velocity']['y'])>1:
   assert a['pose']['x']<-50,a['pose'];break
  time.sleep(.03)
 else:raise AssertionError('Ego did not enter the target junction')
 report['before']={'frame':s['frame'],'actor':a,'running':s['running']}
 # Recording begins while moving and covers the destination command itself.
 sid=cmd('record-start',{'rosbag':True})['id'];report['session']=sid
 start_command=time.monotonic();result=cmd('destination',{'id':ego,'point':point(75)})
 report['replacement']=result;report['command_ms']=(time.monotonic()-start_command)*1000
 assert result['route_update']['preserved_junction'],result['route_update']
 route=result['route'];start=time.monotonic();last_frame=0
 while time.monotonic()-start<600:
  s=get();a=next(a for a in s['actors'] if a['id']==ego);m=s['managed'][str(ego)]
  assert s['running'] and s['mode']=='live' and not s.get('error'),s.get('error')
  assert m['route_update']['revision']==result['route_update']['revision']
  if s['frame']==last_frame:time.sleep(.1);continue
  last_frame=s['frame']
  speed=math.hypot(a['velocity']['x'],a['velocity']['y'])
  offset=min(math.hypot(p['x']-a['pose']['x'],p['y']-a['pose']['y']) for p in route)
  report['samples'].append({'frame':s['frame'],'pose':a['pose'],'speed':speed,'route_distance':offset,'arrived':m.get('arrived',False)})
  if sid and len(report['samples'])>=30:
   report['recording']=cmd('record-stop');sid=None
  if m.get('arrived') and speed<.15:
   distance=math.hypot(a['pose']['x']-m['destination']['x'],a['pose']['y']-m['destination']['y'])
   assert distance<3.2,distance
   report.update(passed=True,arrival_distance=distance,seconds=time.monotonic()-start,max_route_distance=max(x['route_distance'] for x in report['samples']))
   assert report['max_route_distance']<5,report['max_route_distance']
   print(json.dumps({k:v for k,v in report.items() if k not in ('samples','initial_route','replacement','before','recording')}),flush=True);break
  time.sleep(.2)
 else:raise AssertionError('Rerouted ego did not arrive')
finally:
 if sid:cmd('record-stop')
 if original is not None:report['restored_goal']=cmd('destination',{'id':ego,'point':original})
 Path('data/live-junction-reroute.json').write_text(json.dumps(report,indent=2))
