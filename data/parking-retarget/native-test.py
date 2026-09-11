import sys,json,time,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import bootstrap,carla,parking
from parking_driving import ParkingDriving,point,angle
from agents.navigation.global_route_planner import GlobalRoutePlanner
from controller import pose,xyz
from types import SimpleNamespace
class Owner:
 def __init__(self):
  self.client=carla.Client('127.0.0.1',2100);self.client.set_timeout(10)
  for _ in range(180):
   try:self.world=self.client.get_world();break
   except RuntimeError:time.sleep(1)
  self.wmap=self.world.get_map();self.original=self.world.get_settings();s=self.world.get_settings();s.synchronous_mode=True;s.fixed_delta_seconds=.05;self.world.apply_settings(s)
  self.tm_port=8105;self.tm=self.client.get_trafficmanager(self.tm_port);self.tm.set_synchronous_mode(True);self.tm.set_random_device_seed(42)
  self.planner=GlobalRoutePlanner(self.wmap,2);self.map_data=json.load(open('data/map-cache.json'));self.managed={};self.parking_static=[]
  ids=set()
  for name in ['Car','Truck','Bus','Motorcycle','Bicycle']:
   ids.update(o.id for o in self.world.get_environment_objects(getattr(carla.CityObjectLabel,name)))
  self.world.enable_environment_objects(ids,False)
  for a in self.world.get_actors().filter('traffic.traffic_light*'):a.set_state(carla.TrafficLightState.Green);a.freeze(True)
  self.driver=ParkingDriving(self);self.tick()
 def refresh(self):
  self.state={'frame':self.world.get_snapshot().frame,'actors':[{'id':a.id,'pose':pose(a.get_transform()),'type':a.type_id,'extent':xyz(a.bounding_box.extent)} for a in self.world.get_actors().filter('vehicle.*')]}
 def tick(self):self.world.tick();self.refresh()
 def waypoint(self,p):return self.wmap.get_waypoint(carla.Location(x=p['x'],y=p['y'],z=p.get('z',0)),lane_type=carla.LaneType.Driving)
 def spawn(self,t,model='vehicle.mini.cooper'):
  t.location.z+=.5;b=self.world.get_blueprint_library().find(model);a=self.world.try_spawn_actor(b,t);assert a,'spawn blocked'
  a.set_autopilot(False,8105);a.apply_control(carla.VehicleControl(brake=1,hand_brake=True));self.managed[a.id]={'actor':a,'role':'background','planner':'tm','arrived':True,'parked':False,'destination':None,'route':[]}
  for _ in range(20):self.tick()
  return a
c=Owner();report={'cases':[]};out=Path('data/parking-retarget/native-verification.json');created=[]
def run(a,bid):
 m=c.managed[a.id];r=c.driver.assign(a.id,{'parking_space':bid});print('PLAN',bid,len(r['route']),m['parking_trip']['stage'],flush=True)
 item={'bay':bid,'stage_at_start':m['parking_trip']['stage'],'trace':[],'reverse_distance_m':0.,'max_frame_displacement':0.};report['cases'].append(item);previous=point(a.get_transform());collisions=[];minspeed=0;stages=set()
 sensor=c.world.spawn_actor(c.world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);sensor.listen(lambda e:collisions.append({'other':e.other_actor.type_id,'impulse':e.normal_impulse.length()}))
 try:
  for i in range(2200):
   ctrl=c.driver.tick(m,c.world.get_snapshot().find(a.id))
   if ctrl is not None:c.client.apply_batch_sync([carla.command.ApplyVehicleControl(a.id,ctrl)],False)
   if m['parking_trip']['stage']=='entering' and 'planned_entry' not in item:item['planned_entry']=m['parking_trip']['entry'];item['geometry']=c.driver.geometry(a)
   c.tick();p=point(a.get_transform());v=a.get_velocity();signed=v.x*math.cos(math.radians(p['yaw']))+v.y*math.sin(math.radians(p['yaw']));d=math.hypot(p['x']-previous['x'],p['y']-previous['y']);previous=p
   item['max_frame_displacement']=max(item['max_frame_displacement'],d)
   if signed<-.1:item['reverse_distance_m']+=d
   minspeed=min(minspeed,signed);stages.add(m['parking_trip']['stage'])
   if i%20==0:
    row={'frame':i,'pose':p,'speed':signed,'lateral_speed':-v.x*math.sin(math.radians(p['yaw']))+v.y*math.cos(math.radians(p['yaw'])),'yaw_rate':a.get_angular_velocity().z,'front_angles':[a.get_wheel_steer_angle(k) for k in [carla.VehicleWheelLocation.FL_Wheel,carla.VehicleWheelLocation.FR_Wheel]],'control':{'reverse':a.get_control().reverse,'steer':a.get_control().steer},'stage':m['parking_trip']['stage'],'index':m['parking_trip']['index'],'blocked':m['parking_trip']['blocked']};item['trace'].append(row)
    out.write_text(json.dumps(report,indent=2))
    if i%100==0:print(row,flush=True)
   if m.get('arrived') or m['parking_trip']['stage']=='blocked' or collisions:break
  target=m['parking_trip']['target'];p=point(a.get_transform());dyaw=abs(angle(math.radians(p['yaw']-target['yaw'])))
  item.update(arrived=m.get('arrived'),stage=m['parking_trip']['stage'],blocked=m['parking_trip']['blocked'],minimum_signed_speed=minspeed,stages=sorted(stages),position_error=math.hypot(p['x']-target['x'],p['y']-target['y']),yaw_error_degrees=math.degrees(dyaw),collisions=collisions)
  out.write_text(json.dumps(report,indent=2));print('RESULT',{k:(len(v) if k=='collisions' else v) for k,v in item.items() if k not in ('trace','planned_entry')},flush=True)
  assert item['arrived'] and item['stage']=='parked' and item['reverse_distance_m']>2 and item['yaw_error_degrees']<6 and not collisions,{k:(len(v) if k=='collisions' else v) for k,v in item.items() if k not in ('trace','planned_entry')}
 finally:sensor.stop();sensor.destroy()
