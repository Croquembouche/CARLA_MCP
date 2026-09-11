"""Restore saved actor loadouts, weather and signal configuration after deployment."""
import json,sys,time,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'data';config=json.loads((data/'pedestrian-backup/configuration.json').read_text())
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=2000,headers={'X-Control-Client':'carla-control-center'})
def cmd(action,payload):
 r=c.post('/api/command/'+action,json=payload);r.raise_for_status();return r.json()
s=c.get('/api/status').json()
if s['phase']!='connected' or s.get('mode','live')!='live' or s['managed'] or s.get('recording'):raise RuntimeError('Requires clean connected live scene')
ids={}
# Restore weather before loading renderers so every renderer receives the requested weather.
cmd('weather',config['weather'])
for actor in config['actors']:
 p={k:v for k,v in actor.items() if k!='id'}
 if p['role']=='pedestrian':p['spawn']={**p['spawn'],'z':max(0,p['spawn']['z']-1)}
 result=cmd('spawn',p);ids[str(actor['id'])]=result['id'];print('RESTORED',actor['role'],result['id'],flush=True)
for gid,program in config['movement_programs'].items():
 if program['active']:cmd('movement-program',dict(group_id=int(gid),operation='enable',**{k:program[k] for k in ('phases','yellow_time','all_red_time')}))
for _ in range(110):
 s=c.get('/api/status').json()
 if all(p.get('stage')=='green' for p in s['movement_programs'].values() if p['active']):break
 cmd('step',{})
s=c.get('/api/status').json();assert len(s['managed'])==len(config['actors']);assert len(s['sensors'])==sum(len(a.get('sensors',[])) for a in config['actors']);assert s['phase']=='connected' and not s['running'] and not s.get('error')
(data/'pedestrian-restored-ids.json').write_text(json.dumps(ids,indent=2));(data/'pedestrian-restored-state.json').write_text(json.dumps(s,indent=2));print('RESTORE_COMPLETE',s['frame'],len(s['sensors']),flush=True)
