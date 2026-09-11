"""Check every mapped Town10 approach movement under a held stop indication."""
import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,httpx
root=Path(__file__).resolve().parents[1];out=root/'data/signal-stop-audit';out.mkdir(exist_ok=True)
h=httpx.Client(base_url='http://127.0.0.1:8095',timeout=120,headers={'X-Control-Client':'carla-control-center'})
def state():return h.get('/api/status').json()
def cmd(a,p={}):
 r=h.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
s=state();assert s['phase']=='connected' and s['mode']=='live' and not s['managed'],'Run in clean scene before restoring user actors'
client=carla.Client('127.0.0.1',2000);client.set_timeout(30);w=client.get_world();wm=w.get_map();tm=client.get_trafficmanager(8005)
for gid in s['movement_programs']:
 cmd('movement-program',{'group_id':int(gid),'operation':'enable','yellow_time':.5,'all_red_time':.5,'phases':[{'name':'Held stop audit','duration':600,'states':{}}]})
for _ in range(35):cmd('step')
for gid in s['movement_programs']:cmd('movement-program',{'group_id':int(gid),'operation':'hold'})
s=state();results=[];aid=None
try:
 for light in sorted([a for a in s['actors'] if a['type'].startswith('traffic.traffic_light')],key=lambda a:a['id']):
  for move,mapping in light['movement_lanes'].items():
   path=mapping['paths'][0]
   def wp(p):return wm.get_waypoint(carla.Location(x=p[0],y=p[1],z=p[2]))
   target_junctions={wp(p).junction_id for p in path if wp(p).is_junction};assert target_junctions
   start=wp(path[0]).previous(18)[0].transform;goal=wp(path[-1]).next(18)[0].transform
   def pose(t):return {'x':t.location.x,'y':t.location.y,'z':t.location.z,'yaw':t.rotation.yaw}
   result=cmd('spawn',{'role':'background','planner':'tm','model':'vehicle.lincoln.mkz','spawn':pose(start),'destination':pose(goal),'sensors':[]});aid=result['id'];a=w.get_actor(aid);tm.auto_lane_change(a,False);tm.set_desired_speed(a,20)
   trace=[]
   for _ in range(100):
    cmd('step');loc=a.get_location();v=a.get_velocity();road=wm.get_waypoint(loc);tl=a.get_traffic_light();ctl=a.get_control()
    trace.append({'frame':state()['frame'],'xy':[loc.x,loc.y],'speed':v.length(),'junction':road.is_junction,'junction_id':road.junction_id,'at_light':a.is_at_traffic_light(),'light':tl.id if tl else None,'brake':ctl.brake,'word':tl.get_movement_states() if tl else 0})
   stopped=any(p['at_light'] and p['light']==light['id'] and p['speed']<.15 and p['brake']>.5 for p in trace[-20:]);entered=any(p['junction'] and p['junction_id'] in target_junctions for p in trace)
   check={'light':light['id'],'movement':move,'stopped_at_expected_light':stopped,'entered_target_junction':entered,'pass':stopped and not entered,'last':trace[-1]};results.append(check);(out/f"{light['id']}-{move}.json").write_text(json.dumps(trace));(out/'report.json').write_text(json.dumps(results,indent=2));print(check,flush=True)
   cmd('delete',{'id':aid});aid=None
finally:
 if aid:
  try:cmd('delete',{'id':aid})
  except Exception:pass
 cmd('pause')
print('RESULT',sum(p['pass'] for p in results),'/',len(results),flush=True)
assert all(p['pass'] for p in results),'Inspect failing approach traces'
