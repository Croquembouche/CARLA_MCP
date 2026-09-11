import json,httpx
from pathlib import Path
root=Path('data/parking-rules-audit');c=httpx.Client(base_url='http://127.0.0.1:8095',timeout=180)
def get(p):r=c.get('/api/'+p);r.raise_for_status();return r.json()
def command(action,p):return c.post('/api/command/'+action,json=p,headers={'X-Control-Client':'carla-control-center'})
s=get('status');cfg=get('configuration');old=json.loads((root/'restart-configuration.json').read_text());m=get('map')
assert s['recovery_operation']['stage']=='ready' and not s['running']
assert len(cfg['actors'])==len(old['actors'])==28 and len(s['sensors'])==6
assert [b['id'] for b in m['parking_spaces']]==json.loads((root/'report.json').read_text())['allowed_ids'];assert len(m['parking_excluded'])==28
old_ego=next(a for a in old['actors'] if a['role']=='ego');ego=next(a for a in cfg['actors'] if a['role']=='ego');assert ego['model']==old_ego['model']=='vehicle.lincoln.mkz_interior';assert sorted(ego['sensors'],key=lambda c:c['name'])==sorted(old_ego['sensors'],key=lambda c:c['name'])
r=command('spawn',{'role':'background','model':'vehicle.mini.cooper','parking_space':'P009'});assert r.status_code==400 and 'parking bay' in r.text,r.text
bg=next(a for a in cfg['actors'] if a['role']=='background');r=command('destination',{'id':bg['id'],'point':{'parking_space':'P009'}});assert r.status_code==400 and 'parking bay' in r.text,r.text
new=get('configuration');assert len(new['actors'])==28;assert next(a for a in new['actors'] if a['id']==bg['id'])['destination']==bg['destination']
r=command('run',{});r.raise_for_status();s=get('status');assert s['running'];assert not s.get('error'),s['error']
(root/'final-status.json').write_text(json.dumps(s,indent=2));(root/'final-configuration.json').write_text(json.dumps(get('configuration'),indent=2));report={'actors':28,'sensors':6,'ego':ego['id'],'running':True,'selectable':13,'excluded':28,'invalid_spawn_and_destination_rejected':True};(root/'live-verification.json').write_text(json.dumps(report,indent=2));print(report)
