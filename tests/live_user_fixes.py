"""Validate the reported destination/weather bugs against the updated four-GPU scene."""
import json,time,math,io
from pathlib import Path
import httpx,numpy as np
from PIL import Image
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def get(p):r=c.get('/api/'+p);r.raise_for_status();return r.json()
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
def wait_arrival(aid,timeout=180):
 cmd('run');t=time.monotonic();positions=[]
 while time.monotonic()-t<timeout:
  s=get('status')
  if s.get('error'):raise RuntimeError(s['error'])
  a=next(a for a in s['actors'] if a['id']==aid);positions.append(a['pose'])
  if s['managed'][str(aid)].get('arrived'):
   cmd('pause')
   for _ in range(35):cmd('step')
   settled=get('status');a=next(a for a in settled['actors'] if a['id']==aid);d=settled['managed'][str(aid)]['destination']
   assert math.hypot(a['velocity']['x'],a['velocity']['y'])<.1,a
   assert math.hypot(a['pose']['x']-d['x'],a['pose']['y']-d['y'])<3.2,a
   assert a['control']['brake']==1,a
   return {'seconds':time.monotonic()-t,'samples':len(positions),'positions':positions,'final_pose':a['pose'],'destination':s['managed'][str(aid)]['destination']}
  time.sleep(1)
 cmd('pause');raise AssertionError(f'Arrival timeout: {a["pose"]}, goal={s["managed"][str(aid)]["destination"]}')
report={};ids=json.loads(Path('data/restored-user-ids.json').read_text());bg=ids['31']
try:
 # The browser test just applied a goal while driving.
 report['changed_goal_arrival']=wait_arrival(bg)
 print('NEW_DESTINATION_REACHED',flush=True)
 # Compare real RGB camera output, not only primary-server weather state.
 s=get('status');rgb=next(x['id'] for x in s['sensors'] if x['type']=='sensor.camera.rgb')
 images={}
 for name,alt in [('day',65),('night',-35)]:
  cmd('weather',{'cloudiness':0,'precipitation':0,'wetness':0,'sun_altitude_angle':alt})
  for _ in range(10):cmd('step')
  raw=c.get(f'/api/preview/{rgb}').content;Path(f'data/weather-{name}.jpg').write_bytes(raw);images[name]=np.array(Image.open(io.BytesIO(raw))).astype(float)
 report['camera_weather_mean_absolute_difference']=float(np.abs(images['day']-images['night']).mean())
 assert report['camera_weather_mean_absolute_difference']>5,report
 print('CAMERA_WEATHER_CHANGED',report['camera_weather_mean_absolute_difference'],flush=True)
 logdir=max(Path('/mnt/simulations/carla/carlab/host-setup/logs').glob('multigpu-*'),key=lambda p:p.stat().st_mtime)
 report['weather_workers']={}
 for i in range(4):
  log=(logdir/f'gpu-{i}.log').read_text(errors='replace')
  assert 'Replicated weather applied: sun=65.0 cloud=0.0 rain=0.0' in log
  assert 'Replicated weather applied: sun=-35.0 cloud=0.0 rain=0.0' in log
  report['weather_workers'][f'gpu-{i}']='day and night applied'
 config=json.loads(Path('data/before-user-fixes-config.json').read_text());cmd('weather',config['weather'])
 # Exercise a longer route through junctions to the user's previously selected goal.
 original=next(a for a in config['actors'] if a['id']==31)['destination']
 report['original_goal_route']=cmd('destination',{'id':bg,'point':original})
 report['original_goal_arrival']=wait_arrival(bg,420)
 print('ORIGINAL_DESTINATION_REACHED',flush=True)
 report['passed']=True
finally:
 cmd('pause');Path('data/live-user-fixes-report.json').write_text(json.dumps(report,indent=2))
