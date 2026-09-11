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
 result=cmd('spawn',{'model':c.get('/api/catalog').json()['vehicles'][0]['id'],'role':'background','planner':'tm','spawn':pose(start),'destination':pose(end),'sensors':[]})
 created.append(result['id']);a=world.get_actor(result['id']);tm.auto_lane_change(a,False);tm.set_desired_speed(a,20)
 return a

def sample(a):
 t=a.get_transform();v=a.get_velocity();tl=a.get_traffic_light();wp=wm.get_waypoint(t.location)
 return {'frame':state()['frame'],'x':t.location.x,'y':t.location.y,'speed':v.length(),'brake':a.get_control().brake,'light':tl.id if tl else None,'at_light':a.is_at_traffic_light(),'junction':wp.is_junction,'road':wp.road_id,'next':str(tm.get_next_action(a))}
try:
 cmd('pause');config({'8':{'left':'Stop'}})
 left=spawn(8,'left');red=[]
 for _ in range(100):cmd('step');red.append(sample(left))
 assert any(x['light']==8 and x['at_light'] and x['speed']<.1 and x['brake']>.5 for x in red),red[-1]
 assert not any(x['junction'] for x in red),red[-1]
 report['red_stop']=red[-1];print('RED_STOP',red[-1],flush=True)
 cmd('delete',{'id':left.id});created.remove(left.id)
 config({'8':{'left':'Permissive'},'16':{'straight':'Protected'}})
 opposing=spawn(16,'straight')
 for _ in range(80):
  cmd('step')
  if opposing.get_location().x>-76 and opposing.get_velocity().length()>3:break
 left=spawn(8,'left',6);trace=[]
 for _ in range(260):
  cmd('step');trace.append({'left':sample(left),'opposing':sample(opposing)})
  if any(x['left']['junction'] for x in trace) and any(x['opposing']['junction'] for x in trace) and not trace[-1]['left']['junction'] and not trace[-1]['opposing']['junction']:break
 yielding=[x for x in trace if x['left']['at_light'] and x['left']['speed']<.15 and x['left']['brake']>.5 and x['opposing']['speed']>1]
 left_entry=next((x['left']['frame'] for x in trace if x['left']['junction']),None)
 opposing_entry=next((x['opposing']['frame'] for x in trace if x['opposing']['junction']),None)
 assert yielding and left_entry and opposing_entry and left_entry>opposing_entry,{'yield_frames':len(yielding),'left_entry':left_entry,'opposing_entry':opposing_entry,'last':trace[-1]}
 report['permissive_left']={'yield_frames':len(yielding),'left_entry':left_entry,'protected_opposing_entry':opposing_entry,'released_after_yield':True}
 (OUT/'driving-trace.json').write_text(json.dumps({'red':red,'trace':trace},indent=2))
 report['result']='passed';(OUT/'driving-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
finally:
 for aid in created:
  try:cmd('delete',{'id':aid})
  except:pass
 cmd('pause')
