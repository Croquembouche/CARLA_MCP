"""Observe the UI-driven moving-ego reroute; does not tick, pause or steer."""
import json,time,math,argparse,httpx
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--actor',type=int,required=True);p.add_argument('--revision',type=int,required=True);p.add_argument('--timeout',type=float,default=360);args=p.parse_args()
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=10)
report={'actor':args.actor,'samples':[]};started=time.monotonic()
try:
 while time.monotonic()-started<args.timeout:
  s=c.get('/api/status').json();m=s['managed'][str(args.actor)];a=next(a for a in s['actors'] if a['id']==args.actor)
  assert s['running'] and s['mode']=='live' and not s.get('error'),(s['running'],s.get('error'))
  sample=dict(frame=s['frame'],revision=m.get('route_update',{}).get('revision',0),pose=a['pose'],speed=math.hypot(a['velocity']['x'],a['velocity']['y']),destination=m['destination'],arrived=m.get('arrived',False))
  report['samples'].append(sample)
  if sample['revision']>=args.revision and sample['arrived']:
   distance=math.hypot(a['pose']['x']-m['destination']['x'],a['pose']['y']-m['destination']['y']);assert distance<3.2
   report.update(passed=True,arrival_distance=distance,seconds=time.monotonic()-started);print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True);break
  time.sleep(.3)
 else:raise AssertionError('Destination not reached before timeout')
finally:
 Path('data/live-reroute-driving.json').write_text(json.dumps(report,indent=2))
