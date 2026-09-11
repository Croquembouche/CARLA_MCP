import json,urllib.request,copy
from pathlib import Path
out=Path('data/ego-lincoln-replacement');base='http://127.0.0.1:8095'
def get(path):
 with urllib.request.urlopen(base+path,timeout=180) as r:return json.load(r)
def command(action,p={}):
 req=urllib.request.Request(base+'/api/command/'+action,data=json.dumps(p).encode(),headers={'Content-Type':'application/json','X-Control-Client':'carla-control-center'})
 with urllib.request.urlopen(req,timeout=600) as r:return json.load(r)
s=get('/api/status');cfg=get('/api/configuration');egos=[a for a in cfg['actors'] if a['role']=='ego'];assert len(egos)==1 and egos[0]['id']==28 and egos[0]['model']=='vehicle.ambulance.ford';assert not s.get('recording') and s['mode']=='live'
assert any(v['id']=='vehicle.lincoln.mkz_interior' for v in get('/api/catalog')['vehicles'])
old=egos[0];new=copy.deepcopy(old);new.pop('id');new['model']='vehicle.lincoln.mkz_interior';cabin=json.loads(Path('examples/lincoln-cabin-sensors.json').read_text())[0];new['sensors']=[copy.deepcopy(cabin) if a['name']=='cabin_overview' else a for a in new['sensors']]
(out/'before-configuration.json').write_text(json.dumps(cfg,indent=2));(out/'replacement-request.json').write_text(json.dumps(new,indent=2))
removed=False;replacement=None
try:
 if s['running']:print('PAUSE',command('pause'),flush=True)
 print('DELETE_OLD_EGO',command('delete',{'id':old['id']}),flush=True);removed=True
 try:replacement=command('spawn',new)
 except Exception:
  print('Replacement failed; restoring original ego.',flush=True);original={k:v for k,v in old.items() if k!='id'};print('ROLLBACK',command('spawn',original),flush=True);raise
 print('REPLACEMENT',json.dumps(replacement),flush=True);aid=replacement['id'];(out/'new-ego.json').write_text(json.dumps({'id':aid}))
 for i in range(12):command('step')
 current=get('/api/status');assert len(current['managed'])==len(s['managed']);assert len(current['sensors'])==len(s['sensors']);assert set(current['managed'])-set(s['managed'])=={str(aid)}
 assert current['managed'][str(aid)]['planner']==old['planner'];sensor=next(a for a in current['sensors'] if a['parent']==aid and a['name']=='cabin_overview')
 with urllib.request.urlopen(base+'/api/preview/'+str(sensor['id'])+'?width=960',timeout=60) as r:(out/'lincoln-cabin.jpg').write_bytes(r.read())
 (out/'configuration.json').write_text(json.dumps(get('/api/configuration'),indent=2));(out/'after-status.json').write_text(json.dumps(current,indent=2))
finally:
 if s['running']:print('RUN',command('run'),flush=True)
