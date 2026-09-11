import json,urllib.request
from pathlib import Path
out=Path('data/sidewalk-vehicles');base='http://127.0.0.1:8095'
def get(path):
 with urllib.request.urlopen(base+path,timeout=180) as r:return json.load(r)
def command(action,p={}):
 req=urllib.request.Request(base+'/api/command/'+action,data=json.dumps(p).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(req,timeout=600) as r:return json.load(r)
s=get('/api/status');saved=json.loads((out/'configuration.json').read_text());targets=json.loads((out/'removal-targets.json').read_text());sources={r['source'] for r in targets}
assert s['recovery_operation']['stage']=='ready' and not s.get('error')
assert len(s['managed'])==28 and len(s['sensors'])==6
assert not sources&{m.get('scene_source') for m in s['managed'].values()}
assert sources<={p['key'] for p in s['scene_vehicles']['hidden']}
retained=[a for a,m in s['managed'].items() if m.get('scene_source')=='SM_Harley2_423'];assert len(retained)==1
config=get('/api/configuration');ego=next(a for a in config['actors'] if a['role']=='ego');old_ego=next(a for a in saved['actors'] if a['role']=='ego');assert ego['model']==old_ego['model'] and ego['sensors']==old_ego['sensors']
result=command('convert-scene-vehicles');assert not result['created']
if json.loads((out/'before-status.json').read_text())['running']:command('run')
final=get('/api/status');assert final['running'] and not final.get('error')
(out/'restored-configuration.json').write_text(json.dumps(get('/api/configuration'),indent=2));(out/'final-status.json').write_text(json.dumps(final,indent=2))
print(json.dumps({'actors':len(final['managed']),'sensors':len(final['sensors']),'ego_id':ego['id'],'parked_motorcycle_id':int(retained[0]),'removed_sources':sorted(sources),'conversion_created':result['created'],'running':final['running'],'error':final.get('error')}))
