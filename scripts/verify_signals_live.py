"""Live TM entry/clearance/yield regression cases using the real map; cleans up actors."""
import sys,json,math,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));import bootstrap,carla,httpx
root=Path(__file__).resolve().parents[1];c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def state():return c.get('/api/status').json()
def step(n):
 rows=[]
 for _ in range(n):cmd('step');rows.append(state())
 return rows
s=state();assert not s['running'] and not s['managed'] and not s.get('recording')
actors=[];collisions=[];sensors=[];report={}
client=carla.Client('127.0.0.1',2000);client.set_timeout(30);world=client.get_world()
def spawn(start,goal):
 aid=cmd('spawn',{'role':'background','planner':'tm','model':'vehicle.lincoln.mkz','spawn':dict(x=start[0],y=start[1]),'destination':dict(x=goal[0],y=goal[1])})['id'];actors.append(aid)
 sensor=world.spawn_actor(world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=world.get_actor(aid));sensor.listen(lambda e:collisions.append({'frame':e.frame,'other':e.other_actor.id}));sensors.append(sensor);return aid
def plan(states):
 cmd('movement-program',{'group_id':8,'operation':'enable','yellow_time':1,'all_red_time':1,'phases':[{'name':'Regression','duration':600,'states':states}]})
 step(45)
def pose(s,aid):return next(a for a in s['actors'] if a['id']==aid)
def signed(a):
 p=a['pose'];yaw=math.radians(p['yaw']);return -(p['x']+a['extent']['x']*math.cos(yaw)+29.084)
try:
 plan({})
 a=spawn((-8,-64.58),(-48.6,-20))
 rows=step(180);last=pose(rows[-1],a);speed=math.hypot(last['velocity']['x'],last['velocity']['y'])
 assert max(signed(pose(r,a)) for r in rows)<1 and speed<.5
 report['red_stop']={'passed':True,'speed':speed,'front_past_entry_m':signed(last)}
 plan({'8':{'left':'Protected'}})
 rows=step(160);assert any(signed(pose(r,a))>4 for r in rows)
 report['protected_entry']={'passed':True,'observed_entry':True}
 for sensor in sensors:sensor.stop();sensor.destroy()
 sensors=[]
 for aid in actors:cmd('delete',{'id':aid})
 actors=[]
 plan({})
 a=spawn((-8,-64.58),(-48.6,-20));b=spawn((-88,-58.4),(-8,-57.6))
 step(180)
 plan({'8':{'left':'Permissive'},'16':{'straight':'Protected'}})
 rows=step(200)
 yielded=[]
 for r in rows:
  x,y=pose(r,a),pose(r,b);bp=y['pose']
  if -63<bp['x']<-35 and abs(bp['y']+60)<4 and signed(x)<1:yielded.append(r['frame'])
 report['yield_trace']=[{'frame':r['frame'],'a':pose(r,a),'b':pose(r,b)} for r in rows]
 assert yielded,'No observed yield to protected opposing vehicle'
 assert any(signed(pose(r,a))>4 for r in rows),'Permissive vehicle never entered after opposing traffic'
 assert not collisions,collisions
 report['permissive_yield']={'passed':True,'yield_observed_frames':len(yielded),'collisions':collisions}
 for sensor in sensors:sensor.stop();sensor.destroy()
 sensors=[]
 for aid in actors:cmd('delete',{'id':aid})
 actors=[]
 plan({'8':{'left':'Protected','straight':'Protected'}})
 ped=cmd('spawn',{'role':'pedestrian','model':'walker.pedestrian.0043','spawn':{'x':-31,'y':-77},'destination':{'x':-31,'y':-49}})['id'];actors.append(ped)
 blocked=step(200);p0=pose(blocked[-1],ped)['pose']
 assert not blocked[-1]['managed'][str(ped)].get('arrived') and p0['y']<-69,('Pedestrian crossed active protected approach',p0)
 plan({})
 arrived=False
 for _ in range(500):
  cmd('step');r=state()
  if r['managed'][str(ped)].get('arrived'):arrived=True;break
 assert arrived,'Pedestrian failed to cross after stop phase'
 report['pedestrian_crossing']={'passed':True,'waiting_pose':p0,'arrival_pose':pose(r,ped)['pose']}
 report['passed']=True
finally:
 for sensor in sensors:
  try:sensor.stop();sensor.destroy()
  except RuntimeError:pass
 for aid in actors:cmd('delete',{'id':aid})
 cmd('movement-program',{'group_id':8,'operation':'disable'});step(45)
 (root/'data/reliability-signals-live.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
