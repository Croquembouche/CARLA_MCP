import json,time,httpx
from pathlib import Path
root=Path('/mnt/simulations/control-center');data=root/'data'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
config=json.loads((data/'movement-verification/before-replay-config.json').read_text())
print('RESTART',cmd('replay-stop'),flush=True)
for _ in range(600):
 try:s=c.get('/api/status').json()
 except httpx.HTTPError:time.sleep(1);continue
 if s['phase']=='connected':break
 if s['phase']=='error':raise RuntimeError(s['error'])
 time.sleep(3)
else:raise TimeoutError('Simulator startup')
for actor in config['actors']:
 p={k:v for k,v in actor.items() if k!='id'}
 if p['role']=='pedestrian':p['spawn']={**p['spawn'],'z':max(0,p['spawn']['z']-1)}
 print('RESTORE',actor['id'],cmd('spawn',p)['id'],flush=True)
cmd('weather',config['weather']);print('RESTORED',flush=True)
