"""Restart the owned scene and restore a saved configuration, paused."""
import argparse,json,time,subprocess,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('configuration',type=Path);p.add_argument('--gpus',choices=['auto','0,1,2,3','3'],default='auto');a=p.parse_args()
config=json.loads(a.configuration.read_text())
request=root/'data/restart-live-request.json';request.write_text(json.dumps({'gpus':a.gpus,'created':time.time(),'configuration':config}))
subprocess.run(['systemctl','--user','restart','carla-control-center.service'],check=True)
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=10)
for _ in range(900):
 try:
  s=c.get('/api/status').json()
  if s.get('phase')=='error':raise RuntimeError(s.get('error'))
  if s.get('recovery_operation',{}).get('stage')=='ready':
   restored=[m for m in s['managed'].values() if 'scene_vehicles' in config or not m.get('scene_source')]
   assert s['phase']=='connected' and not s['running'] and len(restored)==len(config['actors'])
   assert len(s['sensors'])==sum(len(x.get('sensors',[])) for x in config['actors'])
   (root/'data/reliability-restored-status.json').write_text(json.dumps(s,indent=2))
   print('SAVED_SCENE_RESTORED',json.dumps({'frame':s['frame'],'actors':list(s['managed']),'sensors':len(s['sensors']),'workers':s['worker_count']}),flush=True);break
 except (httpx.TransportError,json.JSONDecodeError):pass
 time.sleep(1)
else:raise RuntimeError('Scene restore timed out')
