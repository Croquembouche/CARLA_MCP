"""Real server acceptance; creates only its own actors and an evidence recording."""
import sys, time, json, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import httpx
import carla
ROOT=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def get(p):r=c.get('/api/'+p);r.raise_for_status();return r.json()
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p)
 if not r.is_success:raise RuntimeError(f'{a}: {r.status_code} {r.text}')
 return r.json()
report={}
try:
 state=get('status');assert state['phase']=='connected' and not state['running']
 m=get('map');catalog=get('catalog');assert len(m['lanes'])>10 and len(catalog['vehicles'])>5
 report.update(map=m['name'],lanes=len(m['lanes']),buildings=len(m['buildings']),models=len(catalog['vehicles']))
 points=m['spawn_points'];model=next((x['id'] for x in catalog['vehicles'] if x['id']=='vehicle.tesla.model3'),catalog['vehicles'][0]['id'])
 ego=cmd('spawn',{'role':'ego','model':model,'spawn':points[0],'destination':points[5],'planner':'tm'})['id'];report['ego']=ego;print('EGO',ego,flush=True)
 bg=cmd('spawn',{'role':'background','model':model,'spawn':points[10],'destination':points[20]})['id'];report['background']=bg;print('BACKGROUND',bg,flush=True)
 direct=carla.Client('127.0.0.1',2000);direct.set_timeout(30);world=direct.get_world()
 nav=world.get_random_location_from_navigation();dest=world.get_random_location_from_navigation()
 if nav and dest:
  ped=cmd('spawn',{'role':'pedestrian','model':catalog['walkers'][0],'spawn':{'x':nav.x,'y':nav.y,'z':nav.z},'destination':{'x':dest.x,'y':dest.y,'z':dest.z}})['id'];report['pedestrian']=ped;print('PEDESTRIAN',ped,flush=True)
 cmd('weather',{'cloudiness':35,'sun_altitude_angle':45,'precipitation':0})
 before=get('status');report['sensor_types']=[s['type'] for s in before['sensors']];assert len(report['sensor_types'])==5
 rec=cmd('record-start',{'rosbag':True});report['session']=rec['id'];print('RECORDING',rec['id'],flush=True)
 for i in range(50):
  cmd('step')
  if i%10==0:print('FRAME',i,flush=True)
 result=cmd('record-stop');assert result['status']=='complete' and result['frames']==50
 after=get('status');p0=next(x['pose'] for x in before['actors'] if x['id']==ego);p1=next(x['pose'] for x in after['actors'] if x['id']==ego)
 report['ego_distance_m']=math.hypot(p1['x']-p0['x'],p1['y']-p0['y']);assert report['ego_distance_m']>.1
 report['ros_topics']=result['ros_topics'];assert len(result['ros_topics'])>=9 and all(x==50 for x in result['ros_topics'].values())
 for i in (0,25,49):
  frame=get(f'sessions/{rec["id"]}/frame/{i}');assert len(frame['sensor_files'])==5 and all(s['frame']==frame['frame'] and abs(s['timestamp']-frame['time'])<1e-5 for s in frame['sensor_files'])
  assert any(a['type'].startswith('traffic.traffic_light') for a in frame['actors'])
 report['recorded_state_checks']='passed'
 # A nearby destination exercises both road routing and arrival braking.
 current=next(a['pose'] for a in after['actors'] if a['id']==ego)
 yaw=math.radians(current['yaw'])
 cmd('destination',{'id':ego,'point':{'x':current['x']+8*math.cos(yaw),'y':current['y']+8*math.sin(yaw),'z':current['z']}})
 for _ in range(160):
  cmd('step');latest=get('status')
  if latest['managed'][str(ego)].get('arrived'):break
 assert latest['managed'][str(ego)].get('arrived')
 assert next(a for a in latest['actors'] if a['id']==ego)['control']['brake']==1
 report['destination_arrival_and_braking']='passed'
 assert c.get(f'/api/sessions/{rec["id"]}/preview/0').status_code==200
 ext=cmd('spawn',{'role':'ego','planner':'external','model':model,'spawn':points[30],'sensors':[]})['id']
 cmd('control',{'id':ext,'throttle':.3,'steer':.1});cmd('step');a=next(a for a in get('status')['actors'] if a['id']==ext);assert a['control']['steer']>.09
 time.sleep(1.1);cmd('step');a=next(a for a in get('status')['actors'] if a['id']==ext);assert a['control']['brake']==1
 report['external_control_watchdog']='passed';cmd('delete',{'id':ext})
 report['passed']=True
finally:
 (ROOT/'data/live-workflow-report.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2),flush=True)
