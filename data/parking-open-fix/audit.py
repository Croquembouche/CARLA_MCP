import sys,json,math,collections
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import bootstrap,carla
from parking_driving import ParkingDriving,point,parking_entry
from types import SimpleNamespace
import httpx
c=carla.Client('127.0.0.1',2000);c.set_timeout(20);world=c.get_world();wm=world.get_map();a=world.get_actor(52)
s=httpx.get('http://127.0.0.1:8095/api/status').json();mapdata=httpx.get('http://127.0.0.1:8095/api/map').json();o=SimpleNamespace(world=world,wmap=wm,map_data=mapdata,parking_static=[],managed={52:{'actor':a,'role':'ego'}},state=s)
d=ParkingDriving(o);geom=d.geometry(a);print('GEOMETRY',geom,'rear',d.rear_axles,flush=True)
print('CURRENT',point(a.get_transform()),'control',a.get_control(),flush=True)
print('TM actions',[(str(x),w.road_id,w.lane_id,point(w.transform)) for x,w in c.get_trafficmanager(8005).get_all_actions(a)][-4:],flush=True)
spaces=json.load(open('data/parking/Town10HD_Opt.json'))['validated_spaces'];rows=[]
for b in spaces:
 near=wm.get_waypoint(carla.Location(x=b['x'],y=b['y'],z=b['z']),lane_type=carla.LaneType.Driving)
 row={'id':b['id'],'lane':b.get('lane'),'nearest_lane':[near.road_id,near.section_id,near.lane_id],'junction':near.is_junction,'heading_error':abs((near.transform.rotation.yaw-b['yaw']+180)%360-180),'lane_distance':math.hypot(near.transform.location.x-b['x'],near.transform.location.y-b['y']),'fits':2*a.bounding_box.extent.x+.1<=b['length'] and 2*a.bounding_box.extent.y+.1<=b['width']}
 if b['id']=='R135':print('R135',b,'near',point(near.transform),flush=True)
 rows.append(row)
Path('data/parking-open-fix/geometry-audit.json').write_text(json.dumps(rows,indent=2));print('AUDIT',{'total':len(rows),'fits':sum(x['fits'] for x in rows),'junction':sum(x['junction'] for x in rows),'heading_mismatch':sum(x['heading_error']>10 for x in rows)},flush=True)