def drive_road(a,target,replace=None):
 m=c.managed[a.id];old=m.get('parking_trip');revision=m.get('route_update',{}).get('revision',0)
 r=c.driver.assign(a.id,target)
 assert m['parking_trip'] is not old and r['route_update']['revision']==revision+1
 print('ROAD PLAN',r['destination'],m['parking_trip']['stage'],flush=True)
 result={'case':'parked_to_road','trace':[],'arrived':False};report['cases'].append(result)
 sensor=c.world.spawn_actor(c.world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);collisions=[];sensor.listen(lambda e:collisions.append(e.other_actor.type_id))
 try:
  for i in range(1600):
   ctrl=c.driver.tick(m,c.world.get_snapshot().find(a.id))
   if ctrl is not None:c.client.apply_batch_sync([carla.command.ApplyVehicleControl(a.id,ctrl)],False)
   c.tick()
   if i%50==0:
    ct=a.get_control();row={'frame':i,'pose':point(a.get_transform()),'speed':a.get_velocity().length(),'stage':m['parking_trip']['stage'],'blocked':m['parking_trip']['blocked'],'control':{'gear':ct.gear,'manual':ct.manual_gear_shift,'brake':ct.brake,'throttle':ct.throttle,'steer':ct.steer,'reverse':ct.reverse,'hand_brake':ct.hand_brake}}
    result['trace'].append(row);print(row,flush=True)
   if m.get('arrived') or m['parking_trip']['stage']=='blocked' or collisions:break
  result.update(arrived=m.get('arrived'),stage=m['parking_trip']['stage'],collisions=collisions,blocked=m['parking_trip']['blocked'])
  out.write_text(json.dumps(report,indent=2));assert result['arrived'] and not collisions,result
 finally:sensor.stop();sensor.destroy()
try:
 b=next(b for b in c.map_data['parking_spaces'] if b['id']=='P025');near=c.waypoint(b)
 start=next(w for w in near.previous(60) if not w.is_junction)
 otherbay=next(b for b in c.map_data['parking_spaces'] if b['id']=='P024')
 other=c.spawn(carla.Transform(carla.Location(x=otherbay['x'],y=otherbay['y'],z=0),carla.Rotation(yaw=otherbay['yaw'])));created.append(other)
 other.set_simulate_physics(False)
 a=c.spawn(start.transform,model='vehicle.lincoln.mkz');created.append(a);run(a,'P025')
 target=point(near.next(40)[0].transform);drive_road(a,{k:target[k] for k in ('x','y','z')})
finally:
 for a in created:
  if a.is_alive:a.destroy()
 c.tm.shut_down();c.world.apply_settings(c.original)
