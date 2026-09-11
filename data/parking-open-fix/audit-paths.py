import sys,json,math,time
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import bootstrap,carla
from parking_driving import parking_entry,point,Obstacles
wm=carla.Map('Town10HD_Opt',Path('data/map-cache.xodr').read_text());bays=json.load(open('data/parking/Town10HD_Opt.json'))['validated_spaces'];rows=[];started=time.monotonic()
for bay in bays:
 near=wm.get_waypoint(carla.Location(x=bay['x'],y=bay['y'],z=bay['z']),lane_type=carla.LaneType.Driving);row={'id':bay['id'],'clear_road_geometry_path':False,'errors':[]}
 for lead in (7,4,2,0,10,12,14,18):
  choices=near.next(lead) if lead else [near]
  if not choices or choices[0].is_junction:continue
  try:
   path=parking_entry(point(choices[0].transform),dict(bay,yaw=near.transform.rotation.yaw),Obstacles([],4.891970157623291,1.8356460332870483),3,2.8672780990600586,1.397070050239563)
   for p in path[::4]:
    w=wm.get_waypoint(carla.Location(x=p['x'],y=p['y'],z=p.get('z',0)),project_to_road=False,lane_type=carla.LaneType.Driving)
    if w and w.is_junction:raise ValueError('crosses junction')
   row.update(clear_road_geometry_path=True,staging_distance=lead,points=len(path));break
  except ValueError as e:row['errors'].append(str(e))
 rows.append(row)
 if len(rows)%30==0:print('AUDITED',len(rows),sum(r['clear_road_geometry_path'] for r in rows),flush=True)
result={'scope':'Empty-road geometric paths, not a guarantee against live obstacles or physical tracking errors','total':len(rows),'valid':sum(r['clear_road_geometry_path'] for r in rows),'seconds':time.monotonic()-started,'bays':rows};Path('data/parking-open-fix/path-audit.json').write_text(json.dumps(result,indent=2));print('FINISHED',result['valid'],result['total'],flush=True)
