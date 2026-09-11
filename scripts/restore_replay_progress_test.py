"""Restore the saved development scenario after the replay progress acceptance run."""
import json,time,httpx
from pathlib import Path
root=Path(__file__).resolve().parents[1];data=root/'data';config=json.loads((data/'replay-progress-restore-config.json').read_text())
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=240,headers={'X-Control-Client':'carla-control-center'})
def cmd(action,payload):
 r=c.post('/api/command/'+action,json=payload);r.raise_for_status();return r.json()
s=c.get('/api/status').json()
if s['phase']!='connected' or s.get('mode')!='live' or s['managed'] or s.get('recording'):raise RuntimeError('Requires the clean connected live scene from the acceptance restart')
ids={}
for actor in config['actors']:
 p={k:v for k,v in actor.items() if k!='id'}
 if p['role']=='pedestrian':p['spawn']={**p['spawn'],'z':max(0,p['spawn']['z']-1)}
 result=cmd('spawn',p);ids[str(actor['id'])]=result['id'];print('RESTORED',actor['role'],result['id'],flush=True)
cmd('weather',config['weather'])
for gid,program in config['movement_programs'].items():
 if program['active']:cmd('movement-program',dict(group_id=int(gid),operation='enable',**{k:program[k] for k in ('phases','yellow_time','all_red_time')}))
for _ in range(110):
 s=c.get('/api/status').json()
 if all(p.get('stage')=='green' for p in s['movement_programs'].values() if p['active']):break
 cmd('step',{})
s=c.get('/api/status').json();assert len(s['managed'])==len(config['actors']);assert len(s['sensors'])==sum(len(a.get('sensors',[])) for a in config['actors']);assert s['phase']=='connected' and s['mode']=='live' and not s['running'] and not s.get('error')
(data/'replay-progress-restored-ids.json').write_text(json.dumps(ids,indent=2));(data/'replay-progress-restored-state.json').write_text(json.dumps(s,indent=2));print('RESTORE_COMPLETE',s['frame'],len(s['sensors']),flush=True)
