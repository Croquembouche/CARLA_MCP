import json,urllib.request
from pathlib import Path
out=Path('data/parking-audit');base='http://127.0.0.1:8095'
def get(ep):
 with urllib.request.urlopen(base+'/api/'+ep,timeout=180) as r:return json.load(r)
s=get('status');cfg=get('configuration');m=get('map');old=json.loads((out/'restart-configuration.json').read_text());assert s['recovery_operation']['stage']=='ready' and not s.get('error');assert len(cfg['actors'])==len(old['actors'])==28;assert len(s['sensors'])==6;assert m['parking_spaces']==json.loads((out/'corrected-bays.json').read_text())
ego=next(a for a in cfg['actors'] if a['role']=='ego');old_ego=next(a for a in old['actors'] if a['role']=='ego');assert ego['model']==old_ego['model']=='vehicle.lincoln.mkz_interior';assert sorted(ego['sensors'],key=lambda c:c['name'])==sorted(old_ego['sensors'],key=lambda c:c['name']);assert ego['destination']==old_ego['destination']
assert 'P019' not in {p['id'] for p in m['parking_spaces']};assert len(m['parking_spaces'])==41
if json.loads((out/'restart-status.json').read_text())['running']:
 req=urllib.request.Request(base+'/api/command/run',data=b'{}',headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(req,timeout=180) as r:print(json.load(r))
s=get('status');(out/'final-status.json').write_text(json.dumps(s,indent=2));(out/'final-configuration.json').write_text(json.dumps(get('configuration'),indent=2));report={'actors':28,'ego_id':ego['id'],'sensors':6,'parking_spaces':41,'excluded':['P019'],'adjusted':m['parking_validation']['adjusted_bays'],'running':s['running'],'error':s.get('error')};(out/'live-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
