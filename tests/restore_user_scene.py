"""Restore the saved three-actor scenario after the engine/client update."""
import json,time,httpx
from pathlib import Path
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
for _ in range(120):
 s=c.get('/api/status').json()
 if s['phase']=='connected':break
 if s['phase']=='error':raise RuntimeError(s.get('error'))
 time.sleep(3)
else:raise TimeoutError('Simulator startup')
config=json.loads(Path('data/before-user-fixes-config.json').read_text());mapping={}
for a in config['actors']:
 p={k:v for k,v in a.items() if k!='id'}
 # Walker actor pose is its capsule centre; spawn() adds 1 m above a nav point.
 if p['role']=='pedestrian':p['spawn']={**p['spawn'],'z':max(0,p['spawn']['z']-1)}
 r=cmd('spawn',p);mapping[str(a['id'])]=r['id'];print('RESTORED',a['id'],r['id'],flush=True)
cmd('weather',config['weather'])
Path('data/restored-user-ids.json').write_text(json.dumps(mapping,indent=2));print('RESTORE_COMPLETE',flush=True)
