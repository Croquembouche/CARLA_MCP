import bootstrap,carla,time,json,math
from pathlib import Path
c=carla.Client('127.0.0.1',2000);c.set_timeout(5);w=c.get_world();m=w.get_map();rows=[]
for _ in range(60):
 snap=w.get_snapshot()
 for a in w.get_actors().filter('vehicle.*'):
  p=a.get_location();v=a.get_velocity();wp=m.get_waypoint(p);tl=a.get_traffic_light();ctl=a.get_control()
  rows.append({'frame':snap.frame,'id':a.id,'xy':[p.x,p.y],'speed':math.sqrt(v.x*v.x+v.y*v.y),'junction':wp.is_junction,'lane':[wp.road_id,wp.lane_id],'at_light':a.is_at_traffic_light(),'light':tl.id if tl else None,'state':str(a.get_traffic_light_state()),'word':tl.get_movement_states() if tl else 0,'brake':ctl.brake,'throttle':ctl.throttle})
 time.sleep(.2)
Path('data/observed-vehicle-signals.json').write_text(json.dumps(rows,indent=2));print('rows',len(rows));print([r for r in rows if r['at_light']][-12:])
