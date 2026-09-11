"""Short live integration check; expects temporary actor 82 with an accepted bay goal."""
import json,math,sys
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verification import verify_session
root=Path(__file__).resolve().parents[1];out=root/'data/parking-driving'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(action,p={}):
 r=c.post('/api/command/'+action,json=p);r.raise_for_status();return r.json()
s=c.get('/api/status').json();assert not s['running'] and not s['recording'];aid=82
assert s['managed'][str(aid)]['destination']['parking_space']=='P017'
start=next(a for a in s['actors'] if a['id']==aid)['pose'];sid=None
try:
 sid=cmd('record-start',{'rosbag':True})['id']
 for _ in range(12):cmd('step')
finally:
 if sid:cmd('record-stop')
s=c.get('/api/status').json();a=next(a for a in s['actors'] if a['id']==aid)
report=verify_session(root/'data/recordings'/sid)
report.update(temporary_actor=aid,parking_trip=s['managed'][str(aid)]['parking_trip'],distance_m=math.hypot(a['pose']['x']-start['x'],a['pose']['y']-start['y']),worker_count=s['worker_count'],ego_sensor_count=len(s['sensors']))
(out/'live-verification.json').write_text(json.dumps(report,indent=2))
assert report['status']=='verified',report
assert report['distance_m']>.02 and not s.get('error'),report
assert len(s['sensors'])==5 and s['worker_count']==1
cmd('delete',{'id':aid})
s=c.get('/api/status').json();assert len(s['managed'])==51 and not s['parking']['reserved']
(out/'final-status.json').write_text(json.dumps(s,indent=2))
(root/'data/recordings'/sid).rename(out/'live-acceptance-recording')
print(json.dumps(report,indent=2))
