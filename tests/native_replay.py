import json,time
from pathlib import Path
import httpx
root=Path(__file__).resolve().parents[1];r=json.loads((root/'data/live-workflow-report.json').read_text())
if 'session' not in r:
 r['session']=next(json.loads(p.read_text())['id'] for p in sorted((root/'data/recordings').glob('*/manifest.json')) if json.loads(p.read_text()).get('frames')==50 and json.loads(p.read_text()).get('status')=='complete')
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 x=c.post('/api/command/'+a,json=p);x.raise_for_status();return x.json()
result=cmd('replay-native',{'id':r['session']})
time.sleep(3);cmd('pause');s=c.get('/api/status').json();assert s['mode']=='native-replay'
assert any(a['type'].startswith('vehicle.') for a in s['actors'])
stopped=cmd('replay-stop');s=c.get('/api/status').json();assert stopped['restarting_live_scene'] and s['phase']=='starting' and not s['running']
result.update(passed=True,actor_replay_checked=True,clean_stop_checked=True)
(root/'data/native-replay-report.json').write_text(json.dumps(result,indent=2));print(result)
