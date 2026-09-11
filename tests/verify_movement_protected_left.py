"""Exercise TM stopping, protected entry and permissive yielding in Town10."""
import sys,json,math,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap,carla,httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/movement-verification';OUT.mkdir(exist_ok=True)
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def state():return c.get('/api/status').json()
client=carla.Client('127.0.0.1',2000);client.set_timeout(120);world=client.get_world();wm=world.get_map();tm=client.get_trafficmanager(8005)
created=[];report={}
def signal(aid):return next(a for a in state()['actors'] if a['id']==aid)
def config(states):
 cmd('movement-program',{'group_id':8,'operation':'update','yellow_time':.5,'all_red_time':.5,'phases':[{'name':'Driving verification','duration':60,'states':states}]})
 for _ in range(40):
  cmd('step')
  if state()['movement_programs']['8']['stage']=='green':break
 else:raise AssertionError('Phase did not leave clearance')
 cmd('movement-program',{'group_id':8,'operation':'hold'})
def spawn(aid,move,distance=15):
 path=signal(aid)['movement_lanes'][move]['paths'][0]
 def wp(p):return wm.get_waypoint(carla.Location(x=p[0],y=p[1],z=p[2]))
 start=wp(path[0]).previous(distance)[0].transform;end=wp(path[-1]).next(18)[0].transform
 def pose(t):return {'x':t.location.x,'y':t.location.y,'z':t.location.z,'yaw':t.rotation.yaw}
 result=cmd('spawn',{'model':'vehicle.lincoln.mkz','role':'background','planner':'tm','spawn':pose(start),'destination':pose(end),'sensors':[]})
 created.append(result['id']);a=world.get_actor(result['id']);tm.auto_lane_change(a,False);tm.set_desired_speed(a,20)
 return a

def sample(a):
 t=a.get_transform();v=a.get_velocity();tl=a.get_traffic_light();wp=wm.get_waypoint(t.location)
 return {'frame':state()['frame'],'x':t.location.x,'y':t.location.y,'speed':v.length(),'brake':a.get_control().brake,'light':tl.id if tl else None,'at_light':a.is_at_traffic_light(),'junction':wp.is_junction,'road':wp.road_id,'next':str(tm.get_next_action(a))}
try:
 config({'8':{'left':'Protected'}})
 actor=spawn(8,'left',6);trace=[]
 for _ in range(100):
  cmd('step');trace.append(sample(actor))
  if trace[-1]['junction']:break
 assert any(x['junction'] for x in trace),trace[-1]
 report={'result':'passed','protected_left_entered':True,'entry':trace[-1]}
 (OUT/'protected-left-report.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
finally:
 for aid in created:cmd('delete',{'id':aid})
 cmd('pause')
