import sys,threading,time,json,math
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import bootstrap,carla,parking
from parking_driving import ParkingDriving
from types import SimpleNamespace
import httpx
c=carla.Client('127.0.0.1',2000);c.set_timeout(20);world=c.get_world()
def advance():
 time.sleep(1);httpx.post('http://127.0.0.1:8095/api/command/step',json={},headers={'X-Control-Client':'carla-control-center'},timeout=40)
thread=threading.Thread(target=advance);thread.start();snap=world.wait_for_tick(20);thread.join();a=world.get_actor(52);p=a.get_transform();print('POSE',p,flush=True)
mapdata=httpx.get('http://127.0.0.1:8095/api/map').json();o=SimpleNamespace(world=world,wmap=world.get_map(),map_data=mapdata,parking_static=[])
d=ParkingDriving(o);ob=d.obstacles(a);rows=[]
for poly in {id(v):v for values in ob.grid.values() for v in values}.values():
 h=math.radians(p.rotation.yaw);x=p.location.x+ob.offset*math.cos(h);y=p.location.y+ob.offset*math.sin(h)
 if parking.overlaps(parking.corners(x,y,ob.length+.12,ob.width+.12,p.rotation.yaw),poly):rows.append({'polygon':poly,'actual_overlap':parking.overlaps(parking.corners(x,y,ob.length,ob.width,p.rotation.yaw),poly)})
print('BLOCKERS',json.dumps(rows),flush=True);Path('data/parking-open-fix/obstruction-audit.json').write_text(json.dumps(rows,indent=2))

from parking_driving import parking_entry,point,maneuver
b=next(b for b in mapdata['parking_spaces'] if b['id']=='R136');near=o.wmap.get_waypoint(carla.Location(x=b['x'],y=b['y'],z=b['z']),lane_type=carla.LaneType.Driving);wb,steer,radius=d.geometry(a)
for n in (7,10,12,14):
 choices=near.next(n)
 for w in choices:
  p=point(w.transform);print('STAGING',n,p,'junction',w.is_junction,'clear',ob.clear(p['x'],p['y'],math.radians(p['yaw'])),flush=True)
  try:entry=parking_entry(p,dict(b,yaw=w.transform.rotation.yaw),ob,radius,wb,d.rear_axles[a.id]);print('ENTRY',len(entry),flush=True)
  except ValueError as e:print('ENTRY ERROR',e,flush=True)
print('ACTORS',[(v.id,v.type_id,str(v.get_location())) for v in world.get_actors() if v.type_id.startswith(('vehicle.','walker.')) and v.get_location().distance(a.get_location())<30],flush=True)
