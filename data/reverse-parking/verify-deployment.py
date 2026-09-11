import json,time
from pathlib import Path
import httpx
out=Path(__file__).resolve().parent
c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180,headers={'X-Control-Client':'carla-control-center'})
def cmd(action,p={}):
 r=c.post('/api/command/'+action,json=p);r.raise_for_status();return r.json()
s=c.get('/api/status').json();assert s['recovery_operation']['stage']=='ready' and not s['running']
before=json.loads((out/'before-configuration.json').read_text())
config=c.get('/api/configuration').json();(out/'restored-configuration.json').write_text(json.dumps(config,indent=2))
print('config keys',list(config),flush=True)
assert len(s['managed'])==28 and len(s['sensors'])==6 and s['worker_count']==4
m=c.get('/api/map').json();assert len(m['parking_spaces'])==13
old_ego=next(a for a in before['actors'] if a['role']=='ego')
new_ego=next(a for a in config['actors'] if a['role']=='ego')
assert old_ego['model']==new_ego['model']=='vehicle.lincoln.mkz_interior'
assert old_ego['sensors']==new_ego['sensors']
print('RESTORED: 28 actors, six matching ego sensors, four workers, 13 allowed bays',flush=True)
aid=None
try:
 r=cmd('spawn',dict(role='background',planner='tm',model='vehicle.mini.cooper',spawn=dict(x=76.6767578125,y=66.34857940673828,z=0)))
 aid=r['id'];print('temporary actor',aid,flush=True)
 r=cmd('destination',dict(id=aid,point={'parking_space':'P025'}))
 assert r['parking_trip']['entry_strategy']=='reverse_in'
 assert r['route'][-1]['reverse'] and any(p.get('reverse') for p in r['route'])
 for _ in range(8):cmd('step')
 s=c.get('/api/status').json();trip=s['managed'][str(aid)]['parking_trip']
 assert trip['entry_strategy']=='reverse_in' and not trip['blocked']
 report=dict(temporary_actor=aid,parking_trip=trip,route_points=len(r['route']),reverse_points=sum(bool(p.get('reverse')) for p in r['route']),actors_restored=28,ego_sensors_preserved=6,workers=s['worker_count'],allowed_bays=13,error=s.get('error'))
 (out/'deployment-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
finally:
 if aid is not None:cmd('delete',{'id':aid})
s=c.get('/api/status').json();assert len(s['managed'])==28 and len(s['sensors'])==6 and not s.get('error')
(out/'restored-status.json').write_text(json.dumps(s,indent=2))
