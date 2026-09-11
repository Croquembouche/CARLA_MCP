"""Live sidewalk placement and destination reassignment; removes its test walker."""
import json,math,sys,httpx
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lane_map import pedestrian_point
root=Path(__file__).resolve().parents[1]
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=150,headers={'X-Control-Client':'carla-control-center'})
def cmd(name,p={}):
 r=c.post('/api/command/'+name,json=p);r.raise_for_status();return r.json()
def status():return c.get('/api/status').json()
s=status();assert s['phase']=='connected' and not s['running'] and not s.get('recording')
m=c.get('/api/map').json();assert len(m['pedestrian_lanes'])==74 and len(m['crosswalks'])==16
# Prefer a known navigation point close to a long sidewalk segment.
candidates=[]
for lane in m['pedestrian_lanes']:
 pts=lane['points']
 for i in range(2,len(pts)-6):
  a,b=pts[i],pts[i+4]
  if math.dist(a[:2],b[:2])<7:continue
  d=min(math.dist(a[:2],[p['x'],p['y']]) for p in m['pedestrian_points'])
  candidates.append((d,a,b,lane['id']))
_,a,b,lane=sorted(candidates)[0];start=dict(zip(('x','y','z'),a[:3]));goal=dict(zip(('x','y','z'),b[:3]))
actor=None;report={'lane':lane,'spawn':start,'goal':goal}
try:
 actor=cmd('spawn',{'role':'pedestrian','model':'walker.pedestrian.0043','spawn':start,'destination':goal})['id'];report['actor']=actor
 for phase,target in [('outbound',goal),('return',start)]:
  if phase=='return':cmd('destination',{'id':actor,'point':target})
  before=next(a['pose'] for a in status()['actors'] if a['id']==actor)
  for n in range(180):
   cmd('step');s=status()
   if s['managed'][str(actor)].get('arrived'):break
  after=next(a['pose'] for a in s['actors'] if a['id']==actor)
  moved=math.hypot(after['x']-before['x'],after['y']-before['y'])
  report[phase]={'steps':n+1,'moved':moved,'arrived':s['managed'][str(actor)].get('arrived'),'pose':after}
  print(phase,report[phase],flush=True)
  assert moved>1 and report[phase]['arrived'],report
  assert math.hypot(after['x']-target['x'],after['y']-target['y'])<3,report
 # Invalid off-map destinations must not replace the existing destination.
 prior=status()['managed'][str(actor)]['destination']
 r=c.post('/api/command/destination',json={'id':actor,'point':{'x':10000,'y':10000}})
 assert r.status_code==400 and status()['managed'][str(actor)]['destination']==prior
 report['off_map_rejected']=True
finally:
 if actor:cmd('delete',{'id':actor})
 (root/'data/pedestrian-live-test.json').write_text(json.dumps(report,indent=2))
print('PEDESTRIAN_LIVE_TEST_PASSED',flush=True)
