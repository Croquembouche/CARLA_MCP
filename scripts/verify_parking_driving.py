"""Disposable native-server checks for physical parking and TM handoffs."""
import sys,json,time,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.verify_scene_vehicles import Owner
from controller import Controller
from parking_driving import ParkingDriving,point
from agents.navigation.global_route_planner import GlobalRoutePlanner
import carla
root=Path(__file__).resolve().parents[1]
c=Owner();c.map_data=json.loads((root/'data/map-cache.json').read_text());c.planner=GlobalRoutePlanner(c.wmap,2);c.parking_driver=ParkingDriving(c)
c.scene_vehicles.convert();c.destination=lambda aid,p:Controller.destination(c,aid,p)
report={'trips':[]};out=root/'data/parking-driving/native-verification.json'
def run(aid,goal,steps=1400):
 m=c.managed[aid];a=m['actor'];start=point(a.get_transform());before=time.monotonic()
 r=c.destination(aid,goal);print('ACCEPTED',aid,len(r['route']),m['parking_trip']['stage'],'plan seconds',round(time.monotonic()-before,2),flush=True)
 item={'actor':aid,'goal':goal,'start':start,'trace':[],'max_frame_displacement':0};previous=start;report['trips'].append(item)
 collisions=[];sensor=c.world.spawn_actor(c.world.get_blueprint_library().find('sensor.other.collision'),carla.Transform(),attach_to=a);sensor.listen(lambda e:collisions.append({'other':e.other_actor.type_id,'impulse':e.normal_impulse.length()}))
 try:
  for i in range(steps):
   snap=c.world.get_snapshot().find(aid);control=c.parking_driver.tick(m,snap)
   if control is not None:c.client.apply_batch_sync([carla.command.ApplyVehicleControl(aid,control)],False)
   c.tick()
   current=point(a.get_transform());item['max_frame_displacement']=max(item['max_frame_displacement'],math.hypot(current['x']-previous['x'],current['y']-previous['y']));previous=current
   if i%20==0:
    row={'frame':i,'pose':point(a.get_transform()),'speed':a.get_velocity().length(),'stage':m['parking_trip']['stage'],'index':m['parking_trip']['index'],'blocked':m['parking_trip']['blocked']};item['trace'].append(row)
    if i%100==0:print(row,flush=True)
    out.write_text(json.dumps(report,indent=2))
   if m.get('arrived') or m['parking_trip']['stage']=='blocked':break
  item.update(final=point(a.get_transform()),arrived=m.get('arrived'),stage=m['parking_trip']['stage'],collisions=collisions,distance=math.hypot(a.get_location().x-start['x'],a.get_location().y-start['y']))
  out.write_text(json.dumps(report,indent=2));print('RESULT',item['arrived'],item['stage'],item['distance'],'collisions',collisions[:5],flush=True)
 finally:sensor.stop();sensor.destroy()
 return item
try:
 aid=min((aid for aid,m in c.managed.items() if m['actor'].type_id=='vehicle.lincoln.mkz'),key=lambda aid:math.hypot(c.managed[aid]['actor'].get_location().x+25.8,c.managed[aid]['actor'].get_location().y-31.2))
 if '--plan-only' in sys.argv:
  for id,m in c.managed.items():
   try:r=c.destination(id,{'x':-4.,'y':28.,'z':0});print('PLAN',id,m['actor'].type_id,len(r['route']),flush=True)
   except Exception as e:print('REJECT',id,str(e),flush=True)
 else:
  run(aid,{'x':-4.,'y':28.,'z':0})
  run(aid,{'parking_space':'P018'})
  if c.managed[aid].get('parked'):run(aid,{'parking_space':'P017'})
  assert all(v['arrived'] and not v['collisions'] and v['max_frame_displacement']<.7 for v in report['trips']),report['trips'][-1]['stage']
finally:
 c.clear_managed=Controller.clear_managed.__get__(c);c.clear_managed();c.tm.set_synchronous_mode(False)
 c.world.apply_settings(c.original)
