import json,time,subprocess,httpx
from pathlib import Path
root=Path('/mnt/simulations/control-center');data=root/'data'
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(a,p={}):
 r=c.post('/api/command/'+a,json=p);r.raise_for_status();return r.json()
s=c.get('/api/status').json()
if s.get('recording') or s.get('mode')!='live':raise RuntimeError('Active recording or replay; do not restart')
config=c.get('/api/configuration').json();(data/'before-signal-controls-config.json').write_text(json.dumps(config,indent=2));(data/'before-signal-controls-state.json').write_text(json.dumps(s,indent=2))
print('SAVED_CURRENT_SCENARIO',flush=True)
subprocess.run(['systemctl','--user','restart','carla-control-center.service'],check=True)
for _ in range(60):
 try:
  if c.get('/api/status').status_code==200:break
 except httpx.HTTPError:pass
 time.sleep(1)
print('SERVICE_RESTARTED',cmd('start',{'gpus':'0,1,2,3'}),flush=True)
for _ in range(400):
 status=c.get('/api/status').json()
 if status['phase']=='connected':break
 if status['phase']=='error':raise RuntimeError(status.get('error'))
 time.sleep(3)
else:raise TimeoutError('CARLA startup')
print('CARLA_CONNECTED',flush=True);mapping={}
for actor in config['actors']:
 p={k:v for k,v in actor.items() if k!='id'}
 if p['role']=='pedestrian':p['spawn']={**p['spawn'],'z':max(0,p['spawn']['z']-1)}
 response=cmd('spawn',p);mapping[str(actor['id'])]=response['id'];print('RESTORED',actor['id'],response['id'],flush=True)
cmd('weather',config['weather']);(data/'signal-controls-restored-ids.json').write_text(json.dumps(mapping,indent=2))
print('RESTORE_COMPLETE',flush=True)
