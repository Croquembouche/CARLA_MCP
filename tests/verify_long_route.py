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
 report['changed_goal_arrival']=wait_arrival(bg,240)
 print('CHANGED_DESTINATION_REACHED_AND_STOPPED',flush=True)
 config=json.loads(Path('data/before-user-fixes-config.json').read_text());cmd('weather',config['weather'])
 # Exercise a longer route through junctions to the user's previously selected goal.
 original=next(a for a in config['actors'] if a['id']==31)['destination']
 report['original_goal_route']=cmd('destination',{'id':bg,'point':original})
 report['original_goal_arrival']=wait_arrival(bg,420)
 print('ORIGINAL_DESTINATION_REACHED',flush=True)
 report['passed']=True
finally:
 cmd('pause');Path('data/long-route-report.json').write_text(json.dumps(report,indent=2))
