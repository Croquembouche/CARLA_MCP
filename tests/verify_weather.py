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
   cmd('pause');return {'seconds':time.monotonic()-t,'samples':len(positions),'positions':positions,'final_pose':a['pose'],'destination':s['managed'][str(aid)]['destination']}
  time.sleep(1)
 cmd('pause');raise AssertionError(f'Arrival timeout: {a["pose"]}, goal={s["managed"][str(aid)]["destination"]}')
report={}
try:
 s=get('status');rgb=next(x['id'] for x in s['sensors'] if x['type']=='sensor.camera.rgb')
 images={}
 for name,alt in [('day',65),('night',-35)]:
  cmd('weather',{'cloudiness':0,'precipitation':0,'wetness':0,'precipitation_deposits':0,'fog_density':0,'sun_altitude_angle':alt})
  for _ in range(60):cmd('step')
  raw=c.get(f'/api/preview/{rgb}').content;Path(f'data/weather-{name}.jpg').write_bytes(raw);images[name]=np.array(Image.open(io.BytesIO(raw))).astype(float)
 report['camera_weather_mean_absolute_difference']=float(np.abs(images['day']-images['night']).mean())
 report['day_mean']=float(images['day'].mean());report['night_mean']=float(images['night'].mean())
 assert report['camera_weather_mean_absolute_difference']>10,report
 # The map includes emissive building surfaces; inspect exposed sky separately.
 report['day_sky_mean']=float(images['day'][0:25,175:230].mean());report['night_sky_mean']=float(images['night'][0:25,175:230].mean())
 assert report['night_sky_mean']<report['day_sky_mean']*.5,report
 assert report['day_mean']<190,report
 print('CAMERA_WEATHER_CHANGED',report['camera_weather_mean_absolute_difference'],flush=True)
 logdir=max(Path('/mnt/simulations/carla/carlab/host-setup/logs').glob('multigpu-*'),key=lambda p:p.stat().st_mtime)
 report['weather_workers']={}
 for i in range(4):
  log=(logdir/f'gpu-{i}.log').read_text(errors='replace')
  assert 'Replicated weather applied: sun=65.0 cloud=0.0 rain=0.0' in log
  assert 'Replicated weather applied: sun=-35.0 cloud=0.0 rain=0.0' in log
  assert 'altitude=-35.0 azimuth=0.0 sun_curve=0.0 sky=0.00' in log
  report['weather_workers'][f'gpu-{i}']='day and night applied to sky components'
 # Fog must change actual scene visibility as well.
 cmd('weather',{'sun_altitude_angle':65,'fog_density':100,'fog_distance':0})
 for _ in range(30):cmd('step')
 raw=c.get(f'/api/preview/{rgb}').content;Path('data/weather-fog.jpg').write_bytes(raw)
 fog=np.array(Image.open(io.BytesIO(raw))).astype(float)
 report['fog_difference']=float(np.abs(images['day']-fog).mean());assert report['fog_difference']>5
 config=json.loads(Path('data/before-user-fixes-config.json').read_text());cmd('weather',config['weather'])
 report['passed']=True
finally:
 cmd('pause');Path('data/weather-render-report.json').write_text(json.dumps(report,indent=2))
