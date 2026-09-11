"""Verify full recording while previews are requested, then remove only our test ego."""
import json,sys
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verification import verify_session
root=Path(__file__).resolve().parents[1];out=root/'data/sensor-view';c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=600,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
aid=json.loads((out/'temporary-actor.json').read_text())['id'];s=c.get('/api/status').json()
assert not s['running'] and not s.get('recording')
assert next(a for a in s['actors'] if a['id']==aid)['type']=='vehicle.lincoln.mkz_interior'
assert len(s['sensors'])==9 and len(s['managed'])==42
sid=None
try:
 sid=cmd('record-start',{'rosbag':True})['id']
 for _ in range(3):
  cmd('step')
  for sensor in c.get('/api/status').json()['sensors']:
   if sensor['parent']==aid:c.get('/api/preview/'+str(sensor['id'])+'?width=320').raise_for_status()
finally:
 if sid:cmd('record-stop')
report=verify_session(root/'data/recordings'/sid);(out/'recording-verification.json').write_text(json.dumps(report,indent=2));assert report['status']=='verified',report
cmd('delete',{'id':aid});cmd('gpu-profile',{'profile':'auto'})
s=c.get('/api/status').json();assert len(s['managed'])==41 and len(s['sensors'])==5 and s['worker_count']==2 and not s.get('error') and not s['running']
(out/'final-status.json').write_text(json.dumps(s,indent=2));(out/'final-configuration.json').write_text(json.dumps(c.get('/api/configuration').json(),indent=2))
(root/'data/recordings'/sid).rename(out/'live-acceptance-recording')
print(json.dumps({'verified_recording':report['status'],'frames':report['frames'],'sensor_samples':report['sensor_samples'],'actors':len(s['managed']),'sensors':len(s['sensors']),'workers':s['worker_count'],'paused':not s['running']}))
